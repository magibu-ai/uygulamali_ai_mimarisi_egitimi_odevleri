from dynamic_rag.models import Chunk, SearchHit
from dynamic_rag.rag.common import ABSTENTION
from dynamic_rag.rag.traditional import TraditionalRAG


class KB:
    def __init__(self, score): self.score = score
    def search(self, query, top_k):
        chunk = Chunk("c", "p", "kanıt", "s.txt", "S", 0)
        return [SearchHit(chunk, self.score)]


class LLM:
    def __init__(self): self.calls = 0
    def complete(self, *args, **kwargs): self.calls += 1; return "cevap [1]"


def test_threshold_rejection_never_calls_llm():
    llm = LLM()
    result = TraditionalRAG(KB(0.2), llm, threshold=0.45).ask("q", model="m", api_key="k")
    assert result.text == ABSTENTION
    assert llm.calls == 0


def test_accepted_context_calls_llm():
    llm = LLM()
    result = TraditionalRAG(KB(0.8), llm, threshold=0.45).ask("q", model="m", api_key="k")
    assert result.answered and llm.calls == 1
