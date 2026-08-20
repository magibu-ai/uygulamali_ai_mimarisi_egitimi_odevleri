"""Phase 3 pipeline: embed all Phase 2 chunks with the locked model.

Usage:
    python scripts/build_embeddings.py

Reads all parameters from ``configs/config.yaml``. Produces:
  * artifacts/embeddings.npz             (embeddings + aligned chunk_ids)
  * artifacts/embedding_statistics.json  (metadata + validation report)

Fails loudly (does not truncate) if any chunk exceeds the model context.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Allow running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import (  # noqa: E402
    Embedder,
    assert_embeddings_valid,
    check_alignment,
    find_overlength_chunks,
    get_model_revision,
)


def _read_chunks(path: Path) -> tuple[list[str], list[str]]:
    ids, texts = [], []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rec = json.loads(line)
                ids.append(rec["chunk_id"])
                texts.append(rec["chunk_text"])
    return ids, texts


def main() -> None:
    config = load_config()
    emb_cfg = config["embedding"]

    chunks_path = resolve_path(config["chunking"]["chunks_output"])
    print(f"[1/6] Reading chunks from {chunks_path} ...")
    chunk_ids, texts = _read_chunks(chunks_path)
    print(f"      {len(chunk_ids)} chunks")

    print(f"[2/6] Loading model '{emb_cfg['model_name']}' ...")
    t0 = time.time()
    embedder = Embedder.from_config(config).load()
    print(f"      loaded in {time.time() - t0:.0f}s on device={embedder.device}; "
          f"dim={embedder.expected_dim}, max_seq_length={embedder.max_seq_length}")

    print("[3/6] Validating chunk token lengths against model context ...")
    offenders = find_overlength_chunks(
        chunk_ids, texts, embedder.count_tokens, embedder.max_seq_length
    )
    token_lengths = [embedder.count_tokens(t) for t in texts]
    if offenders:
        ids = ", ".join(o["chunk_id"] for o in offenders[:20])
        raise SystemExit(
            f"ABORT: {len(offenders)} chunk(s) exceed model max_seq_length "
            f"{embedder.max_seq_length}; refusing to truncate. Offending: {ids}"
        )
    print(f"      OK: 0 chunks exceed {embedder.max_seq_length} "
          f"(max observed {max(token_lengths)})")

    print(f"[4/6] Encoding {len(texts)} chunks (batch_size={embedder.batch_size}) ...")
    t0 = time.time()
    embeddings = embedder.encode_documents(texts)
    print(f"      encoded in {time.time() - t0:.0f}s; shape={embeddings.shape}")

    print("[5/6] Validating embeddings ...")
    check_alignment(chunk_ids, embeddings)
    norm_stats = assert_embeddings_valid(embeddings, embedder.expected_dim)
    assert embeddings.shape[0] == len(chunk_ids), "count mismatch"
    assert embeddings.dtype == np.float32
    print(f"      OK: count={embeddings.shape[0]}, dim={embeddings.shape[1]}, "
          f"no NaN/Inf, norms~1.0 (max dev {norm_stats['norm_max_abs_deviation']:.2e})")

    print("[6/6] Saving embeddings and statistics ...")
    out_path = resolve_path(emb_cfg["embeddings_output"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        embeddings=embeddings,
        chunk_ids=np.array(chunk_ids, dtype=object),
    )
    print(f"      -> {out_path}")

    revision = get_model_revision(embedder.model_name)
    statistics = {
        **embedder.metadata(),
        "model_revision": revision,
        "model_revision_note": (
            "resolved from Hugging Face Hub" if revision
            else "could not be determined (offline or unavailable)"
        ),
        "num_chunks": len(chunk_ids),
        "num_embeddings": int(embeddings.shape[0]),
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "count_match": embeddings.shape[0] == len(chunk_ids),
            "dimension_ok": embeddings.shape[1] == embedder.expected_dim,
            "no_nan": not bool(np.isnan(embeddings).any()),
            "no_inf": not bool(np.isinf(embeddings).any()),
            "normalized": True,
            "alignment_ok": True,
            "overlength_chunks": len(offenders),
            **norm_stats,
        },
        "token_length_stats_model_tokenizer": {
            "min": int(min(token_lengths)),
            "max": int(max(token_lengths)),
            "mean": round(float(np.mean(token_lengths)), 2),
            "p95": int(np.percentile(token_lengths, 95)),
            "max_seq_length": embedder.max_seq_length,
        },
    }
    stats_path = resolve_path(emb_cfg["statistics_output"])
    with open(stats_path, "w", encoding="utf-8") as handle:
        json.dump(statistics, handle, ensure_ascii=False, indent=2)
    print(f"      -> {stats_path}")

    print("\nDone. Summary:")
    print(f"  model        : {statistics['model_name']} (rev {revision})")
    print(f"  device       : {statistics['device']}")
    print(f"  embeddings   : {statistics['num_embeddings']} x {statistics['embedding_dim']}")
    print(f"  validation   : all checks passed")


if __name__ == "__main__":
    main()
