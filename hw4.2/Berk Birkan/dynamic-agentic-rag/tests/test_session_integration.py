import math

from dynamic_rag.service import DynamicRagSession


class Encoder:
    def token_count(self, text):
        return len(text.split())

    def _encode(self, texts):
        vectors = []
        for text in texts:
            vector = [float(text.lower().count("elma") + 1), float(text.lower().count("armut") + 1)]
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector])
        return vectors

    encode_documents = _encode
    encode_queries = _encode


def test_sessions_use_isolated_chroma_collections():
    first = DynamicRagSession(Encoder())
    second = DynamicRagSession(Encoder())
    first.build_from_files([], "elma elma hakkında bilgi")
    second.build_from_files([], "armut armut hakkında bilgi")

    first_hit = first.kb.search("elma", 1)[0]
    second_hit = second.kb.search("elma", 1)[0]

    assert "elma" in first_hit.chunk.text
    assert "armut" in second_hit.chunk.text
    assert first.kb.collection.name != second.kb.collection.name
