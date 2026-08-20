#!/usr/bin/env python3
"""Calibrate an abstention threshold and evaluate the untouched test set."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from turkish_medical_vector_search.config import load_config  # noqa: E402
from turkish_medical_vector_search.embeddings.local import LocalSentenceEmbedder  # noqa: E402
from turkish_medical_vector_search.vectorstore.chroma import (  # noqa: E402
    cosine_distance_to_similarity,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/default.yaml")
    parser.add_argument(
        "--benchmark-dir", type=Path, default=PROJECT_ROOT / "data/benchmark"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "reports/metrics"
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--false-accept-cost", type=float, default=2.0)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def classification_metrics(
    rows: list[dict[str, Any]], threshold: float, *, false_accept_cost: float
) -> dict[str, float | int]:
    tp = sum(row["is_answerable"] and row["top_similarity"] >= threshold for row in rows)
    fn = sum(row["is_answerable"] and row["top_similarity"] < threshold for row in rows)
    fp = sum(not row["is_answerable"] and row["top_similarity"] >= threshold for row in rows)
    tn = sum(not row["is_answerable"] and row["top_similarity"] < threshold for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / len(rows),
        "negative_rejection_rate": tn / (tn + fp) if tn + fp else 0.0,
        "weighted_error_cost": false_accept_cost * fp + fn,
    }


def retrieval_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    positives = [row for row in rows if row["is_answerable"]]
    metrics: dict[str, float] = {}
    for k in (1, 3, 5):
        metrics[f"exact_chunk_recall@{k}"] = sum(
            row["expected_chunk_id"] in row["retrieved_chunk_ids"][:k] for row in positives
        ) / len(positives)
        metrics[f"parent_document_recall@{k}"] = sum(
            row["expected_parent_id"] in row["retrieved_parent_ids"][:k] for row in positives
        ) / len(positives)
    return metrics


def error_analysis(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Return compact IDs for manual inspection without hiding alternate matches."""

    positives = [row for row in rows if row["is_answerable"]]
    negatives = [row for row in rows if not row["is_answerable"]]
    return {
        "positive_score_min": min(row["top_similarity"] for row in positives),
        "positive_score_max": max(row["top_similarity"] for row in positives),
        "negative_score_min": min(row["top_similarity"] for row in negatives),
        "negative_score_max": max(row["top_similarity"] for row in negatives),
        "false_reject_question_ids": [
            row["question_id"] for row in positives if row["top_similarity"] < threshold
        ],
        "false_accept_question_ids": [
            row["question_id"] for row in negatives if row["top_similarity"] >= threshold
        ],
        "expected_parent_missing_at_5": [
            row["question_id"]
            for row in positives
            if row["expected_parent_id"] not in row["retrieved_parent_ids"][:5]
        ],
        "expected_chunk_missing_at_5": [
            row["question_id"]
            for row in positives
            if row["expected_chunk_id"] not in row["retrieved_chunk_ids"][:5]
        ],
    }


def threshold_candidates(scores: list[float]) -> list[float]:
    unique = sorted(set(scores))
    candidates = [unique[0] - 1e-6, unique[-1] + 1e-6]
    candidates.extend(unique)
    candidates.extend((left + right) / 2 for left, right in zip(unique, unique[1:]))
    return sorted(set(candidates))


