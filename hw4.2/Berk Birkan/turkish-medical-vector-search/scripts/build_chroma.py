#!/usr/bin/env python3
"""Build the persistent cosine ChromaDB collection from embedded chunks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.config import load_config  # noqa: E402
from turkish_medical_vector_search.vectorstore.chroma import build_collection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data/processed/chunks_with_vectors.parquet",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    rows = pq.read_table(args.source).to_pylist()
    collection = build_collection(
        rows,
        persist_directory=PROJECT_ROOT / config.vector_store.persist_directory,
        collection_name=config.vector_store.collection_name,
        embedding_model=config.embedding.model_id,
    )
    print(f"Collection: {collection.name}")
    print(f"Records: {collection.count()}")


if __name__ == "__main__":
    main()

