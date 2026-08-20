"""Deterministic enrichment of the CC0 Kaggle sensor CSV."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

DATASET_PATH = Path(__file__).with_name("data") / "honey_bee_dataset.csv"
SOURCE_URL = "https://www.kaggle.com/datasets/sharannagarajan06/honey-bee-hive-monitoring-dataset"
SOURCE_LICENSE = "CC0: Public Domain"

CSV_COLUMNS = ("Temperature_C", "Moisture_%", "pH", "Hive_Weight_kg")
METRIC_COLUMNS = ("temperature_c", "humidity_percent", "ph", "weight_kg")

# Metadata is intentionally synthetic: the four sensor values are retained
# exactly from the source, while identity, location, and time are generated.
HIVE_METADATA = tuple(
    {
        "hive_id": f"hive-{number}",
        "name": f"Kovan-{number}",
        "location": f"Arı Bahçesi {chr(64 + number)}",
        "latitude": round(40.95 + number * 0.007, 6),
        "longitude": round(29.11 + number * 0.009, 6),
    }
    for number in range(1, 7)
)


def load_sensor_data(path: str | Path = DATASET_PATH) -> list[dict[str, float]]:
    """Read all 3,000 source rows and normalize metric names.

    No sampling or random values are introduced here. A malformed source file
    fails early so the database cannot silently contain partial data.
    """

    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(f"Unexpected dataset columns: {reader.fieldnames!r}")
        rows: list[dict[str, float]] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                values = {
                    "temperature_c": float(row["Temperature_C"]),
                    "humidity_percent": float(row["Moisture_%"]),
                    "ph": float(row["pH"]),
                    "weight_kg": float(row["Hive_Weight_kg"]),
                }
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid sensor value on CSV line {line_number}") from exc
            rows.append(values)
    if len(rows) != 3000:
        raise ValueError(f"Expected 3000 source rows, found {len(rows)}")
    return rows


def iter_enriched_rows(path: str | Path = DATASET_PATH) -> Iterator[dict[str, object]]:
    """Yield deterministic hive/time metadata joined to each source row."""

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index, metrics in enumerate(load_sensor_data(path)):
        hive_number = index % len(HIVE_METADATA)
        metadata = HIVE_METADATA[hive_number]
        # One source record maps to one six-hour slot for its assigned hive.
        recorded_at = start + timedelta(hours=index)
        yield {
            "source_row": index + 1,
            "hive_id": metadata["hive_id"],
            "recorded_at": recorded_at.isoformat().replace("+00:00", "Z"),
            **metrics,
        }


# Short names used by notebooks and smoke scripts.
load_dataset = load_sensor_data
enrich_sensor_data = iter_enriched_rows


__all__ = [
    "CSV_COLUMNS",
    "DATASET_PATH",
    "HIVE_METADATA",
    "METRIC_COLUMNS",
    "SOURCE_LICENSE",
    "SOURCE_URL",
    "iter_enriched_rows",
    "enrich_sensor_data",
    "load_dataset",
    "load_sensor_data",
]
