"""Phase 2 tests: deterministic chunking behaviour and integrity."""
from __future__ import annotations

import pytest

from src.data.chunker import (
    chunk_document,
    chunk_text,
    split_paragraphs,
    token_fallback,
)
from src.tokenizer import Tokenizer

TOKENIZER = Tokenizer(backend="tiktoken", encoding="cl100k_base")

# Small, explicit parameters so behaviour is easy to reason about in tests.
MAX = 40
OVERLAP = 8
MIN = 5


def _tok(text: str) -> int:
    return TOKENIZER.count(text)


def test_split_paragraphs_on_newlines():
    text = "Birinci satır\nİkinci satır\n\nÜçüncü satır"
    assert split_paragraphs(text) == [
        "Birinci satır",
        "İkinci satır",
        "Üçüncü satır",
    ]


def test_split_paragraphs_single_block():
    assert split_paragraphs("Tek bir paragraf.") == ["Tek bir paragraf."]


def test_paragraph_grouping_respects_max_tokens():
    # Many short lines should be grouped, each chunk <= MAX tokens.
    text = "\n".join(f"Kısa satır numarası {i}" for i in range(40))
    chunks = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    assert len(chunks) > 1
    for c in chunks:
        assert _tok(c) <= MAX


def test_token_fallback_splits_oversized_unit():
    long_unit = " ".join(f"kelime{i}" for i in range(300))
    parts = token_fallback(long_unit, MAX, OVERLAP, TOKENIZER)
    assert len(parts) > 1
    for p in parts:
        assert _tok(p) <= MAX
        assert p.strip()


def test_token_fallback_applies_overlap():
    long_unit = " ".join(f"kelime{i}" for i in range(300))
    parts = token_fallback(long_unit, MAX, OVERLAP, TOKENIZER)
    # Consecutive fallback chunks should share trailing/leading words (overlap).
    first_tail = parts[0].split()[-1]
    assert first_tail in parts[1].split()


def test_no_text_is_lost_in_fallback():
    long_unit = " ".join(f"kelime{i}" for i in range(300))
    parts = token_fallback(long_unit, MAX, OVERLAP, TOKENIZER)
    covered = set()
    for p in parts:
        covered.update(p.split())
    assert set(long_unit.split()) <= covered


def test_deterministic_output():
    text = "\n".join(f"Satır {i} biraz daha uzun metin içerir" for i in range(50))
    a = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    b = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    assert a == b


def test_no_empty_chunks():
    text = "\n".join(f"Satır {i}" for i in range(60))
    chunks = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    assert all(c.strip() for c in chunks)


def test_every_document_produces_at_least_one_chunk():
    for text in ["kısa", "Tek satır.", "a\nb\nc", "x " * 500]:
        chunks = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
        assert len(chunks) >= 1


def test_min_tokens_no_tiny_chunks_when_multiple():
    text = "\n".join(f"Satır {i} yeterince uzun bir metin parçası" for i in range(30))
    chunks = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    if len(chunks) > 1:
        assert all(_tok(c) >= MIN for c in chunks)


def test_metadata_preservation_and_ids():
    doc = {
        "doc_id": "doc_00007",
        "url": "https://example.com/x",
        "title": "Başlık",
        "source": "acibadem",
        "text": "\n".join(f"Satır {i} biraz metin" for i in range(40)),
    }
    records = chunk_document(doc, TOKENIZER, MAX, OVERLAP, MIN)
    assert len(records) >= 1
    for i, r in enumerate(records):
        assert r["chunk_id"] == f"doc_00007_chunk_{i:03d}"
        assert r["parent_id"] == "doc_00007"
        assert r["url"] == doc["url"]
        assert r["title"] == doc["title"]
        assert r["source"] == "acibadem"
        assert r["chunk_text"].strip()
        assert set(r.keys()) == {
            "chunk_id", "parent_id", "url", "title", "source",
            "chunk_text", "token_count",
        }


def test_turkish_utf8_preserved_across_chunks():
    # Oversized Turkish paragraph forced through the token fallback.
    turkish = ("Bağışıklık sistemi kırmızı kan hücrelerini üretir. "
               "Şeker ölçümü ığşçöü İĞŞÇÖÜ ") * 60
    doc = {
        "doc_id": "doc_00000",
        "url": "u",
        "title": "t",
        "source": "s",
        "text": turkish,
    }
    records = chunk_document(doc, TOKENIZER, MAX, OVERLAP, MIN)
    joined = " ".join(r["chunk_text"] for r in records)
    assert "�" not in joined  # no replacement characters
    for needle in ["Bağışıklık", "kırmızı", "hücrelerini", "ığşçöü", "İĞŞÇÖÜ"]:
        assert needle in joined


def test_chunk_token_limits_documentwide():
    # After chunking, no chunk should exceed MAX except deliberately-merged mins.
    text = "\n".join(f"Satır {i} orta uzunlukta bir cümle içeriyor" for i in range(80))
    chunks = chunk_text(text, TOKENIZER, MAX, OVERLAP, MIN)
    # Allow a small tolerance only for min-merge; core grouping stays <= MAX.
    assert max(_tok(c) for c in chunks) <= MAX + MIN
