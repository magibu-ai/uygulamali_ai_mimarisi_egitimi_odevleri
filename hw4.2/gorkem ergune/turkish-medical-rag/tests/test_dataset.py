"""Phase 1 tests: validation and deterministic selection.

These tests operate on synthetic in-memory documents so they never touch the
network or the Hugging Face Hub, keeping the suite fast and reproducible.
"""
from __future__ import annotations

import pytest

from src.data.selector import (
    compute_length_stats,
    find_valid_and_duplicates,
    select_documents,
)


def make_docs(n: int) -> list[dict]:
    """Build ``n`` distinct valid documents."""
    return [
        {
            "url": f"https://example.com/a/{i}",
            "title": f"Title {i}",
            "text": f"Bu {i}. dokümanın anlamlı Türkçe metnidir. ığşçöü",
            "source": "hospital_a" if i % 2 == 0 else "hospital_b",
        }
        for i in range(n)
    ]


def test_find_valid_filters_empty_and_duplicates():
    docs = make_docs(3)
    docs.append({"url": "u", "title": "t", "text": "   ", "source": "s"})  # empty
    docs.append(dict(docs[0]))  # exact duplicate text
    valid, diag = find_valid_and_duplicates(docs)
    assert len(valid) == 3
    assert diag["empty_text_count"] == 1
    assert diag["duplicate_count"] == 1


def test_missing_metadata_counts():
    docs = [
        {"url": "", "title": "t", "text": "abc", "source": "s"},
        {"url": "u", "title": "", "text": "def", "source": "s"},
    ]
    _, diag = find_valid_and_duplicates(docs)
    assert diag["missing_url_count"] == 1
    assert diag["missing_title_count"] == 1


def test_selection_is_deterministic():
    valid, _ = find_valid_and_duplicates(make_docs(100))
    first = select_documents(valid, seed=42, count=30)
    second = select_documents(valid, seed=42, count=30)
    assert [d["url"] for d in first] == [d["url"] for d in second]
    assert [d["doc_id"] for d in first] == [d["doc_id"] for d in second]


def test_selection_count_and_ids():
    valid, _ = find_valid_and_duplicates(make_docs(100))
    selected = select_documents(valid, seed=42, count=30)
    assert len(selected) == 30
    assert selected[0]["doc_id"] == "doc_00000"
    assert selected[-1]["doc_id"] == "doc_00029"
    assert len({d["doc_id"] for d in selected}) == 30


def test_every_selected_has_nonempty_text():
    valid, _ = find_valid_and_duplicates(make_docs(100))
    selected = select_documents(valid, seed=42, count=30)
    for doc in selected:
        assert doc["text"].strip(), doc


def test_metadata_is_preserved():
    valid, _ = find_valid_and_duplicates(make_docs(100))
    selected = select_documents(valid, seed=42, count=30)
    source_by_url = {d["url"]: d for d in make_docs(100)}
    for doc in selected:
        original = source_by_url[doc["url"]]
        assert doc["title"] == original["title"]
        assert doc["source"] == original["source"]
        assert doc["text"] == original["text"]
        assert set(doc.keys()) == {"doc_id", "url", "title", "source", "text"}


def test_different_seed_changes_selection():
    valid, _ = find_valid_and_duplicates(make_docs(500))
    a = [d["url"] for d in select_documents(valid, seed=42, count=50)]
    b = [d["url"] for d in select_documents(valid, seed=7, count=50)]
    assert a != b


def test_insufficient_pool_raises():
    valid, _ = find_valid_and_duplicates(make_docs(10))
    with pytest.raises(ValueError):
        select_documents(valid, seed=42, count=300)


def test_length_stats_shape():
    stats = compute_length_stats(make_docs(5))
    assert stats["count"] == 5
    assert set(stats["characters"]) == {"min", "max", "mean", "median"}
    assert set(stats["words"]) == {"min", "max", "mean", "median"}
