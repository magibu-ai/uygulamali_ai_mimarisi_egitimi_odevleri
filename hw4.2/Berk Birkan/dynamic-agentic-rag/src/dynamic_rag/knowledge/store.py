"""Per-session Chroma knowledge base."""

from __future__ import annotations

from typing import Any, Protocol

from dynamic_rag.models import Chunk, SearchHit


class Encoder(Protocol):
    def encode_documents(self, texts: list[str]) -> list[list[float]]: ...
    def encode_queries(self, texts: list[str]) -> list[list[float]]: ...


class KnowledgeBase:
    def __init__(self, collection: Any, encoder: Encoder):
        self.collection = collection
        self.encoder = encoder

    def index(self, chunks: list[Chunk]) -> int:
        if not chunks:
            raise ValueError("Indexlenecek chunk yok.")
        embeddings = self.encoder.encode_documents([c.text for c in chunks])
        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[{"parent_id": c.parent_id, "source": c.source, "title": c.title, "index": c.index, **{k: v for k, v in c.metadata.items() if isinstance(v, (str, int, float, bool))}} for c in chunks],
        )
        return len(chunks)

    def search(self, query: str, top_k: int = 4) -> list[SearchHit]:
        vector = self.encoder.encode_queries([query])[0]
        raw = self.collection.query(query_embeddings=[vector], n_results=top_k, include=["documents", "metadatas", "distances"])
        hits = []
        for cid, text, meta, distance in zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]):
            chunk = Chunk(cid, meta["parent_id"], text, meta["source"], meta.get("title", ""), int(meta.get("index", 0)), meta)
            hits.append(SearchHit(chunk, max(-1.0, min(1.0, 1.0 - float(distance)))))
        return hits
