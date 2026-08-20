"""Document validation and deterministic selection (Phase 1).

Pure, network-free functions so they can be unit-tested without touching the
Hugging Face Hub. The selection is fully reproducible: given the same input
documents, seed, and count, it always returns the same documents in the same
order with the same ``doc_id`` assignment.
"""
from __future__ import annotations

import random
from statistics import mean, median
from typing import Any


def find_valid_and_duplicates(
    documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Split documents into a valid, de-duplicated pool plus diagnostics.

    A document is *valid* when its ``text`` is non-empty after stripping.
    Duplicates are detected by exact stripped-text equality; the first
    occurrence (in input order) is kept.

    Returns ``(valid_unique, diagnostics)`` where diagnostics counts are over
    the full input set.
    """
    valid: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    empty_text = 0
    duplicates = 0
    missing_url = 0
    missing_title = 0

    for doc in documents:
        text = (doc.get("text") or "").strip()
        if not (doc.get("url") or "").strip():
            missing_url += 1
        if not (doc.get("title") or "").strip():
            missing_title += 1
        if not text:
            empty_text += 1
            continue
        if text in seen_text:
            duplicates += 1
            continue
        seen_text.add(text)
        valid.append(doc)

    diagnostics = {
        "empty_text_count": empty_text,
        "duplicate_count": duplicates,
        "missing_url_count": missing_url,
        "missing_title_count": missing_title,
    }
    return valid, diagnostics


def select_documents(
    valid_documents: list[dict[str, Any]],
    seed: int,
    count: int,
) -> list[dict[str, str]]:
    """Deterministically select ``count`` documents from a valid pool.

    The pool is first sorted by a stable key (``url`` then ``text``) so the
    result is independent of the input ordering, then sampled with a seeded RNG.
    Each selected document is projected onto the required schema and assigned a
    sequential ``doc_id``.

    Raises ``ValueError`` if fewer than ``count`` valid documents are available
    (rather than silently returning a smaller set).
    """
    available = len(valid_documents)
    if available < count:
        raise ValueError(
            f"Only {available} valid unique documents available; "
            f"need {count}. Refusing to silently change the requirement."
        )

    pool = sorted(
        valid_documents,
        key=lambda d: ((d.get("url") or ""), (d.get("text") or "")),
    )
    rng = random.Random(seed)
    chosen_indices = sorted(rng.sample(range(len(pool)), count))

    selected: list[dict[str, str]] = []
    for new_index, pool_index in enumerate(chosen_indices):
        source_doc = pool[pool_index]
        selected.append(
            {
                "doc_id": f"doc_{new_index:05d}",
                "url": source_doc.get("url", ""),
                "title": source_doc.get("title", ""),
                "source": source_doc.get("source", ""),
                "text": source_doc.get("text", ""),
            }
        )
    return selected


def compute_length_stats(
    documents: list[dict[str, Any]], field: str = "text"
) -> dict[str, Any]:
    """Compute character- and word-length statistics over a document set."""
    if not documents:
        return {"count": 0}
    char_lengths = [len(doc.get(field, "")) for doc in documents]
    word_lengths = [len((doc.get(field, "") or "").split()) for doc in documents]
    return {
        "count": len(documents),
        "characters": {
            "min": min(char_lengths),
            "max": max(char_lengths),
            "mean": round(mean(char_lengths), 2),
            "median": round(median(char_lengths), 2),
        },
        "words": {
            "min": min(word_lengths),
            "max": max(word_lengths),
            "mean": round(mean(word_lengths), 2),
            "median": round(median(word_lengths), 2),
        },
    }
