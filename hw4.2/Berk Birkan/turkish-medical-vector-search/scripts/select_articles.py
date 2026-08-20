#!/usr/bin/env python3
"""CLI for deterministic dermatology article selection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.config import load_config  # noqa: E402
from turkish_medical_vector_search.data.select_articles import (  # noqa: E402
    select_articles,
    write_selection_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data/raw/doktorsitesi_articles.parquet",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data/interim/selected_articles.parquet",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports/metrics/selection_summary.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    stats = select_articles(
        args.source,
        args.output,
        branch_label=config.dataset.branch_query,
        sample_size=config.dataset.sample_size,
        seed=config.project.seed,
        min_text_length=config.dataset.min_text_length,
    )
    write_selection_report(
        stats,
        args.report,
        source_repo=config.dataset.repo_id,
        source_file=args.source.name,
    )
    print(f"Selected {stats.selected_rows} of {stats.eligible_rows} eligible articles")
    print(f"Output: {args.output}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()

