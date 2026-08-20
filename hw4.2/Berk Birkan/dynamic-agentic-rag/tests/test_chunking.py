from dynamic_rag.knowledge.chunking import MixedChunker
from dynamic_rag.models import Document


def words(text):
    return len(text.split())


def test_chunking_is_bounded_and_deterministic():
    doc = Document(" ".join(f"kelime{i}." for i in range(40)), "x.txt", "X")
    chunker = MixedChunker(words, target_tokens=10, overlap_tokens=2)
    first = chunker.split([doc])
    second = chunker.split([doc])
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert all(words(c.text) <= 10 for c in first)
    assert len(first) >= 4
