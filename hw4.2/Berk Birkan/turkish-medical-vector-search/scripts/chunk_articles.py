#!/usr/bin/env python3
"""Chunk the deterministic article sample with the embedding model tokenizer."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.chunking.mixed import MixedChunker, chunk_articles  # noqa: E402
from turkish_medical_vector_search.config import load_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data/interim/selected_articles.parquet",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data/processed/chunks.parquet",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports/metrics/chunking_summary.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    tokenizer = AutoTokenizer.from_pretrained(
        config.embedding.model_id,
        extra_special_tokens={},
    )
    chunker = MixedChunker(
        tokenizer,
        target_tokens=config.chunking.target_tokens,
        overlap_tokens=config.chunking.overlap_tokens,
        min_chunk_tokens=config.chunking.min_chunk_tokens,
    )
    source = pq.read_table(args.source)
    rows = chunk_articles(source, chunker)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.output, compression="zstd")

    token_counts = [row["token_count"] for row in rows]
    per_parent: dict[str, int] = {}
    for row in rows:
        per_parent[row["parent_id"]] = per_parent.get(row["parent_id"], 0) + 1
    report = {
        "article_count": source.num_rows,
        "chunk_count": len(rows),
        "embedding_model": config.embedding.model_id,
        "tokenizer_patch": "not_applied_custom_split_pretokenizer",
        "target_tokens": config.chunking.target_tokens,
        "overlap_tokens": config.chunking.overlap_tokens,
        "min_chunk_tokens": config.chunking.min_chunk_tokens,
        "token_count": {
            "min": min(token_counts),
            "median": statistics.median(token_counts),
            "mean": statistics.fmean(token_counts),
            "max": max(token_counts),
        },
        "chunks_per_article": {
            "min": min(per_parent.values()),
            "median": statistics.median(per_parent.values()),
            "mean": statistics.fmean(per_parent.values()),
            "max": max(per_parent.values()),
        },
        "articles_without_chunks": source.num_rows - len(per_parent),
        "chunks_over_target": sum(count > config.chunking.target_tokens for count in token_counts),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(rows)} chunks from {source.num_rows} articles")
    print(f"Output: {args.output}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
