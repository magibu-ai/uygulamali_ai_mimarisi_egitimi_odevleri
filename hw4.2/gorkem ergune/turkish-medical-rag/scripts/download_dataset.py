"""Phase 1 pipeline: load, validate, select, and persist the document corpus.

Usage:
    python scripts/download_dataset.py

Reads all parameters from ``configs/config.yaml``. Produces:
  * data/processed/selected_documents.jsonl  (the 300 selected documents)
  * artifacts/dataset_statistics.json        (corpus + selection statistics)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as a plain script (`python scripts/download_dataset.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, resolve_path  # noqa: E402
from src.data.loader import load_documents, resolve_splits  # noqa: E402
from src.data.selector import (  # noqa: E402
    compute_length_stats,
    find_valid_and_duplicates,
    select_documents,
)


def _per_split_counts(documents: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in documents:
        counts[doc["source"]] = counts.get(doc["source"], 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    config = load_config()
    ds_cfg = config["dataset"]
    seed = config["seed"]
    count = ds_cfg["document_count"]

    print(f"[1/5] Loading dataset '{ds_cfg['name']}' ...")
    documents = load_documents(config)
    print(f"      loaded {len(documents)} raw documents "
          f"from splits: {resolve_splits(config)}")

    print("[2/5] Validating and de-duplicating ...")
    valid, diagnostics = find_valid_and_duplicates(documents)
    print(f"      valid unique documents: {len(valid)} "
          f"(empty={diagnostics['empty_text_count']}, "
          f"duplicates={diagnostics['duplicate_count']})")

    print(f"[3/5] Selecting {count} documents (seed={seed}) ...")
    selected = select_documents(valid, seed=seed, count=count)
    print(f"      selected {len(selected)} documents")

    print("[4/5] Writing selected documents ...")
    out_path = resolve_path(ds_cfg["selected_output"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        for doc in selected:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"      -> {out_path}")

    print("[5/5] Writing statistics ...")
    statistics = {
        "dataset_name": ds_cfg["name"],
        "splits": resolve_splits(config),
        "seed": seed,
        "fields": {
            "text_field": ds_cfg["text_field"],
            "url_field": ds_cfg["url_field"],
            "title_field": ds_cfg["title_field"],
            "source_field": "derived from HF split name",
        },
        "total_source_documents": len(documents),
        "per_split_source_counts": _per_split_counts(documents),
        "empty_text_count": diagnostics["empty_text_count"],
        "duplicate_count": diagnostics["duplicate_count"],
        "missing_url_count": diagnostics["missing_url_count"],
        "missing_title_count": diagnostics["missing_title_count"],
        "valid_unique_documents": len(valid),
        "selected_documents": len(selected),
        "selected_per_split_counts": _per_split_counts(selected),
        "length_stats_selected": compute_length_stats(selected),
        "length_stats_valid_pool": compute_length_stats(valid),
    }
    stats_path = resolve_path(ds_cfg["statistics_output"])
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as handle:
        json.dump(statistics, handle, ensure_ascii=False, indent=2)
    print(f"      -> {stats_path}")

    print("\nDone. Summary:")
    print(f"  total source documents : {statistics['total_source_documents']}")
    print(f"  valid unique documents : {statistics['valid_unique_documents']}")
    print(f"  selected documents     : {statistics['selected_documents']}")


if __name__ == "__main__":
    main()
