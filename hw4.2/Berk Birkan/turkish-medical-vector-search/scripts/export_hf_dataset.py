#!/usr/bin/env python3
"""Build and validate the local Hugging Face Dataset delivery package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT = PROJECT_ROOT / "data/processed/chunks_with_vectors.parquet"
OUTPUT = PROJECT_ROOT / "hf_dataset/data/train.parquet"
REPORT = PROJECT_ROOT / "reports/metrics/hf_dataset_validation.json"

COLUMNS = [
    "url", "chunk_text", "chunk_vector", "chunk_id", "parent_id", "title",
    "branch", "chunk_index", "token_count", "embedding_model",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(table: pa.Table) -> dict:
    missing = {"url", "chunk_text", "chunk_vector"}.difference(table.column_names)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if table.num_rows != 1019:
        raise ValueError(f"Expected 1019 chunks, got {table.num_rows}")
    if table.column("url").null_count or table.column("chunk_text").null_count:
        raise ValueError("Required text columns contain null values")

    vector_type = table.schema.field("chunk_vector").type
    if not pa.types.is_fixed_size_list(vector_type) or vector_type.list_size != 768:
        raise ValueError(f"Unexpected vector type: {vector_type}")
    vectors = np.asarray(table.column("chunk_vector").to_pylist(), dtype=np.float32)
    if vectors.shape != (1019, 768) or not np.isfinite(vectors).all():
        raise ValueError(f"Invalid vector matrix: {vectors.shape}")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        raise ValueError("Vectors are not L2-normalized")

    return {
        "rows": table.num_rows,
        "columns": table.column_names,
        "required_columns_present": True,
        "unique_chunks": len(set(table.column("chunk_id").to_pylist())),
        "unique_parents": len(set(table.column("parent_id").to_pylist())),
        "vector_dimension": vector_type.list_size,
        "vector_dtype": str(vector_type.value_type),
        "finite_vectors": True,
        "l2_norm_min": float(norms.min()),
        "l2_norm_mean": float(norms.mean()),
        "l2_norm_max": float(norms.max()),
    }


def main() -> None:
    table = pq.read_table(INPUT).select(COLUMNS)
    validation = validate(table)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, OUTPUT, compression="zstd", version="2.6")
    round_trip = pq.read_table(OUTPUT)
    if not table.schema.equals(round_trip.schema) or table.num_rows != round_trip.num_rows:
        raise ValueError("Parquet round-trip changed schema or row count")
    validation.update({
        "output": str(OUTPUT.relative_to(PROJECT_ROOT)),
        "file_size_bytes": OUTPUT.stat().st_size,
        "sha256": sha256(OUTPUT),
        "parquet_round_trip": True,
    })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
