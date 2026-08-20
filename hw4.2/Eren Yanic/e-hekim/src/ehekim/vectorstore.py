"""ChromaDB persistence and cosine search.

Two details matter enough to state explicitly:

* **Cosine, not L2.** Chroma's HNSW index defaults to squared L2. The collection
  is created with the cosine space so that the distance Chroma returns is
  ``1 - cosine_similarity`` and the threshold in the UI means what it says.
* **No built-in embedding function.** Vectors are always computed by
  :class:`~ehekim.embedding.Embedder` and passed in explicitly. Letting Chroma
  embed for us would silently drop the model's asymmetric query/document
  prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

logger = logging.getLogger(__name__)

COSINE_SPACE = "cosine"


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    chunk_text: str
    similarity: float
    url: str
    title: str
    source: str
    parent_id: str
    chunk_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _create_collection(client, name: str):
    """Create the collection with cosine space across chromadb API revisions."""
    # chromadb >= 1.x prefers the structured `configuration` argument; older
    # releases only understand the `hnsw:space` metadata key. Try the modern
    # form first and fall back, so the project works on either.
    try:
        return client.create_collection(
            name=name,
            configuration={"hnsw": {"space": COSINE_SPACE}},
            embedding_function=None,
        )
    except TypeError:
        return client.create_collection(
            name=name,
            metadata={"hnsw:space": COSINE_SPACE},
            embedding_function=None,
        )


class VectorStore:
    """Thin, explicit wrapper over a persistent Chroma collection."""

    def __init__(self, persist_dir: Path | str, collection_name: str) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self.collection = self._open_or_create()

    def _open_or_create(self):
        try:
            return self.client.get_collection(name=self.collection_name, embedding_function=None)
        except Exception:
            return _create_collection(self.client, self.collection_name)

    # -- ingestion ---------------------------------------------------------
    def recreate(self) -> None:
        """Drop and re-create the collection. Used only by the ingest script."""
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self.collection = _create_collection(self.client, self.collection_name)

    def _max_batch(self) -> int:
        try:
            return max(1, int(self.client.get_max_batch_size()))
        except Exception:
            return 2000

    def add(
        self,
        ids: Sequence[str],
        embeddings: np.ndarray,
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        if not (len(ids) == len(documents) == len(metadatas) == len(embeddings)):
            raise ValueError("ids, embeddings, documents ve metadatas aynı uzunlukta olmalı.")
        batch = min(self._max_batch(), 1000)
        for start in range(0, len(ids), batch):
            stop = start + batch
            self.collection.add(
                ids=list(ids[start:stop]),
                embeddings=embeddings[start:stop].tolist(),
                documents=list(documents[start:stop]),
                metadatas=list(metadatas[start:stop]),
            )

    # -- search ------------------------------------------------------------
    def count(self) -> int:
        return int(self.collection.count())

    def get_siblings(self, parent_id: str, indices: Sequence[int]) -> list[SearchHit]:
        """Fetch specific chunks of one article by position, without scoring.

        Used for parent-context expansion: a chunk can rank highest for a query
        while the sentence that actually answers it sits in the neighbouring
        chunk of the same article. Similarity is reported as ``nan`` because
        these passages were fetched by position, not retrieved by score.
        """
        wanted = [int(i) for i in indices if int(i) >= 0]
        if not wanted:
            return []
        result = self.collection.get(
            where={
                "$and": [
                    {"parent_id": {"$eq": parent_id}},
                    {"chunk_index": {"$in": wanted}},
                ]
            },
            include=["documents", "metadatas"],
        )
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        hits: list[SearchHit] = []
        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            meta = metadata or {}
            hits.append(
                SearchHit(
                    chunk_id=str(chunk_id),
                    chunk_text=document or "",
                    similarity=float("nan"),
                    url=str(meta.get("url", "")),
                    title=str(meta.get("title", "")),
                    source=str(meta.get("source", "")),
                    parent_id=str(meta.get("parent_id", "")),
                    chunk_index=int(meta.get("chunk_index", 0) or 0),
                )
            )
        hits.sort(key=lambda h: h.chunk_index)
        return hits

    def query(self, embedding: np.ndarray, top_k: int) -> list[SearchHit]:
        if self.count() == 0:
            return []
        n = max(1, min(int(top_k), self.count()))
        result = self.collection.query(
            query_embeddings=[np.asarray(embedding, dtype=np.float32).tolist()],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        return list(_iter_hits(result))


def _iter_hits(result: dict[str, Any]) -> Iterable[SearchHit]:
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        meta = metadata or {}
        # Cosine space: distance = 1 - cosine_similarity. Clamp to absorb the
        # small float error HNSW can introduce at the extremes.
        similarity = float(np.clip(1.0 - float(distance), -1.0, 1.0))
        yield SearchHit(
            chunk_id=str(chunk_id),
            chunk_text=document or "",
            similarity=similarity,
            url=str(meta.get("url", "")),
            title=str(meta.get("title", "")),
            source=str(meta.get("source", "")),
            parent_id=str(meta.get("parent_id", "")),
            chunk_index=int(meta.get("chunk_index", 0) or 0),
        )
