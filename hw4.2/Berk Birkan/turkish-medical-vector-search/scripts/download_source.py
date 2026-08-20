#!/usr/bin/env python3
"""Download the gated source Parquet file from Hugging Face Hub."""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "umutertugrul/turkish-medical-articles"
FULL_FILENAME = "doktorsitesi_articles.parquet"
SAMPLE_FILENAME = "sample.parquet"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Download the 1,000-row preview instead of the complete dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data/raw",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filename = SAMPLE_FILENAME if args.sample else FULL_FILENAME
    path = hf_hub_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        filename=filename,
        local_dir=args.output_dir,
    )
    print(f"Downloaded {REPO_ID}/{filename} to {path}")


if __name__ == "__main__":
    main()

