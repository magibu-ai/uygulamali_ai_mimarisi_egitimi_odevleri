#!/usr/bin/env python3
"""Run one threshold-aware semantic search against the local Chroma index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.config import load_config  # noqa: E402
from turkish_medical_vector_search.embeddings.local import LocalSentenceEmbedder  # noqa: E402
from turkish_medical_vector_search.retrieval.search import search_collection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--threshold", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    embedder = LocalSentenceEmbedder(
        config.embedding.model_id,
        expected_dimension=config.embedding.dimension,
        normalize=config.embedding.normalize,
    )
    vector = embedder.encode_queries([args.question])[0].tolist()
    client = chromadb.PersistentClient(
        path=str(PROJECT_ROOT / config.vector_store.persist_directory)
    )
    collection = client.get_collection(config.vector_store.collection_name)
    result = search_collection(
        collection,
        question=args.question,
        query_vector=vector,
        top_k=args.top_k or config.retrieval.top_k,
        threshold=args.threshold if args.threshold is not None else config.retrieval.threshold,
        abstention_message=config.retrieval.abstention_message,
    )
    print(f"Answerable: {result.answerable}")
    if result.message:
        print(result.message)
    for rank, hit in enumerate(result.hits, start=1):
        print(f"\n#{rank} similarity={hit.similarity:.4f}")
        print(f"title={hit.metadata['title']}")
        print(f"url={hit.metadata['url']}")
        print(hit.chunk_text[:400].replace("\n", " "))


if __name__ == "__main__":
    main()