def select_threshold(
    rows: list[dict[str, Any]], *, false_accept_cost: float
) -> tuple[float, list[dict[str, float | int]]]:
    positives = [row["top_similarity"] for row in rows if row["is_answerable"]]
    negatives = [row["top_similarity"] for row in rows if not row["is_answerable"]]
    if max(negatives) < min(positives):
        selected = (max(negatives) + min(positives)) / 2
    else:
        candidates = threshold_candidates([row["top_similarity"] for row in rows])
        ranked = []
        for threshold in candidates:
            metrics = classification_metrics(
                rows, threshold, false_accept_cost=false_accept_cost
            )
            ranked.append((threshold, metrics))
        selected, _ = min(
            ranked,
            key=lambda item: (
                item[1]["weighted_error_cost"],
                -item[1]["f1"],
                -item[1]["negative_rejection_rate"],
                -item[0],
            ),
        )

    curve = []
    for threshold in threshold_candidates([row["top_similarity"] for row in rows]):
        curve.append(
            {
                "threshold": threshold,
                **classification_metrics(
                    rows, threshold, false_accept_cost=false_accept_cost
                ),
            }
        )
    return selected, curve


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    calibration = read_jsonl(args.benchmark_dir / "calibration.jsonl")
    test = read_jsonl(args.benchmark_dir / "test.jsonl")
    all_rows = calibration + test

    embedder = LocalSentenceEmbedder(
        config.embedding.model_id,
        expected_dimension=config.embedding.dimension,
        normalize=config.embedding.normalize,
    )
    query_vectors = embedder.encode_queries(
        [row["question"] for row in all_rows],
        batch_size=config.embedding.batch_size,
    )
    client = chromadb.PersistentClient(
        path=str(PROJECT_ROOT / config.vector_store.persist_directory)
    )
    collection = client.get_collection(config.vector_store.collection_name)
    response = collection.query(
        query_embeddings=query_vectors.tolist(),
        n_results=args.top_k,
        include=["metadatas", "distances"],
    )

    evaluated: list[dict[str, Any]] = []
    for index, benchmark_row in enumerate(all_rows):
        similarities = [
            cosine_distance_to_similarity(distance) for distance in response["distances"][index]
        ]
        metadatas = response["metadatas"][index]
        evaluated.append(
            {
                **benchmark_row,
                "top_similarity": similarities[0],
                "retrieved_chunk_ids": response["ids"][index],
                "retrieved_parent_ids": [metadata["parent_id"] for metadata in metadatas],
                "retrieved_titles": [metadata["title"] for metadata in metadatas],
                "similarities": similarities,
            }
        )

    calibration_results = evaluated[: len(calibration)]
    test_results = evaluated[len(calibration) :]
    threshold, curve = select_threshold(
        calibration_results,
        false_accept_cost=args.false_accept_cost,
    )
    for row in evaluated:
        row["accepted_at_selected_threshold"] = row["top_similarity"] >= threshold

    summary = {
        "model_id": config.embedding.model_id,
        "top_k": args.top_k,
        "threshold_selection": {
            "source_split": "calibration_only",
            "false_accept_cost": args.false_accept_cost,
            "false_reject_cost": 1.0,
            "selected_threshold": threshold,
            "calibration_positive_score_min": min(
                row["top_similarity"] for row in calibration_results if row["is_answerable"]
            ),
            "calibration_positive_score_max": max(
                row["top_similarity"] for row in calibration_results if row["is_answerable"]
            ),
            "calibration_negative_score_min": min(
                row["top_similarity"] for row in calibration_results if not row["is_answerable"]
            ),
            "calibration_negative_score_max": max(
                row["top_similarity"] for row in calibration_results if not row["is_answerable"]
            ),
        },
        "calibration": {
            "classification": classification_metrics(
                calibration_results,
                threshold,
                false_accept_cost=args.false_accept_cost,
            ),
            "retrieval": retrieval_metrics(calibration_results),
            "error_analysis": error_analysis(calibration_results, threshold),
        },
        "test": {
            "classification": classification_metrics(
                test_results,
                threshold,
                false_accept_cost=args.false_accept_cost,
            ),
            "retrieval": retrieval_metrics(test_results),
            "error_analysis": error_analysis(test_results, threshold),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "calibration_results.jsonl", calibration_results)
    write_jsonl(args.output_dir / "test_results.jsonl", test_results)
    (args.output_dir / "threshold_evaluation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.output_dir / "threshold_curve.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(curve[0]))
        writer.writeheader()
        writer.writerows(curve)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
