from turkish_medical_vector_search.generation.local_qwen import answer_from_search
from turkish_medical_vector_search.retrieval.search import SearchHit, SearchResult


class RecordingGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return "Kanıta dayalı cevap [1]"


def test_rejected_search_never_calls_generator():
    generator = RecordingGenerator()
    result = SearchResult("alakasız soru", False, [], "kesin ret")

    answer = answer_from_search(result, generator)

    assert answer.text == "kesin ret"
    assert answer.answered is False
    assert answer.sources == []
    assert generator.calls == []


def test_accepted_search_builds_grounded_prompt_and_sources():
    generator = RecordingGenerator()
    hit = SearchHit(
        chunk_id="chunk-1",
        chunk_text="Kanıt metni",
        similarity=0.71,
        metadata={"title": "Makale", "url": "https://example.org/article"},
    )
    result = SearchResult("Soru?", True, [hit], None)

    answer = answer_from_search(result, generator)

    assert answer.answered is True
    assert answer.text == "Kanıta dayalı cevap [1]"
    assert answer.sources[0]["chunk_id"] == "chunk-1"
    assert "Kanıt metni" in generator.calls[0][1]
    assert "Soru?" in generator.calls[0][1]
