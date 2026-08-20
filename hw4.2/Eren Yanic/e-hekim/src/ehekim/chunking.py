"""Hybrid paragraph-aware, token-bounded chunking with overlap.

Why this strategy
-----------------
The corpus is scraped hospital patient-education prose: short titled sections,
each a handful of paragraphs ("Belirtileri nelerdir?", "Nasıl tedavi edilir?").
Two properties follow from that shape:

* Paragraph boundaries are real semantic boundaries. Cutting blindly every N
  tokens routinely splits a symptom list away from the condition it belongs to,
  which is exactly the failure mode that produces confidently wrong retrieval.
* Paragraph *lengths* are wildly uneven — one-line intros next to 900-token
  procedure descriptions. Pure ``\\n\\n`` splitting therefore yields chunks that
  are both too small to be self-contained and too large to be precise.

So the chunker packs whole paragraphs greedily into a token budget, recursively
splits any paragraph that overflows the budget on sentence boundaries (and, as a
last resort, on a hard token window), and carries a fixed token overlap across
chunk boundaries so that a fact straddling a cut is still fully present in one
of the two neighbours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence


class TokenCounter(Protocol):
    """Minimal tokenizer surface the chunker needs."""

    def encode(self, text: str, add_special_tokens: bool = ...) -> Sequence[int]: ...

    def decode(self, ids: Sequence[int], skip_special_tokens: bool = ...) -> str: ...


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    token_count: int


# The scraper emits one paragraph per line: only ~35% of the corpus contains
# blank lines at all, and articles average ~44 single newlines. Splitting on a
# blank line alone would therefore treat two thirds of the corpus as one giant
# paragraph. Any run of newlines is a paragraph boundary here.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n+")
_WHITESPACE_RUN_RE = re.compile(r"[ \t ]+")
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")

# Turkish abbreviations that end in a period but do not end a sentence.
_ABBREVIATIONS = (
    "Dr", "Doç", "Prof", "Op", "Uzm", "Yrd", "Sn", "Av", "Bkz", "bkz",
    "vb", "vs", "örn", "yy", "No", "Nu", "Mah", "Cad", "Sok", "Apt",
    "Tel", "Fak", "St", "mg", "ml", "gr", "cm", "mm", "yak", "haz",
)
_ABBREV_SET = {a.lower() for a in _ABBREVIATIONS}

# A candidate sentence boundary: terminal punctuation, an optional closing
# quote/bracket, whitespace, and a following character that can start a new
# sentence. Python's `re` only supports fixed-width lookbehind, so the
# "is the preceding token an abbreviation?" test is done in code rather than in
# the pattern (see `split_sentences`).
_BOUNDARY_RE = re.compile(r"[.!?…]+[\"'”’)\]]?\s+(?=[\"'“(\[]?[A-ZÇĞİÖŞÜ0-9•\-])")

# The last alphabetic word before the punctuation, Turkish letters included.
_TRAILING_WORD_RE = re.compile(r"([^\W\d_]+)$", re.UNICODE)


def normalize_text(text: str) -> str:
    """Collapse scrape artefacts while preserving paragraph structure."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _EXCESS_NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences, Turkish abbreviations respected.

    A candidate boundary is rejected when the word immediately before the
    punctuation is a known abbreviation ("Dr.", "vb.", "mg.") or a single
    capital letter used as an initial ("M. Ali").
    """
    sentences: list[str] = []
    start = 0
    for match in _BOUNDARY_RE.finditer(paragraph):
        preceding = paragraph[start : match.start()]
        word_match = _TRAILING_WORD_RE.search(preceding)
        if word_match:
            word = word_match.group(1)
            if word.lower() in _ABBREV_SET or (len(word) == 1 and word.isupper()):
                continue
        piece = paragraph[start : match.end()].strip()
        if piece:
            sentences.append(piece)
        start = match.end()

    tail = paragraph[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _token_len(tokenizer: TokenCounter, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def _hard_split(tokenizer: TokenCounter, text: str, max_tokens: int) -> list[str]:
    """Last-resort split of a single oversized sentence on a token window."""
    ids = list(tokenizer.encode(text, add_special_tokens=False))
    pieces: list[str] = []
    for start in range(0, len(ids), max_tokens):
        piece = tokenizer.decode(ids[start : start + max_tokens], skip_special_tokens=True).strip()
        if piece:
            pieces.append(piece)
    return pieces or [text]


def _to_units(tokenizer: TokenCounter, text: str, max_tokens: int) -> list[tuple[str, int]]:
    """Break ``text`` into atomic (unit, token_count) pairs no larger than the budget.

    A unit is a whole paragraph where possible, a sentence where a paragraph
    overflows, and a token window only when a single sentence overflows.
    """
    units: list[tuple[str, int]] = []
    for paragraph in _PARAGRAPH_SPLIT_RE.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        n = _token_len(tokenizer, paragraph)
        if n <= max_tokens:
            units.append((paragraph, n))
            continue

        for sentence in split_sentences(paragraph):
            m = _token_len(tokenizer, sentence)
            if m <= max_tokens:
                units.append((sentence, m))
            else:
                for piece in _hard_split(tokenizer, sentence, max_tokens):
                    units.append((piece, _token_len(tokenizer, piece)))
    return units


def _overlap_tail(units: Sequence[tuple[str, int]], overlap_tokens: int) -> list[tuple[str, int]]:
    """Take whole trailing units from a finished chunk, up to the overlap budget."""
    if overlap_tokens <= 0:
        return []
    tail: list[tuple[str, int]] = []
    total = 0
    for unit in reversed(units):
        # Never let the overlap alone fill the next chunk.
        if total + unit[1] > overlap_tokens:
            break
        tail.insert(0, unit)
        total += unit[1]
    return tail


def chunk_article(
    text: str,
    tokenizer: TokenCounter,
    *,
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    min_tokens: int = 32,
) -> list[Chunk]:
    """Chunk one article. Returns chunks in reading order, re-indexed from 0."""
    normalized = normalize_text(text)
    if not normalized:
        return []

    units = _to_units(tokenizer, normalized, target_tokens)
    if not units:
        return []

    raw_chunks: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_tokens = 0

    for unit, n in units:
        if current and current_tokens + n > target_tokens:
            raw_chunks.append(current)
            current = _overlap_tail(current, overlap_tokens)
            current_tokens = sum(t for _, t in current)
        current.append((unit, n))
        current_tokens += n

    if current:
        raw_chunks.append(current)

    chunks: list[Chunk] = []
    for parts in raw_chunks:
        body = "\n\n".join(p for p, _ in parts).strip()
        if not body:
            continue
        n_tokens = _token_len(tokenizer, body)
        if n_tokens < min_tokens and chunks:
            # A trailing sliver carries no independent meaning; fold it back.
            continue
        chunks.append(Chunk(text=body, index=len(chunks), token_count=n_tokens))

    # An article whose entire body is below min_tokens yields nothing useful.
    if len(chunks) == 1 and chunks[0].token_count < min_tokens:
        return []
    return chunks
