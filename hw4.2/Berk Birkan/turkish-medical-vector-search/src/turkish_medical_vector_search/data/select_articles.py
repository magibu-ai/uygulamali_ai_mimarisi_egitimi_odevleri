"""Select a clean, reproducible branch-specific article sample."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

REQUIRED_COLUMNS = {"url", "title", "text", "name", "branch", "publish_date"}
WHITESPACE_PATTERN = re.compile(r"\s+")
INLINE_WHITESPACE_PATTERN = re.compile(r"[^\S\r\n]+")


@dataclass(frozen=True)
class SelectionStats:
    """Auditable counts produced by the article selection pipeline."""

    source_rows: int
    branch_rows: int
    rejected_missing_required: int
    rejected_short_text: int
    rejected_duplicate_url: int
    rejected_duplicate_text: int
    eligible_rows: int
    selected_rows: int
    branch_label: str
    sample_size: int
    seed: int
    min_text_length: int


def normalize_text(value: str | None) -> str:
    """Trim and collapse whitespace without otherwise changing article content."""

    return WHITESPACE_PATTERN.sub(" ", value or "").strip()


def clean_article_text(value: str | None) -> str:
    """Normalize inline spacing while retaining source line boundaries."""

    normalized_newlines = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [INLINE_WHITESPACE_PATTERN.sub(" ", line).strip() for line in normalized_newlines.split("\n")]
    return "\n".join(line for line in lines if line)


def normalize_label(value: str | None) -> str:
    """Normalize a categorical label for case-insensitive exact matching."""

    # Unicode casefold maps Turkish capital İ to ``i`` + COMBINING DOT ABOVE.
    # Removing that combining dot makes labels stable across common Turkish
    # capitalization variants without otherwise transliterating the text.
    return normalize_text(value).casefold().replace("\u0307", "")


def stable_parent_id(url: str) -> str:
    """Create a stable article identifier from its canonical source URL."""

    return f"article_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"


def _validate_schema(table: pa.Table) -> None:
    missing = REQUIRED_COLUMNS.difference(table.column_names)
    if missing:
        raise ValueError(f"Source dataset is missing required columns: {sorted(missing)}")


def select_articles(
    source_path: str | Path,
    output_path: str | Path,
    *,
    branch_label: str,
    sample_size: int,
    seed: int,
    min_text_length: int,
) -> SelectionStats:
    """Filter, deduplicate, sample, and persist articles as Parquet."""

    source_path = Path(source_path)
    output_path = Path(output_path)
    table = pq.read_table(source_path)
    _validate_schema(table)

    target_label = normalize_label(branch_label)
    branch_rows: list[dict[str, Any]] = []
    for row in table.to_pylist():
        if normalize_label(row.get("branch")) == target_label:
            branch_rows.append(row)

    rejected_missing_required = 0
    rejected_short_text = 0
    rejected_duplicate_url = 0
    rejected_duplicate_text = 0
    seen_urls: set[str] = set()
    seen_text_hashes: set[str] = set()
    eligible: list[dict[str, Any]] = []

    # Sorting makes the same seed stable even if Parquet row-group ordering changes.
    for row in sorted(branch_rows, key=lambda item: normalize_text(item.get("url"))):
        url = normalize_text(row.get("url"))
        title = normalize_text(row.get("title"))
        text = clean_article_text(row.get("text"))
        if not url or not title or not text:
            rejected_missing_required += 1
            continue
        if len(text) < min_text_length:
            rejected_short_text += 1
            continue
        normalized_url = url.casefold().rstrip("/")
        if normalized_url in seen_urls:
            rejected_duplicate_url += 1
            continue
        text_hash = hashlib.sha256(normalize_text(text).casefold().encode("utf-8")).hexdigest()
        if text_hash in seen_text_hashes:
            rejected_duplicate_text += 1
            continue

        seen_urls.add(normalized_url)
        seen_text_hashes.add(text_hash)
        eligible.append(
            {
                "parent_id": stable_parent_id(url),
                "url": url,
                "title": title,
                "text": text,
                "name": normalize_text(row.get("name")),
                "branch": normalize_text(row.get("branch")),
                "publish_date": normalize_text(row.get("publish_date")),
            }
        )

    if len(eligible) < sample_size:
        raise ValueError(
            f"Requested {sample_size} articles but only {len(eligible)} eligible rows remain"
        )

    selected = random.Random(seed).sample(eligible, sample_size)
    for rank, row in enumerate(selected):
        row["selection_rank"] = rank

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(selected), output_path, compression="zstd")

    return SelectionStats(
        source_rows=table.num_rows,
        branch_rows=len(branch_rows),
        rejected_missing_required=rejected_missing_required,
        rejected_short_text=rejected_short_text,
        rejected_duplicate_url=rejected_duplicate_url,
        rejected_duplicate_text=rejected_duplicate_text,
        eligible_rows=len(eligible),
        selected_rows=len(selected),
        branch_label=branch_label,
        sample_size=sample_size,
        seed=seed,
        min_text_length=min_text_length,
    )


def write_selection_report(
    stats: SelectionStats,
    report_path: str | Path,
    *,
    source_repo: str,
    source_file: str,
) -> None:
    """Write a small JSON audit report without embedding local filesystem paths."""

    payload = {
        "source_repo": source_repo,
        "source_file": source_file,
        "selection": asdict(stats),
    }
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def branch_counts(source_path: str | Path) -> Counter[str]:
    """Return normalized non-empty branch counts for exploratory reporting."""

    table = pq.read_table(source_path, columns=["branch"])
    return Counter(
        normalize_text(value)
        for value in table.column("branch").to_pylist()
        if normalize_text(value)
    )
