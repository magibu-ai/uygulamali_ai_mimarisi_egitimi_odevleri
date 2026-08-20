"""Search Chroma with locally encoded query vectors and explicit abstention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from turkish_medical_vector_search.vectorstore.chroma import cosine_distance_to_similarity


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    chunk_text: str
    similarity: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    question: str
    answerable: bool
    hits: list[SearchHit]
    message: str | None


def search_collection(
    collection: Any,
    *,
    question: str,
    query_vector: list[float],
    top_k: int,
    threshold: float | None,
    abstention_message: str,
) -> SearchResult:
    """Retrieve top-k chunks and apply a cosine similarity threshold."""

    raw = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = raw["ids"][0]
    documents = raw["documents"][0]
    metadatas = raw["metadatas"][0]
    distances = raw["distances"][0]
    hits = [
        SearchHit(
            chunk_id=chunk_id,
            chunk_text=document,
            similarity=cosine_distance_to_similarity(distance),
            metadata=metadata,
        )
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        )
    ]
    best_score = hits[0].similarity if hits else float("-inf")
    answerable = bool(hits) and (threshold is None or best_score >= threshold)
    return SearchResult(
        question=question,
        answerable=answerable,
        hits=hits,
        message=None if answerable else abstention_message,
    )
