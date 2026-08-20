#!/usr/bin/env python3
"""Regenerate report figures from versioned metrics and local chunk artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS = PROJECT_ROOT / "reports/metrics"
FIGURES = PROJECT_ROOT / "reports/figures"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((METRICS / "threshold_evaluation.json").read_text(encoding="utf-8"))
    threshold = summary["threshold_selection"]["selected_threshold"]
    calibration = read_jsonl(METRICS / "calibration_results.jsonl")
    test = read_jsonl(METRICS / "test_results.jsonl")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for axis, rows, title in zip(axes, [calibration, test], ["Kalibrasyon", "Bağımsız test"]):
        positive = [row["top_similarity"] for row in rows if row["is_answerable"]]
        negative = [row["top_similarity"] for row in rows if not row["is_answerable"]]
        axis.scatter(positive, [1] * len(positive), label="Pozitif", alpha=0.8)
        axis.scatter(negative, [0] * len(negative), label="Negatif", alpha=0.8)
        axis.axvline(threshold, color="black", linestyle="--", label=f"Eşik={threshold:.4f}")
        axis.set_title(title)
        axis.set_xlabel("Top-1 cosine similarity")
        axis.set_yticks([0, 1], ["Negatif", "Pozitif"])
        axis.grid(alpha=0.2)
    axes[0].legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(FIGURES / "score_distributions.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    with (METRICS / "threshold_curve.csv").open(encoding="utf-8") as file:
        curve = list(csv.DictReader(file))
    x = [float(row["threshold"]) for row in curve]
    fig, axis = plt.subplots(figsize=(7, 4))
    axis.plot(x, [float(row["precision"]) for row in curve], label="Precision")
    axis.plot(x, [float(row["recall"]) for row in curve], label="Recall")
    axis.plot(x, [float(row["f1"]) for row in curve], label="F1")
    axis.axvline(threshold, color="black", linestyle="--", label="Seçilen eşik")
    axis.set(xlabel="Threshold", ylabel="Skor", ylim=(-0.02, 1.02), title="Kalibrasyon threshold taraması")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "threshold_curve.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    chunks = pq.read_table(PROJECT_ROOT / "data/processed/chunks.parquet")
    token_counts = chunks.column("token_count").to_pylist()
    fig, axis = plt.subplots(figsize=(7, 4))
    axis.hist(token_counts, bins=24, color="#4c78a8", edgecolor="white")
    axis.axvline(512, color="black", linestyle="--", label="512 token sınırı")
    axis.set(xlabel="Chunk token sayısı", ylabel="Chunk sayısı", title="Chunk boyutu dağılımı")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "chunk_token_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Figures written to {FIGURES}")


if __name__ == "__main__":
    main()
