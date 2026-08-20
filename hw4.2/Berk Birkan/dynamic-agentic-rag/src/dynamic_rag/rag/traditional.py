"""Always-retrieve traditional RAG with a hard similarity gate."""

from __future__ import annotations

from typing import Any

from dynamic_rag.models import RagAnswer
from dynamic_rag.rag.common import ABSTENTION, SYSTEM, context


class TraditionalRAG:
    def __init__(self, knowledge_base: Any, llm: Any, *, threshold: float = 0.45, top_k: int = 4):
        self.knowledge_base = knowledge_base
        self.llm = llm
        self.threshold = threshold
        self.top_k = top_k

    def ask(self, question: str, *, model: str, api_key: str) -> RagAnswer:
        hits = self.knowledge_base.search(question, self.top_k)
        if not hits or hits[0].similarity < self.threshold:
            return RagAnswer(ABSTENTION, False, hits, ["retrieve", "abstain"])
        answer = self.llm.complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"KANITLAR:\n{context(hits)}\n\nSORU:\n{question}"}],
            model=model,
            api_key=api_key,
        )
        return RagAnswer(answer.strip(), True, hits, ["retrieve", "threshold_pass", "generate"])
