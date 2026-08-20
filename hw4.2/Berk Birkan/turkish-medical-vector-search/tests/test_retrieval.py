from turkish_medical_vector_search.retrieval.search import search_collection


class FakeCollection:
    def __init__(self, distance: float) -> None:
        self.distance = distance

    def query(self, **kwargs):
        del kwargs
        return {
            "ids": [["chunk_1"]],
            "documents": [["Kanıt metni"]],
            "metadatas": [[{"title": "Kaynak"}]],
            "distances": [[self.distance]],
        }


def test_threshold_accepts_sufficient_similarity() -> None:
    result = search_collection(
        FakeCollection(distance=0.40),
        question="Soru",
        query_vector=[0.0],
        top_k=1,
        threshold=0.4240,
        abstention_message="Dokümanlarda yok",
    )

    assert result.answerable is True
    assert result.message is None
    assert result.hits[0].similarity == 0.60


def test_threshold_returns_exact_abstention_message() -> None:
    message = "Bu sorunun cevabı dokümanlarımda yer almamaktadır."
    result = search_collection(
        FakeCollection(distance=0.70),
        question="Soru",
        query_vector=[0.0],
        top_k=1,
        threshold=0.4240,
        abstention_message=message,
    )

    assert result.answerable is False
    assert result.message == message
