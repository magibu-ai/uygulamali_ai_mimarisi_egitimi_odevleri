"""Deterministic chunking (Phase 2).

Strategy (``paragraph_then_token``):

1. Split a document into paragraph units on newline boundaries.
2. Greedily group consecutive units until ``max_tokens`` is reached.
3. If a single unit alone exceeds ``max_tokens``, split it with a token-measured
   WORD-boundary window fallback that applies ``overlap_tokens`` overlap. Word
   boundaries are used (instead of raw token-id slicing) so that multi-byte
   Turkish characters are never split, preserving UTF-8 exactly.
4. Merge any chunk below ``min_tokens`` into a neighbour so no tiny chunks and
   no empty chunks are produced, and no source text is discarded.

All functions are deterministic and network-free (the tokenizer is injected),
so they are cheap to unit-test.
"""
from __future__ import annotations

import re
from typing import Any

from src.tokenizer import Tokenizer

# Paragraph unit = maximal run of text between one or more newlines.
_NEWLINE_SPLIT = re.compile(r"\n+")


def split_paragraphs(text: str) -> list[str]:
    """Split document text into non-empty paragraph units."""
    units = [u.strip() for u in _NEWLINE_SPLIT.split(text.strip())]
    units = [u for u in units if u]
    if not units and text.strip():
        units = [text.strip()]
    return units


def _overlap_suffix(
    words: list[str], overlap_tokens: int, tokenizer: Tokenizer
) -> list[str]:
    """Smallest suffix of ``words`` whose token count reaches ``overlap_tokens``.

    Never returns the entire list, so the caller can always make progress.
    """
    if overlap_tokens <= 0 or len(words) <= 1:
        return []
    suffix: list[str] = []
    for word in reversed(words[1:]):  # never carry the whole chunk
        suffix.insert(0, word)
        if tokenizer.count(" ".join(suffix)) >= overlap_tokens:
            break
    return suffix


def token_fallback(
    unit: str, max_tokens: int, overlap_tokens: int, tokenizer: Tokenizer
) -> list[str]:
    """Split an oversized unit into <= max_tokens windows on word boundaries."""
    words = unit.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        if current and tokenizer.count(" ".join(current + [word])) > max_tokens:
            chunks.append(" ".join(current))
            carry = _overlap_suffix(current, overlap_tokens, tokenizer)
            current = carry + [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _enforce_min_tokens(
    chunks: list[str], min_tokens: int, tokenizer: Tokenizer
) -> list[str]:
    """Merge any chunk below ``min_tokens`` into a neighbour (deterministic)."""
    chunks = list(chunks)
    while len(chunks) > 1:
        idx = next(
            (i for i, c in enumerate(chunks) if tokenizer.count(c) < min_tokens),
            None,
        )
        if idx is None:
            break
        if idx > 0:
            chunks[idx - 1] = chunks[idx - 1] + "\n" + chunks[idx]
            del chunks[idx]
        else:
            chunks[1] = chunks[0] + "\n" + chunks[1]
            del chunks[0]
    return chunks


def chunk_text(
    text: str,
    tokenizer: Tokenizer,
    max_tokens: int,
    overlap_tokens: int,
    min_tokens: int,
) -> list[str]:
    """Chunk a single document's text into a list of non-empty chunk strings."""
    units = split_paragraphs(text)
    chunks: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            chunks.append("\n".join(buffer))
            buffer = []

    for unit in units:
        # A unit that alone exceeds the limit goes to the token fallback.
        if tokenizer.count(unit) > max_tokens:
            flush()
            chunks.extend(
                token_fallback(unit, max_tokens, overlap_tokens, tokenizer)
            )
            continue
        # Otherwise grow the current group only while the *joined* chunk text
        # (including newline separators) stays within the limit.
        if buffer and tokenizer.count("\n".join(buffer + [unit])) > max_tokens:
            flush()
        buffer.append(unit)
    flush()

    return _enforce_min_tokens(chunks, min_tokens, tokenizer)


def chunk_document(
    document: dict[str, Any],
    tokenizer: Tokenizer,
    max_tokens: int,
    overlap_tokens: int,
    min_tokens: int,
) -> list[dict[str, Any]]:
    """Chunk one selected document into schema-complete chunk records."""
    pieces = chunk_text(
        document["text"], tokenizer, max_tokens, overlap_tokens, min_tokens
    )
    parent_id = document["doc_id"]
    records: list[dict[str, Any]] = []
    for index, piece in enumerate(pieces):
        records.append(
            {
                "chunk_id": f"{parent_id}_chunk_{index:03d}",
                "parent_id": parent_id,
                "url": document.get("url", ""),
                "title": document.get("title", ""),
                "source": document.get("source", ""),
                "chunk_text": piece,
                "token_count": tokenizer.count(piece),
            }
        )
    return records


def chunk_documents(
    documents: list[dict[str, Any]],
    tokenizer: Tokenizer,
    max_tokens: int,
    overlap_tokens: int,
    min_tokens: int,
) -> list[dict[str, Any]]:
    """Chunk every document, preserving order."""
    all_chunks: list[dict[str, Any]] = []
    for document in documents:
        all_chunks.extend(
            chunk_document(
                document, tokenizer, max_tokens, overlap_tokens, min_tokens
            )
        )
    return all_chunks
