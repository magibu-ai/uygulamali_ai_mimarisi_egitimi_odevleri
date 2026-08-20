"""Paragraph-first, sentence-aware, token-bounded mixed chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")


class TokenizerLike(Protocol):
    """Small tokenizer surface required by the chunker."""

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]: ...

    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool = True) -> str: ...


@dataclass(frozen=True)
class Chunk:
    """One token-bounded article chunk before storage metadata is attached."""

    chunk_index: int
    chunk_text: str
    token_count: int
    body_token_count: int


class MixedChunker:
    """Preserve source boundaries while enforcing a hard tokenizer limit."""

    def __init__(
        self,
        tokenizer: TokenizerLike,
        *,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        min_chunk_tokens: int = 80,
    ) -> None:
        if target_tokens <= 0:
            raise ValueError("target_tokens must be positive")
        if not 0 <= overlap_tokens < target_tokens:
            raise ValueError("overlap_tokens must be in [0, target_tokens)")
        if not 0 < min_chunk_tokens <= target_tokens:
            raise ValueError("min_chunk_tokens must be in (0, target_tokens]")
        self.tokenizer = tokenizer
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

    def _encode(self, text: str) -> list[int]:
        return list(self.tokenizer.encode(text, add_special_tokens=False))

    def _decode(self, token_ids: Sequence[int]) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True).strip()

    def _split_long_paragraph(self, paragraph: str, max_tokens: int) -> list[list[int]]:
        paragraph_ids = self._encode(paragraph)
        if len(paragraph_ids) <= max_tokens:
            return [paragraph_ids]

        sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
        if len(sentences) <= 1:
            return [paragraph_ids[start : start + max_tokens] for start in range(0, len(paragraph_ids), max_tokens)]

        segments: list[list[int]] = []
        current: list[int] = []
        space_ids = self._encode(" ")
        for sentence in sentences:
            sentence_ids = self._encode(sentence)
            if len(sentence_ids) > max_tokens:
                if current:
                    segments.append(current)
                    current = []
                segments.extend(
                    sentence_ids[start : start + max_tokens]
                    for start in range(0, len(sentence_ids), max_tokens)
                )
                continue
            candidate = current + (space_ids if current else []) + sentence_ids
            if current and len(candidate) > max_tokens:
                segments.append(current)
                current = sentence_ids
            else:
                current = candidate
        if current:
            segments.append(current)
        return segments

    def _units(self, text: str, max_unit_tokens: int) -> list[list[int]]:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
        units: list[list[int]] = []
        for paragraph in paragraphs:
            units.extend(self._split_long_paragraph(paragraph, max_unit_tokens))
        return [unit for unit in units if unit]

    def chunk(self, *, title: str, text: str) -> list[Chunk]:
        """Chunk one article and prepend its title to every resulting chunk."""

        title_prefix = f"Başlık: {title.strip()}\n\n"
        prefix_ids = self._encode(title_prefix)
        body_budget = self.target_tokens - len(prefix_ids)
        if body_budget <= self.overlap_tokens:
            raise ValueError("Article title leaves no room for body text and overlap")

        max_unit_tokens = body_budget - self.overlap_tokens
        units = self._units(text, max_unit_tokens)
        if not units:
            return []

        separator_ids = self._encode("\n\n")
        bodies: list[list[int]] = []
        current: list[int] = []
        for unit in units:
            candidate = current + (separator_ids if current else []) + unit
            if current and len(candidate) > body_budget:
                bodies.append(current)
                carry = current[-self.overlap_tokens :] if self.overlap_tokens else []
                allowed_carry = max(0, body_budget - len(unit) - len(separator_ids))
                carry = carry[-allowed_carry:] if allowed_carry else []
                current = carry + (separator_ids if carry else []) + unit
            else:
                current = candidate
        if current:
            bodies.append(current)

        # Increase overlap for a tiny final chunk instead of emitting a weak
        # fragment. The previous chunk is unchanged, so no source token is lost.
        if len(bodies) > 1 and len(prefix_ids) + len(bodies[-1]) < self.min_chunk_tokens:
            needed = self.min_chunk_tokens - len(prefix_ids) - len(bodies[-1])
            previous = bodies[-2]
            extra_start = max(0, len(previous) - self.overlap_tokens - needed)
            extra = previous[extra_start : len(previous) - self.overlap_tokens]
            bodies[-1] = extra + bodies[-1]

        chunks: list[Chunk] = []
        for index, body_ids in enumerate(bodies):
            body_text = self._decode(body_ids)
            chunk_text = f"{title_prefix}{body_text}".strip()
            token_count = len(self._encode(chunk_text))
            if token_count > self.target_tokens:
                raise RuntimeError(
                    f"Chunk {index} has {token_count} tokens, exceeding {self.target_tokens}"
                )
            chunks.append(
                Chunk(
                    chunk_index=index,
                    chunk_text=chunk_text,
                    token_count=token_count,
                    body_token_count=len(body_ids),
                )
            )
        return chunks


def chunk_articles(table: Any, chunker: MixedChunker) -> list[dict[str, Any]]:
    """Convert selected article rows into storage-ready chunk dictionaries."""

    chunks: list[dict[str, Any]] = []
    for article in table.to_pylist():
        article_chunks = chunker.chunk(title=article["title"], text=article["text"])
        for chunk in article_chunks:
            chunks.append(
                {
                    "chunk_id": f"{article['parent_id']}_chunk_{chunk.chunk_index:04d}",
                    "parent_id": article["parent_id"],
                    "url": article["url"],
                    "title": article["title"],
                    "branch": article["branch"],
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "chunk_text": chunk.chunk_text,
                }
            )
    return chunks

