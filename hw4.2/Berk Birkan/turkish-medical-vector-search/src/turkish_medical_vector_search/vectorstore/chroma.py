"""ChromaDB collection construction and cosine score conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import chromadb


def cosine_distance_to_similarity(distance: float) -> float:
    """Convert Chroma cosine distance to cosine similarity."""

    return 1.0 - float(distance)


def batched(values: Sequence[Any], batch_size: int) -> Iterable[Sequence[Any]]:
    """Yield stable slices from a sequence."""

    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def build_collection(
    rows: list[dict[str, Any]],
    *,
    persist_directory: str | Path,
    collection_name: str,
    embedding_model: str,
    batch_size: int = 100,
) -> Any:
    """Create or idempotently update a cosine Chroma collection."""

    client = chromadb.PersistentClient(path=str(persist_directory))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": embedding_model,
        },
    )
    expected_ids = {row["chunk_id"] for row in rows}
    if collection.count() not in {0, len(expected_ids)}:
        raise RuntimeError(
            "Existing collection count does not match the current dataset; "
            "use a new collection name or rebuild the generated index"
        )

    for batch in batched(rows, batch_size):
        collection.upsert(
            ids=[row["chunk_id"] for row in batch],
            documents=[row["chunk_text"] for row in batch],
            embeddings=[row["chunk_vector"] for row in batch],
            metadatas=[
                {
                    "parent_id": row["parent_id"],
                    "url": row["url"],
                    "title": row["title"],
                    "branch": row["branch"],
                    "chunk_index": row["chunk_index"],
                    "token_count": row["token_count"],
                }
                for row in batch
            ],
        )
    if collection.count() != len(expected_ids):
        raise RuntimeError("Chroma collection count validation failed")
    return collection

