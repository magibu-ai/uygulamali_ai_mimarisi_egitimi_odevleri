"""Article selection and chunk-record construction.

Selection policy (documented in the README) is deterministic: given the same
dataset revision and seed, the same 1,000 articles come out every time, so the
benchmark numbers and the published vector dataset stay reproducible.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Sequence

import pandas as pd

from .chunking import Chunk, TokenCounter, chunk_article, normalize_text
from .config import (
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    HOSPITAL_SPLITS,
    MIN_ARTICLE_CHARS,
    SOURCE_DATASET_ID,
    TARGET_ARTICLE_COUNT,
)

logger = logging.getLogger(__name__)

SELECTION_SEED = 42

# Scrape boilerplate that occasionally survives extraction. An article whose
# body is mostly one of these is not patient-education content.
_BOILERPLATE_RE = re.compile(
    r"(?:çerez politikas|kvkk|gizlilik politikas|randevu al|online randevu|"
    r"tüm hakları saklıdır|sayfa bulunamad)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChunkRecord:
    """One row of the published vector dataset."""

    chunk_id: str
    parent_id: str
    url: str
    title: str
    source: str
    chunk_index: int
    chunk_text: str
    token_count: int

    def metadata(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source": self.source,
            "parent_id": self.parent_id,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_raw_articles(dataset_id: str = SOURCE_DATASET_ID, token: str | None = None) -> pd.DataFrame:
    """Load every hospital split into one frame with a ``source`` column."""
    from datasets import load_dataset

    dataset = load_dataset(dataset_id, token=token)
    frames: list[pd.DataFrame] = []
    for name in HOSPITAL_SPLITS:
        if name not in dataset:
            logger.warning("Beklenen split bulunamadı: %s", name)
            continue
        frame = dataset[name].to_pandas()[["url", "title", "text"]].copy()
        frame["source"] = name
        frames.append(frame)
    if not frames:
        raise RuntimeError("Kaynak veri kümesinden hiçbir split yüklenemedi.")
    return pd.concat(frames, ignore_index=True)


def clean_articles(df: pd.DataFrame, min_chars: int = MIN_ARTICLE_CHARS) -> pd.DataFrame:
    """Drop unusable rows and exact duplicates.

    The raw dataset carries ~336 empty bodies, ~1.5k repeated URLs and ~2.1k
    byte-identical bodies (the same article republished under several hospital
    paths). Duplicates would inflate retrieval scores and let one article occupy
    several top-k slots, so both are removed before sampling.
    """
    out = df.dropna(subset=["url", "text"]).copy()
    out["url"] = out["url"].astype(str).str.strip()
    out["title"] = out["title"].fillna("").astype(str).str.strip()
    out["text"] = out["text"].astype(str).map(normalize_text)

    out = out[out["url"].str.startswith("http")]
    out = out[out["text"].str.len() >= min_chars]

    # An article that is mostly cookie/consent boilerplate carries no answers.
    head = out["text"].str.slice(0, 300)
    out = out[~head.str.contains(_BOILERPLATE_RE, regex=True, na=False)]

    # Deterministic dedup: sort first so "first" is stable across runs.
    out = out.sort_values(["source", "url"], kind="mergesort")
    out = out.drop_duplicates(subset=["url"], keep="first")
    out = out.drop_duplicates(subset=["text"], keep="first")
    return out.reset_index(drop=True)


def select_articles(
    df: pd.DataFrame,
    target: int = TARGET_ARTICLE_COUNT,
    seed: int = SELECTION_SEED,
) -> pd.DataFrame:
    """Sample ``target`` articles, balanced across the 14 hospital sources.

    Rationale: the raw corpus is dominated by two hospitals (Acıbadem 6,071 and
    Memorial 5,264 of ~21k eligible articles). A proportional sample would make
    roughly half the index a single institution's house style and narrow the
    topic spread. An equal quota per source — with any shortfall from a small
    source redistributed to the larger ones — gives wider medical coverage for
    the same 1,000 documents, which is what both the positive and the negative
    benchmark questions depend on.
    """
    sources = [s for s in HOSPITAL_SPLITS if s in set(df["source"])]
    if not sources:
        raise RuntimeError("Seçilebilecek kaynak yok.")

    available = {s: int((df["source"] == s).sum()) for s in sources}
    total_available = sum(available.values())
    if total_available < target:
        logger.warning(
            "Uygun makale sayısı (%s) hedeften (%s) az; tümü kullanılacak.",
            total_available,
            target,
        )
        target = total_available

    quota = {s: 0 for s in sources}
    remaining = target
    open_sources = set(sources)

    # Water-filling: repeatedly hand out an equal share to the sources that can
    # still absorb it, until the budget is spent.
    while remaining > 0 and open_sources:
        share = max(1, remaining // len(open_sources))
        progressed = False
        for source in sorted(open_sources):
            if remaining <= 0:
                break
            capacity = available[source] - quota[source]
            if capacity <= 0:
                open_sources.discard(source)
                continue
            take = min(share, capacity, remaining)
            quota[source] += take
            remaining -= take
            progressed = True
            if quota[source] >= available[source]:
                open_sources.discard(source)
        if not progressed:
            break

    picked: list[pd.DataFrame] = []
    for source in sources:
        n = quota[source]
        if n <= 0:
            continue
        group = df[df["source"] == source].sort_values("url", kind="mergesort")
        picked.append(group.sample(n=n, random_state=seed))

    selected = pd.concat(picked, ignore_index=True)
    return selected.sort_values(["source", "url"], kind="mergesort").reset_index(drop=True)


def parent_id_for(url: str) -> str:
    """Stable article identifier derived from the canonical URL."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def build_chunk_records(
    articles: pd.DataFrame,
    tokenizer: TokenCounter,
    *,
    target_tokens: int = CHUNK_TARGET_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
    min_tokens: int = CHUNK_MIN_TOKENS,
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for row in articles.itertuples(index=False):
        chunks: Sequence[Chunk] = chunk_article(
            row.text,
            tokenizer,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
            min_tokens=min_tokens,
        )
        if not chunks:
            continue
        parent = parent_id_for(row.url)
        for chunk in chunks:
            records.append(
                ChunkRecord(
                    chunk_id=f"{parent}-{chunk.index:04d}",
                    parent_id=parent,
                    url=row.url,
                    title=row.title,
                    source=row.source,
                    chunk_index=chunk.index,
                    chunk_text=chunk.text,
                    token_count=chunk.token_count,
                )
            )
    return records
