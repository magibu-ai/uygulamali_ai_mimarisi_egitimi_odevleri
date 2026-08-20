"""ChromaDB vector store (Phase 4).

Isolates all ChromaDB-specific logic behind a small abstraction. The rest of the
application only sees the structured search results produced here.

Critical detail: the collection uses ``hnsw:space = cosine``, so ChromaDB
returns cosine *distance*. This module converts it to cosine *similarity*
(``similarity = 1 - distance``) before exposing results — the raw distance is
never surfaced as the application's similarity score.
"""
from __future__ import annotations

from typing import Any

import numpy as np


# --------------------------------------------------------------------------- #
# Pure helpers (unit-testable without a running ChromaDB)
# --------------------------------------------------------------------------- #

def distance_to_similarity(distance: float) -> float:
    """Convert ChromaDB cosine distance to cosine similarity."""
    return 1.0 - float(distance)


def _safe_str(value: Any) -> str:
    """Coerce None/other to a string (Chroma metadata forbids None values)."""
    return "" if value is None else str(value)


def build_metadata(chunk: dict[str, Any]) -> dict[str, str]:
    """Build the stored metadata for a chunk.

    Note: ``chunk_text`` is intentionally NOT included — it is stored once as
    ChromaDB's document field, not duplicated into metadata. Missing titles are
    handled safely (empty string).
    """
    return {
        "url": _safe_str(chunk.get("url")),
        "title": _safe_str(chunk.get("title")),
        "source": _safe_str(chunk.get("source")),
        "parent_id": _safe_str(chunk.get("parent_id")),
    }


def check_unique_ids(ids: list[str]) -> None:
    """Raise ``ValueError`` if any id repeats."""
    seen: set[str] = set()
    dups: set[str] = set()
    for i in ids:
        if i in seen:
            dups.add(i)
        seen.add(i)
    if dups:
        raise ValueError(f"Duplicate chunk IDs detected: {sorted(dups)[:10]}")


def format_search_results(query_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a ChromaDB single-query result into ranked structured records."""
    ids = query_result["ids"][0]
    distances = query_result["distances"][0]
    documents = query_result["documents"][0]
    metadatas = query_result["metadatas"][0]

    results: list[dict[str, Any]] = []
    for rank, (cid, dist, doc, md) in enumerate(
        zip(ids, distances, documents, metadatas), start=1
    ):
        md = md or {}
        results.append(
            {
                "rank": rank,
                "chunk_id": cid,
                "similarity": distance_to_similarity(dist),
                "chunk_text": doc,
                "url": md.get("url", ""),
                "title": md.get("title", ""),
                "source": md.get("source", ""),
                "parent_id": md.get("parent_id", ""),
            }
        )
    return results


# --------------------------------------------------------------------------- #
# ChromaDB-backed store
# --------------------------------------------------------------------------- #

class ChromaStore:
    """Thin wrapper around a persistent ChromaDB cosine collection."""

    def __init__(self, persist_path: str, collection_name: str, space: str = "cosine"):
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.space = space
        self.client = None
        self.collection = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ChromaStore":
        vs = config["vectorstore"]
        return cls(
            persist_path=vs["persist_path"],
            collection_name=vs["collection_name"],
            space=vs["distance"],
        )

    def connect(self, fresh: bool = False) -> "ChromaStore":
        """Open the persistent client and get/create the cosine collection.

        ``fresh=True`` drops any existing collection first (used by ingestion so
        re-runs don't duplicate records).
        """
        import chromadb

        self.client = chromadb.PersistentClient(path=self.persist_path)
        if fresh:
            try:
                self.client.delete_collection(self.collection_name)
            except Exception:
                pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": self.space},
            embedding_function=None,  # we always supply embeddings explicitly
        )
        return self

    def count(self) -> int:
        return self.collection.count()

    def ingest(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        documents: list[str],
        metadatas: list[dict[str, str]],
        batch_size: int = 1000,
    ) -> None:
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self.collection.add(
                ids=ids[start:end],
                embeddings=[row.tolist() for row in embeddings[start:end]],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=[np.asarray(query_embedding, dtype=np.float32).tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return format_search_results(result)
