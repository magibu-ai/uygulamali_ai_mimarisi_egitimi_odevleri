"""Paragraph/sentence-aware, token-budgeted chunking with overlap.

Strategy (a.k.a. "mixed" chunking):
  1. Normalise whitespace and split the article on blank lines into paragraphs.
  2. Split each paragraph into sentences (Turkish-aware regex).
  3. Greedily pack sentences into chunks up to ``max_tokens`` (measured with the
     *embedding model's own tokenizer*, so the budget matches what the encoder
     actually sees).
  4. Start each new chunk with a trailing overlap (~``overlap_tokens``) carried
     over from the previous chunk, so facts spanning a boundary stay retrievable.

This respects natural language boundaries (never cuts mid-sentence) while
keeping every chunk within a retrieval-friendly size window.
"""
import re
from typing import Callable, List

# Split on sentence-final punctuation followed by whitespace + an uppercase /
# digit start. Turkish uppercase letters (incl. İ, Ş, Ğ, Ü, Ö, Ç) are included.
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÇĞİÖŞÜ0-9])")
_WS = re.compile(r"[ \t]+")
_MULTINL = re.compile(r"\n{2,}")


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS.sub(" ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text.strip()


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in _MULTINL.split(text) if p.strip()]


def _sentences(paragraph: str) -> List[str]:
    parts = _SENT_SPLIT.split(paragraph)
    return [s.strip() for s in parts if s.strip()]


def _segments(text: str) -> List[str]:
    """Flat list of sentence-level segments across all paragraphs."""
    segs: List[str] = []
    for para in _paragraphs(text):
        segs.extend(_sentences(para))
    return segs


def chunk_text(
    text: str,
    count_tokens: Callable[[str], int],
    max_tokens: int = 384,
    overlap_tokens: int = 64,
    min_tokens: int = 24,
) -> List[str]:
    """Split ``text`` into overlapping, token-budgeted chunks.

    ``count_tokens`` maps a string to its token count using the embedding
    model's tokenizer. Returns a list of chunk strings.
    """
    text = _normalise(text)
    if not text:
        return []

    segments = _segments(text)
    if not segments:
        return []

    # Pre-compute token counts once.
    seg_tokens = [count_tokens(s) for s in segments]

    chunks: List[str] = []
    cur: List[str] = []
    cur_tok = 0

    def flush():
        nonlocal cur, cur_tok
        if cur and cur_tok >= min_tokens:
            chunks.append(" ".join(cur))
        elif cur and chunks:
            # too-small tail: glue onto the previous chunk instead of dropping.
            chunks[-1] = chunks[-1] + " " + " ".join(cur)
        cur, cur_tok = [], 0

    i = 0
    n = len(segments)
    while i < n:
        seg, tok = segments[i], seg_tokens[i]

        # A single sentence longer than the budget: hard-wrap it on word bounds.
        if tok > max_tokens:
            flush()
            for piece in _hardwrap(seg, count_tokens, max_tokens):
                chunks.append(piece)
            i += 1
            continue

        if cur_tok + tok <= max_tokens:
            cur.append(seg)
            cur_tok += tok
            i += 1
        else:
            flush()
            # Build overlap: carry trailing sentences (up to overlap_tokens)
            # from the segments we just emitted into the start of the new chunk.
            back, back_tok = [], 0
            k = i - 1
            while k >= 0 and back_tok < overlap_tokens:
                back.insert(0, segments[k])
                back_tok += seg_tokens[k]
                k -= 1
            # Trim the overlap from the front until segment i fits, so the loop
            # always makes progress (seg tok <= max_tokens is guaranteed above).
            while back and back_tok + tok > max_tokens:
                back_tok -= seg_tokens[i - len(back)]
                back.pop(0)
            cur = list(back)
            cur_tok = back_tok

    flush()
    return chunks


def _hardwrap(sentence: str, count_tokens: Callable[[str], int], max_tokens: int) -> List[str]:
    """Split an over-long sentence into <=max_tokens pieces on word boundaries."""
    words = sentence.split(" ")
    out, cur, cur_tok = [], [], 0
    for w in words:
        wt = count_tokens(w) or 1
        if cur and cur_tok + wt > max_tokens:
            out.append(" ".join(cur))
            cur, cur_tok = [], 0
        cur.append(w)
        cur_tok += wt
    if cur:
        out.append(" ".join(cur))
    return out
