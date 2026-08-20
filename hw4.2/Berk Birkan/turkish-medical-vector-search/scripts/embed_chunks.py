#!/usr/bin/env python3
"""Generate checkpointed local embeddings and append them to chunk Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.config import load_config  # noqa: E402
from turkish_medical_vector_search.embeddings.local import LocalSentenceEmbedder  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument(
        "--source", type=Path, default=PROJECT_ROOT / "data/processed/chunks.parquet"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data/processed/chunks_with_vectors.parquet",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts/embedding_shards",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports/metrics/embedding_summary.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    table = pq.read_table(args.source)
    texts = table.column("chunk_text").to_pylist()
    source_sha256 = hashlib.sha256(args.source.read_bytes()).hexdigest()
    checkpoint_payload = json.dumps(
        {
            "source_sha256": source_sha256,
            "model_id": config.embedding.model_id,
            "dimension": config.embedding.dimension,
            "normalize": config.embedding.normalize,
            "batch_size": config.embedding.batch_size,
            "tokenizer_patch": "not_applied_custom_split_pretokenizer",
        },
        sort_keys=True,
    )
    checkpoint_fingerprint = hashlib.sha256(checkpoint_payload.encode("utf-8")).hexdigest()
    checkpoint_dir = args.checkpoint_dir / checkpoint_fingerprint[:16]
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    expected_shards: list[tuple[int, int, Path]] = []
    batch_size = config.embedding.batch_size
    for start in range(0, len(texts), batch_size):
        end = min(start + batch_size, len(texts))
        expected_shards.append((start, end, checkpoint_dir / f"{start:06d}_{end:06d}.npy"))

    missing = [item for item in expected_shards if not item[2].exists()]
    embedder = None
    if missing:
        embedder = LocalSentenceEmbedder(
            config.embedding.model_id,
            expected_dimension=config.embedding.dimension,
            normalize=config.embedding.normalize,
        )
    for start, end, shard_path in expected_shards:
        if shard_path.exists():
            vectors = np.load(shard_path)
            if vectors.shape != (end - start, config.embedding.dimension):
                raise ValueError(f"Invalid checkpoint shape in {shard_path}: {vectors.shape}")
            continue
        assert embedder is not None
        vectors = embedder.encode_documents(texts[start:end], batch_size=batch_size)
        np.save(shard_path, vectors.astype(np.float32, copy=False))
        print(f"Embedded chunks {start}:{end}")

    matrix = np.concatenate([np.load(path) for _, _, path in expected_shards], axis=0)
    if matrix.shape != (table.num_rows, config.embedding.dimension):
        raise ValueError(f"Unexpected combined matrix shape: {matrix.shape}")
    vector_array = pa.array(
        matrix.tolist(),
        type=pa.list_(pa.float32(), list_size=config.embedding.dimension),
    )
    output = table.append_column("chunk_vector", vector_array)
    output = output.append_column(
        "embedding_model",
        pa.array([config.embedding.model_id] * table.num_rows, type=pa.string()),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(output, args.output, compression="zstd")

    norms = np.linalg.norm(matrix, axis=1)
    report = {
        "chunk_count": table.num_rows,
        "model_id": config.embedding.model_id,
        "dimension": config.embedding.dimension,
        "dtype": str(matrix.dtype),
        "normalize": config.embedding.normalize,
        "batch_size": batch_size,
        "source_sha256": source_sha256,
        "checkpoint_fingerprint": checkpoint_fingerprint,
        "tokenizer_patch": "not_applied_custom_split_pretokenizer",
        "norm_min": float(norms.min()),
        "norm_mean": float(norms.mean()),
        "norm_max": float(norms.max()),
        "finite_values": bool(np.isfinite(matrix).all()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {table.num_rows} vectors to {args.output}")


if __name__ == "__main__":
    main()
