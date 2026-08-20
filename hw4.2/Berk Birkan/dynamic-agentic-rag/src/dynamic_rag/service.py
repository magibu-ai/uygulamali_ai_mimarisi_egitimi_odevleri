"""Session service that turns user content into a queryable RAG system."""

from __future__ import annotations

import uuid
from pathlib import Path

from dynamic_rag.ingestion.loaders import load_files, load_hf_dataset
from dynamic_rag.knowledge.chunking import MixedChunker
from dynamic_rag.knowledge.store import KnowledgeBase
from dynamic_rag.llm.openrouter import OpenRouterClient
from dynamic_rag.rag.agentic import AgenticRAG
from dynamic_rag.rag.common import sources
from dynamic_rag.rag.traditional import TraditionalRAG


class DynamicRagSession:
    def __init__(self, encoder, *, threshold: float = 0.45):
        import chromadb

        collection = chromadb.EphemeralClient().create_collection(
            f"kb_{uuid.uuid4().hex}", metadata={"hnsw:space": "cosine"}
        )
        self.encoder = encoder
        self.kb = KnowledgeBase(collection, encoder)
        self.llm = OpenRouterClient()
        self.threshold = threshold
        self.document_count = 0
        self.chunk_count = 0

    def build_from_files(self, paths: list[str | Path], raw_text: str = "") -> str:
        return self._index(load_files(paths, raw_text))

    def build_from_hf(self, repo_id: str, split: str, text_column: str, max_rows: int, token: str | None = None) -> str:
        return self._index(load_hf_dataset(repo_id, split=split, text_column=text_column, max_rows=max_rows, token=token))

    def _index(self, documents) -> str:
        chunks = MixedChunker(self.encoder.token_count).split(documents)
        if len(chunks) > 2000:
            raise ValueError(f"En fazla 2.000 chunk desteklenir; bu girdi {len(chunks)} chunk üretti.")
        self.kb.index(chunks)
        self.document_count += len(documents)
        self.chunk_count += len(chunks)
        return f"Bilgi tabanı hazır: {self.document_count} doküman, {self.chunk_count} chunk."

    def ask(self, question: str, mode: str, model: str, api_key: str, threshold: float | None = None):
        active_threshold = self.threshold if threshold is None else float(threshold)
        rag = AgenticRAG(self.kb, self.llm, threshold=active_threshold) if mode == "Agentic RAG" else TraditionalRAG(self.kb, self.llm, threshold=active_threshold)
        result = rag.ask(question, model=model, api_key=api_key)
        return result.text, sources(result.hits) or "Kaynak yok", " → ".join(result.trace)
