"""Phase 4 pipeline: ingest embeddings into a persistent ChromaDB collection.

Usage:
    python scripts/build_vector_db.py

Reads all parameters from ``configs/config.yaml``. Produces the persistent
ChromaDB store at ``vectorstore.persist_path`` (gitignored) and a small
``artifacts/vectorstore_statistics.json`` metadata file.

Validates all ingestion invariants and verifies persistence across a client
recreation. Fails loudly on any violation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# Allow running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import (  # noqa: E402
    Embedder,
    assert_embeddings_valid,
    check_alignment,
)
from src.vectorstore.chroma_store import (  # noqa: E402
    ChromaStore,
    build_metadata,
    check_unique_ids,
)

PILOT_SMOKE_QUERY = "Hipertansiyon belirtileri nelerdir?"  # diagnostic only


def _read_chunks(path: Path):
    ids, texts, metas = [], [], []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rec = json.loads(line)
                ids.append(rec["chunk_id"])
                texts.append(rec["chunk_text"])
                metas.append(build_metadata(rec))
    return ids, texts, metas


def main() -> None:
    config = load_config()
    expected_dim = config["embedding"]["expected_dim"]
    top_k = config["retrieval"]["top_k"]

    chunks_path = resolve_path(config["chunking"]["chunks_output"])
    emb_path = resolve_path(config["embedding"]["embeddings_output"])
    print(f"[1/7] Reading chunks + embeddings ...")
    ids, texts, metas = _read_chunks(chunks_path)
    npz = np.load(emb_path, allow_pickle=True)
    embeddings = npz["embeddings"].astype(np.float32)
    emb_ids = [str(x) for x in npz["chunk_ids"]]
    print(f"      {len(ids)} chunks, embeddings shape {embeddings.shape}")

    print("[2/7] Validating ingestion invariants ...")
    if emb_ids != ids:
        raise SystemExit("ABORT: embedding chunk_ids are not aligned with chunks.jsonl")
    if not (len(ids) == len(texts) == embeddings.shape[0]):
        raise SystemExit("ABORT: chunk / embedding count mismatch")
    check_alignment(ids, embeddings)
    check_unique_ids(ids)
    norm_stats = assert_embeddings_valid(embeddings, expected_dim)  # dim/NaN/Inf/norm
    print(f"      OK: {len(ids)} aligned, unique, dim={expected_dim}, "
          f"no NaN/Inf, normalized (max dev {norm_stats['norm_max_abs_deviation']:.2e})")

    print("[3/7] Creating fresh cosine collection and ingesting ...")
    store = ChromaStore.from_config(config).connect(fresh=True)
    store.ingest(ids, embeddings, texts, metas)
    count = store.count()
    print(f"      ingested; collection count = {count}")
    if count != len(ids):
        raise SystemExit(f"ABORT: expected {len(ids)} records, got {count}")

    print("[4/7] Verifying persistence across client recreation ...")
    del store
    store2 = ChromaStore.from_config(config).connect(fresh=False)
    reloaded = store2.count()
    print(f"      reloaded collection count = {reloaded}")
    if reloaded != len(ids):
        raise SystemExit(f"ABORT: persistence failure, got {reloaded}")

    print("[5/7] Smoke test A: search using an existing stored embedding ...")
    probe_idx = 0
    resA = store2.search(embeddings[probe_idx], top_k=top_k)
    top = resA[0]
    print(f"      probe chunk={ids[probe_idx]} -> top1={top['chunk_id']} "
          f"similarity={top['similarity']:.4f}")
    if top["chunk_id"] != ids[probe_idx] or top["similarity"] < 0.999:
        raise SystemExit("ABORT: self-retrieval smoke test failed")

    print("[6/7] Smoke test B: known pilot query (diagnostic, not saved) ...")
    embedder = Embedder.from_config(config).load()
    q_emb = embedder.encode_queries([PILOT_SMOKE_QUERY])[0]
    resB = store2.search(q_emb, top_k=top_k)
    for r in resB:
        print(f"      #{r['rank']} sim={r['similarity']:.4f} "
              f"[{r['source']}] {r['title'][:60]}")
    assert resB and all(0.0 <= r["similarity"] <= 1.0001 for r in resB)

    print("[7/7] Writing vectorstore metadata ...")
    stats = {
        "collection_name": store2.collection_name,
        "persist_path": store2.persist_path,
        "distance_space": store2.space,
        "similarity_formula": "similarity = 1 - cosine_distance",
        "embedding_dim": expected_dim,
        "num_records": reloaded,
        "unique_ids": True,
        "metadata_fields": ["url", "title", "source", "parent_id"],
        "document_field": "chunk_text",
        "default_top_k": top_k,
        "persistence_verified": True,
        "smoke_test_self_retrieval_similarity": round(top["similarity"], 6),
        "smoke_test_query": PILOT_SMOKE_QUERY,
        "smoke_test_top1": {
            "chunk_id": resB[0]["chunk_id"],
            "title": resB[0]["title"],
            "similarity": round(resB[0]["similarity"], 4),
        },
    }
    stats_path = resolve_path("artifacts/vectorstore_statistics.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)
    print(f"      -> {stats_path}")

    print("\nDone. Collection persisted with "
          f"{reloaded} records at {store2.persist_path}")


if __name__ == "__main__":
    main()
