#!/usr/bin/env python3
"""Validate benchmark evidence and materialize calibration/test JSONL files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize(value: str) -> str:
    return " ".join(value.casefold().replace("\u0307", "").split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--draft", type=Path, default=PROJECT_ROOT / "data/benchmark/benchmark_drafts.json"
    )
    parser.add_argument(
        "--chunks", type=Path, default=PROJECT_ROOT / "data/processed/chunks.parquet"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "data/benchmark"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports/metrics/benchmark_validation.json",
    )
    return parser.parse_args()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    drafts = json.loads(args.draft.read_text(encoding="utf-8"))
    chunks = pq.read_table(args.chunks).to_pylist()
    by_id = {row["chunk_id"]: row for row in chunks}
    corpus = normalize("\n".join(row["chunk_text"] for row in chunks))

    ids = [row["question_id"] for row in drafts]
    if len(ids) != len(set(ids)):
        raise ValueError("question_id values must be unique")

    materialized: list[dict[str, Any]] = []
    absent_checks: dict[str, dict[str, int]] = {}
    for draft in drafts:
        row = dict(draft)
        if row["is_answerable"]:
            evidence = by_id.get(row["expected_chunk_id"])
            if evidence is None:
                raise ValueError(f"Missing evidence chunk for {row['question_id']}")
            evidence_text = normalize(evidence["chunk_text"])
            missing_terms = [term for term in row["evidence_terms"] if normalize(term) not in evidence_text]
            if missing_terms:
                raise ValueError(f"Evidence terms missing for {row['question_id']}: {missing_terms}")
            row.update(
                {
                    "expected_parent_id": evidence["parent_id"],
                    "source_url": evidence["url"],
                    "source_title": evidence["title"],
                    "verification": "evidence_terms_present_in_expected_chunk",
                }
            )
        else:
            counts = {term: corpus.count(normalize(term)) for term in row["absence_terms"]}
            if any(counts.values()):
                raise ValueError(f"Negative evidence term found for {row['question_id']}: {counts}")
            absent_checks[row["question_id"]] = counts
            row.update(
                {
                    "expected_chunk_id": None,
                    "expected_parent_id": None,
                    "source_url": None,
                    "source_title": None,
                    "verification": "absence_terms_zero_occurrences_in_corpus",
                }
            )
        materialized.append(row)

    calibration = [row for row in materialized if row["split"] == "calibration"]
    test = [row for row in materialized if row["split"] == "test"]
    counts = Counter((row["split"], row["is_answerable"]) for row in materialized)
    expected_counts = {
        ("calibration", True): 10,
        ("calibration", False): 10,
        ("test", True): 20,
        ("test", False): 10,
    }
    if counts != expected_counts:
        raise ValueError(f"Unexpected benchmark distribution: {counts}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "calibration.jsonl", calibration)
    write_jsonl(args.output_dir / "test.jsonl", test)
    report = {
        "corpus_chunks": len(chunks),
        "total_questions": len(materialized),
        "calibration": {"positive": 10, "negative": 10},
        "test": {"positive": 20, "negative": 10},
        "unique_positive_evidence_chunks": len(
            {row["expected_chunk_id"] for row in materialized if row["is_answerable"]}
        ),
        "negative_absence_checks": absent_checks,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Calibration questions: {len(calibration)}")
    print(f"Test questions: {len(test)}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()

