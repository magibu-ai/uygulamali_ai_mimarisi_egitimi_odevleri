"""LangGraph retrieve-grade-rewrite loop with bounded retries and abstention."""

from __future__ import annotations

from typing import Any, TypedDict

from dynamic_rag.models import RagAnswer, SearchHit
from dynamic_rag.rag.common import ABSTENTION, SYSTEM, context


class AgentState(TypedDict, total=False):
    question: str
    query: str
    hits: list[SearchHit]
    relevant: bool
    attempts: int
    answer: str
    trace: list[str]
    model: str
    api_key: str


class AgenticRAG:
    def __init__(self, knowledge_base: Any, llm: Any, *, threshold: float = 0.45, top_k: int = 4, max_attempts: int = 2):
        self.kb, self.llm = knowledge_base, llm
        self.threshold, self.top_k, self.max_attempts = threshold, top_k, max_attempts
        self.graph = self._build()

    def _build(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("grade", self._grade)
        graph.add_node("rewrite", self._rewrite)
        graph.add_node("answer", self._answer)
        graph.add_node("abstain", self._abstain)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "grade")
        graph.add_conditional_edges("grade", self._route, {"answer": "answer", "rewrite": "rewrite", "abstain": "abstain"})
        graph.add_edge("rewrite", "retrieve")
        graph.add_edge("answer", END)
        graph.add_edge("abstain", END)
        return graph.compile()

    def _retrieve(self, state: AgentState) -> dict:
        hits = self.kb.search(state.get("query", state["question"]), self.top_k)
        return {"hits": hits, "attempts": state.get("attempts", 0) + 1, "trace": state.get("trace", []) + ["retrieve"]}

    def _grade(self, state: AgentState) -> dict:
        score_pass = bool(state["hits"]) and state["hits"][0].similarity >= self.threshold
        if not score_pass:
            return {"relevant": False, "trace": state["trace"] + ["grade:score_fail"]}
        verdict = self.llm.json(
            [{"role": "system", "content": "Kanıtlar soruyu cevaplamak için yeterliyse yalnızca {\"relevant\": true}, değilse false döndür."}, {"role": "user", "content": f"SORU: {state['question']}\nKANITLAR:\n{context(state['hits'])}"}],
            model=state["model"], api_key=state["api_key"],
        )
        relevant = verdict.get("relevant") is True
        return {"relevant": relevant, "trace": state["trace"] + [f"grade:{'pass' if relevant else 'fail'}"]}

    def _route(self, state: AgentState) -> str:
        if state["relevant"]:
            return "answer"
        return "rewrite" if state["attempts"] < self.max_attempts else "abstain"

    def _rewrite(self, state: AgentState) -> dict:
        rewritten = self.llm.complete(
            [{"role": "system", "content": "Soruyu anlamını değiştirmeden semantik arama için kısa bir Türkçe sorguya dönüştür. Yalnızca sorguyu yaz."}, {"role": "user", "content": state["question"]}],
            model=state["model"], api_key=state["api_key"],
        )
        return {"query": rewritten.strip(), "trace": state["trace"] + ["rewrite"]}

    def _answer(self, state: AgentState) -> dict:
        answer = self.llm.complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"KANITLAR:\n{context(state['hits'])}\n\nSORU:\n{state['question']}"}],
            model=state["model"], api_key=state["api_key"],
        )
        return {"answer": answer.strip(), "trace": state["trace"] + ["generate"]}

    def _abstain(self, state: AgentState) -> dict:
        return {"answer": ABSTENTION, "hits": [], "trace": state["trace"] + ["abstain"]}

    def ask(self, question: str, *, model: str, api_key: str) -> RagAnswer:
        state = self.graph.invoke({"question": question, "query": question, "attempts": 0, "trace": [], "model": model, "api_key": api_key})
        answered = state["answer"] != ABSTENTION
        return RagAnswer(state["answer"], answered, state.get("hits", []), state["trace"])
