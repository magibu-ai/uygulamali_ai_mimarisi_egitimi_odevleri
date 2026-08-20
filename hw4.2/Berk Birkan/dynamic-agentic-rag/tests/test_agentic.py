from dynamic_rag.models import Chunk, SearchHit
from dynamic_rag.rag.agentic import AgenticRAG
from dynamic_rag.rag.common import ABSTENTION


class KB:
    def __init__(self, scores):
        self.scores = iter(scores)
        self.queries = []

    def search(self, query, top_k):
        self.queries.append(query)
        score = next(self.scores)
        chunk = Chunk("c", "p", "kanıt metni", "doc.txt", "Belge", 0)
        return [SearchHit(chunk, score)]


class LLM:
    def __init__(self, relevant=True):
        self.relevant = relevant
        self.complete_calls = []
        self.json_calls = 0

    def complete(self, messages, **kwargs):
        self.complete_calls.append(messages)
        if "dönüştür" in messages[0]["content"]:
            return "yeniden yazılan sorgu"
        return "kaynaklı cevap [1]"

    def json(self, messages, **kwargs):
        self.json_calls += 1
        return {"relevant": self.relevant}


def test_agent_rewrites_once_then_abstains_without_grading_low_scores():
    kb, llm = KB([0.1, 0.2]), LLM()
    answer = AgenticRAG(kb, llm, threshold=0.45, max_attempts=2).ask("soru", model="m", api_key="k")
    assert answer.text == ABSTENTION
    assert kb.queries == ["soru", "yeniden yazılan sorgu"]
    assert llm.json_calls == 0
    assert answer.trace.count("retrieve") == 2
    assert answer.trace[-1] == "abstain"


def test_agent_grades_and_answers_relevant_high_score_context():
    kb, llm = KB([0.8]), LLM(relevant=True)
    answer = AgenticRAG(kb, llm, threshold=0.45).ask("soru", model="m", api_key="k")
    assert answer.answered
    assert answer.text == "kaynaklı cevap [1]"
    assert llm.json_calls == 1
    assert answer.trace == ["retrieve", "grade:pass", "generate"]
