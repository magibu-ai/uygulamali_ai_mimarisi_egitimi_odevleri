"""Phase 2 pipeline: chunk the 300 selected documents.

Usage:
    python scripts/build_chunks.py

Reads all parameters from ``configs/config.yaml``. Produces:
  * data/processed/chunks.jsonl        (all chunks, UTF-8, one JSON per line)
  * artifacts/chunk_statistics.json    (chunk statistics + integrity checks)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, median

# Allow running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, resolve_path  # noqa: E402
from src.data.chunker import chunk_documents  # noqa: E402
from src.tokenizer import get_tokenizer  # noqa: E402


def _read_documents(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _percentile(sorted_values: list[int], pct: float) -> float:
    """Nearest-rank percentile on an already-sorted list."""
    if not sorted_values:
        return 0.0
    rank = max(1, int(round(pct / 100.0 * len(sorted_values))))
    return float(sorted_values[min(rank, len(sorted_values)) - 1])


def _distribution(values: list[int], edges: list[int]) -> dict[str, int]:
    """Bucket counts using half-open bins [edges[i], edges[i+1])."""
    buckets: dict[str, int] = {}
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        label = f"{lo}-{hi - 1}"
        buckets[label] = sum(1 for v in values if lo <= v < hi)
    buckets[f"{edges[-1]}+"] = sum(1 for v in values if v >= edges[-1])
    return buckets


def compute_statistics(
    documents: list[dict], chunks: list[dict], max_tokens: int
) -> dict:
    token_counts = sorted(c["token_count"] for c in chunks)

    # chunks per document
    per_doc: dict[str, int] = {d["doc_id"]: 0 for d in documents}
    for c in chunks:
        per_doc[c["parent_id"]] = per_doc.get(c["parent_id"], 0) + 1
    per_doc_counts = sorted(per_doc.values())
    docs_without_chunks = [doc_id for doc_id, n in per_doc.items() if n == 0]

    # integrity: every source word must appear in at least one of its chunks
    chunks_by_parent: dict[str, list[dict]] = {}
    for c in chunks:
        chunks_by_parent.setdefault(c["parent_id"], []).append(c)
    docs_with_lost_words = 0
    total_lost_words = 0
    total_source_words = 0
    for d in documents:
        source_words = set(d["text"].split())
        total_source_words += len(d["text"].split())
        covered: set[str] = set()
        for c in chunks_by_parent.get(d["doc_id"], []):
            covered.update(c["chunk_text"].split())
        lost = source_words - covered
        if lost:
            docs_with_lost_words += 1
            total_lost_words += len(lost)

    empty_chunks = sum(1 for c in chunks if not c["chunk_text"].strip())
    oversized = sum(1 for c in chunks if c["token_count"] > max_tokens)

    return {
        "source_document_count": len(documents),
        "chunk_count": len(chunks),
        "chunks_per_document": {
            "min": per_doc_counts[0] if per_doc_counts else 0,
            "max": per_doc_counts[-1] if per_doc_counts else 0,
            "mean": round(mean(per_doc_counts), 2) if per_doc_counts else 0,
            "median": round(median(per_doc_counts), 2) if per_doc_counts else 0,
        },
        "token_counts": {
            "min": token_counts[0] if token_counts else 0,
            "max": token_counts[-1] if token_counts else 0,
            "mean": round(mean(token_counts), 2) if token_counts else 0,
            "median": round(median(token_counts), 2) if token_counts else 0,
            "p95": _percentile(token_counts, 95),
        },
        "empty_chunk_count": empty_chunks,
        "documents_without_chunks": len(docs_without_chunks),
        "documents_without_chunks_ids": docs_without_chunks,
        "oversized_chunks": oversized,
        "max_tokens_limit": max_tokens,
        "integrity": {
            "total_source_words": total_source_words,
            "documents_with_lost_words": docs_with_lost_words,
            "total_lost_words": total_lost_words,
            "coverage_ok": docs_with_lost_words == 0,
        },
        "distributions": {
            "token_count_buckets": _distribution(
                token_counts, [0, 30, 128, 256, 384, 512]
            ),
            "chunks_per_document_buckets": _distribution(
                per_doc_counts, [1, 2, 4, 8, 16, 32]
            ),
        },
    }


def main() -> None:
    config = load_config()
    ch_cfg = config["chunking"]

    docs_path = resolve_path(config["dataset"]["selected_output"])
    print(f"[1/4] Reading selected documents from {docs_path} ...")
    documents = _read_documents(docs_path)
    print(f"      {len(documents)} documents")

    print("[2/4] Chunking (tokenizer="
          f"{ch_cfg['tokenizer']['backend']}:{ch_cfg['tokenizer']['encoding']}, "
          f"max_tokens={ch_cfg['max_tokens']}, "
          f"overlap={ch_cfg['overlap_tokens']}, min={ch_cfg['min_tokens']}) ...")
    tokenizer = get_tokenizer(config)
    chunks = chunk_documents(
        documents,
        tokenizer,
        max_tokens=ch_cfg["max_tokens"],
        overlap_tokens=ch_cfg["overlap_tokens"],
        min_tokens=ch_cfg["min_tokens"],
    )
    print(f"      produced {len(chunks)} chunks")

    print("[3/4] Writing chunks ...")
    out_path = resolve_path(ch_cfg["chunks_output"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"      -> {out_path}")

    print("[4/4] Writing statistics ...")
    statistics = compute_statistics(documents, chunks, ch_cfg["max_tokens"])
    stats_path = resolve_path(ch_cfg["statistics_output"])
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as handle:
        json.dump(statistics, handle, ensure_ascii=False, indent=2)
    print(f"      -> {stats_path}")

    print("\nDone. Summary:")
    print(f"  documents         : {statistics['source_document_count']}")
    print(f"  chunks            : {statistics['chunk_count']}")
    print(f"  empty chunks      : {statistics['empty_chunk_count']}")
    print(f"  docs w/o chunks   : {statistics['documents_without_chunks']}")
    print(f"  oversized chunks  : {statistics['oversized_chunks']}")
    print(f"  coverage ok       : {statistics['integrity']['coverage_ok']}")


if __name__ == "__main__":
    main()
