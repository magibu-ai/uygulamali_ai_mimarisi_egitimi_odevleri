"""Production RAG pipeline with a threshold gate (Phase 7).

Flow:
    question -> query embedding -> ChromaDB top-k retrieval -> top-1 similarity
             -> threshold gate -> reject (no LLM)  OR  grounded LLM answer.

The gate runs BEFORE any LLM call: if the top-1 similarity is below the
configured threshold, the pipeline returns the exact rejection message and the
LLM is never invoked. All collaborators (embedder, store, llm) are injected, so
the whole flow is unit-testable offline with fakes.
"""
from __future__ import annotations

from typing import Any

from src.rag.prompt import build_context, build_prompt, build_sources


class RAGPipeline:
    def __init__(
        self,
        embedder: Any,
        store: Any,
        llm: Any,
        threshold: float,
        top_k: int,
        rejection_message: str,
        max_context_chars: int,
    ):
        self.embedder = embedder
        self.store = store
        self.llm = llm
        self.threshold = threshold
        self.top_k = top_k
        self.rejection_message = rejection_message
        self.max_context_chars = max_context_chars

    def answer(self, question: str) -> dict[str, Any]:
        query_vec = self.embedder.encode_queries([question])[0]
        hits = self.store.search(query_vec, top_k=self.top_k)

        top_similarity = float(hits[0]["similarity"]) if hits else 0.0
        retrieved_chunk_ids = [h["chunk_id"] for h in hits]

        base = {
            "question": question,
            "top_similarity": round(top_similarity, 4),
            "threshold": self.threshold,
            "retrieved_chunk_ids": retrieved_chunk_ids,
        }

        # --- threshold gate: reject BEFORE any LLM call ---
        if not hits or top_similarity < self.threshold:
            return {
                **base,
                "accepted": False,
                "answer": self.rejection_message,
                "sources": [],
                "llm_called": False,
            }

        # --- accepted: build grounded context and call the LLM ---
        context_text, used_chunks = build_context(hits, self.max_context_chars)
        system, user = build_prompt(question, context_text)
        answer_text = self.llm.generate(system, user)

        return {
            **base,
            "accepted": True,
            "answer": answer_text,
            "sources": build_sources(used_chunks),
            "llm_called": True,
        }


def build_pipeline(config: dict[str, Any]) -> RAGPipeline:
    """Wire a production pipeline from config (real embedder, store, llm).

    Imported lazily inside so unit tests never need the heavy dependencies.
    """
    from src.embeddings.embedder import Embedder
    from src.rag.llm import build_llm_client
    from src.vectorstore.chroma_store import ChromaStore

    embedder = Embedder.from_config(config).load()
    store = ChromaStore.from_config(config).connect(fresh=False)
    llm = build_llm_client(config)
    return RAGPipeline(
        embedder=embedder,
        store=store,
        llm=llm,
        threshold=config["retrieval"]["threshold"],
        top_k=config["retrieval"]["top_k"],
        rejection_message=config["rejection_message"],
        max_context_chars=config["rag"]["max_context_chars"],
    )
