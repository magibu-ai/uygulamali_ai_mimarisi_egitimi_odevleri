"""Chunker behaviour, exercised with a deterministic fake tokenizer."""

from __future__ import annotations

import pytest

from ehekim.chunking import chunk_article, normalize_text, split_sentences


class WordTokenizer:
    """Whitespace tokenizer: one token per word, so counts are predictable."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        return [hash(w) % 1000 for w in text.split()]

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        return " ".join("w" for _ in ids)


@pytest.fixture
def tok() -> WordTokenizer:
    return WordTokenizer()


class TestNormalize:
    def test_collapses_excess_blank_lines_and_spaces(self):
        assert normalize_text("a\n\n\n\nb\r\nc   d") == "a\n\nb\nc d"

    def test_empty_input(self):
        assert normalize_text("") == ""
        assert normalize_text("   \n  ") == ""


class TestSentenceSplitting:
    def test_splits_on_terminal_punctuation(self):
        out = split_sentences("Birinci cümle. İkinci cümle! Üçüncü cümle?")
        assert out == ["Birinci cümle.", "İkinci cümle!", "Üçüncü cümle?"]

    @pytest.mark.parametrize(
        "text",
        [
            "Dr. Ahmet geldi.",
            "Doz 500 mg. olarak verildi.",
            "Bunlar vb. durumlardır.",
            "M. Ali Bey geldi.",
        ],
    )
    def test_does_not_split_on_abbreviations_or_initials(self, text):
        assert len(split_sentences(text)) == 1

    def test_no_boundary_returns_whole_text(self):
        assert split_sentences("tek parça metin") == ["tek parça metin"]


class TestChunkArticle:
    def test_short_article_is_one_chunk(self, tok):
        text = " ".join(f"kelime{i}" for i in range(50))
        chunks = chunk_article(text, tok, target_tokens=100, overlap_tokens=10, min_tokens=5)
        assert len(chunks) == 1
        assert chunks[0].index == 0

    def test_respects_the_token_budget(self, tok):
        paragraphs = ["\n".join([" ".join(f"w{i}" for i in range(40))] * 1) for _ in range(20)]
        text = "\n".join(paragraphs)
        chunks = chunk_article(text, tok, target_tokens=100, overlap_tokens=0, min_tokens=1)
        assert len(chunks) > 1
        # Joining adds separators, so allow a small margin over the target.
        assert all(c.token_count <= 120 for c in chunks)

    def test_single_newlines_are_paragraph_boundaries(self, tok):
        """The corpus separates paragraphs with one newline, not a blank line."""
        text = "\n".join(" ".join(f"p{p}w{i}" for i in range(30)) for p in range(10))
        chunks = chunk_article(text, tok, target_tokens=60, overlap_tokens=0, min_tokens=1)
        assert len(chunks) > 1

    def test_overlap_repeats_content_between_neighbours(self, tok):
        text = "\n".join(f"paragraf{p} " + " ".join(f"w{i}" for i in range(20)) for p in range(10))
        with_overlap = chunk_article(text, tok, target_tokens=60, overlap_tokens=25, min_tokens=1)
        assert len(with_overlap) >= 2
        first_words = set(with_overlap[0].text.split())
        second_words = set(with_overlap[1].text.split())
        assert first_words & second_words, "ardışık parçalar örtüşmeli"

    def test_oversized_single_sentence_is_hard_split(self, tok):
        text = " ".join(f"w{i}" for i in range(300))  # one sentence, no punctuation
        chunks = chunk_article(text, tok, target_tokens=50, overlap_tokens=0, min_tokens=1)
        assert len(chunks) > 1

    def test_indices_are_sequential_from_zero(self, tok):
        text = "\n".join(" ".join(f"p{p}w{i}" for i in range(30)) for p in range(12))
        chunks = chunk_article(text, tok, target_tokens=60, overlap_tokens=10, min_tokens=1)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_empty_article_yields_nothing(self, tok):
        assert chunk_article("", tok) == []
        assert chunk_article("   \n\n  ", tok) == []
