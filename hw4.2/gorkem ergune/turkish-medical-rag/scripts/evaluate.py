"""Phase 6: evaluate the 30 benchmark questions and derive a threshold.

Runs every official benchmark question through the REAL production pipeline
(Phase 3 query encoding -> Phase 4 ChromaDB cosine retrieval), records the full
top-5 output, analyzes positive vs negative top-1 score distributions, sweeps a
fine threshold grid, and selects a defensible threshold.

Writes (all gitignored artifacts):
  * artifacts/benchmark_results.json   (per-question retrieval)
  * artifacts/threshold_analysis.json  (distributions, sweep, selection)
  * artifacts/score_distribution.txt   (ASCII score histogram)

Does NOT modify the frozen benchmark. Prints the selected threshold for the
operator to record in configs/config.yaml.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import Embedder  # noqa: E402
from src.evaluation.threshold import (  # noqa: E402
    confusion_at_threshold,
    distribution_stats,
    frange,
    select_threshold,
    sweep_thresholds,
)
from src.vectorstore.chroma_store import ChromaStore  # noqa: E402

TOP_K = 5


def _ascii_histogram(pos: list[float], neg: list[float], width: int = 40) -> str:
    lines = ["score  | P=positive top1   N=negative top1", "-" * 52]
    lo, hi, step = 0.40, 0.90, 0.05
    edges = frange(lo, hi, step)
    for e in edges:
        p = sum(1 for s in pos if e <= s < e + step)
        n = sum(1 for s in neg if e <= s < e + step)
        bar = "P" * p + "N" * n
        lines.append(f"{e:.2f}  | {bar}  ({p}P {n}N)")
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    bench = json.loads(
        (resolve_path(config["paths"]["data_benchmark"]) / "benchmark.json")
        .read_text(encoding="utf-8")
    )
    embedder = Embedder.from_config(config).load()
    store = ChromaStore.from_config(config).connect(fresh=False)

    results = []
    pos_top1, neg_top1 = [], []
    for q in bench["questions"]:
        emb = embedder.encode_queries([q["question"]])[0]
        hits = store.search(emb, top_k=TOP_K)
        top1 = hits[0]["similarity"]
        record = {
            "id": q["id"],
            "question": q["question"],
            "type": q["type"],
            "top1_similarity": round(top1, 4),
            "top5_chunk_ids": [h["chunk_id"] for h in hits],
            "top5_similarities": [round(h["similarity"], 4) for h in hits],
            "top5_parent_ids": [h["parent_id"] for h in hits],
            "top5_urls": [h["url"] for h in hits],
            "top5_titles": [h["title"] for h in hits],
        }
        if q["type"] == "positive":
            pos_top1.append(top1)
            exp_chunk = q["expected_chunk_ids"][0]
            exp_parent = q["expected_parent_ids"][0]
            record["expected_chunk_id"] = exp_chunk
            record["expected_parent_id"] = exp_parent
            record["expected_evidence_in_top5"] = exp_chunk in record["top5_chunk_ids"]
            record["expected_parent_rank1"] = record["top5_parent_ids"][0] == exp_parent
        else:
            neg_top1.append(top1)
            record["target_topic"] = q["target_topic"]
        results.append(record)

    pos_stats = distribution_stats(pos_top1)
    neg_stats = distribution_stats(neg_top1)
    margin = round(pos_stats["min"] - neg_stats["max"], 4)

    # sweep across the observed interval (rounded to 0.01 grid)
    lo = math.floor(min(pos_top1 + neg_top1) * 100) / 100
    hi = math.ceil(max(pos_top1 + neg_top1) * 100) / 100
    sweep = sweep_thresholds(pos_top1, neg_top1, lo, hi, step=0.01)
    selection = select_threshold(pos_top1, neg_top1, sweep)

    chosen = selection["threshold"]
    robustness = [
        confusion_at_threshold(pos_top1, neg_top1, t)
        for t in frange(round(chosen - 0.03, 2), round(chosen + 0.03, 2), 0.01)
    ]

    # --- write artifacts ---
    art = resolve_path(config["paths"]["artifacts"])
    (art / "benchmark_results.json").write_text(
        json.dumps({"metadata": bench["metadata"], "results": results},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = {
        "note": (
            "Threshold CALIBRATED on the frozen 30-question official benchmark. "
            "The same set is used for selection, so this is an evaluation/"
            "calibration threshold, NOT an independently validated production "
            "generalization threshold."
        ),
        "decision_rule": "accept if similarity >= threshold, else reject",
        "signal": "top-1 cosine similarity",
        "positive_distribution": pos_stats,
        "negative_distribution": neg_stats,
        "min_positive_minus_max_negative_margin": margin,
        "sweep_interval": {"start": lo, "stop": hi, "step": 0.01},
        "candidate_sweep": sweep,
        "selected_threshold": chosen,
        "selection": selection,
        "robustness_neighbors": robustness,
        "positive_recall_verification": {
            "expected_evidence_in_top5": sum(
                1 for r in results
                if r["type"] == "positive" and r.get("expected_evidence_in_top5")),
            "expected_parent_rank1": sum(
                1 for r in results
                if r["type"] == "positive" and r.get("expected_parent_rank1")),
            "positive_total": len(pos_top1),
        },
    }
    (art / "threshold_analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    (art / "score_distribution.txt").write_text(
        _ascii_histogram(pos_top1, neg_top1), encoding="utf-8")

    # --- console summary ---
    print("POSITIVE top1:", pos_stats)
    print("NEGATIVE top1:", neg_stats)
    print("min(pos) - max(neg) margin:", margin,
          "| separable:", selection["separable"])
    print(f"\nSELECTED THRESHOLD = {chosen}")
    print("metrics:", selection["metrics"])
    print("rationale:", selection["rationale"])
    print("\nRobustness (neighbors):")
    for r in robustness:
        print(f"  t={r['threshold']:.2f} acc={r['accuracy']} "
              f"spec={r['specificity']} recall={r['recall']} f1={r['f1']} "
              f"FP={r['fp']} FN={r['fn']}")
    print("\n--> Record this threshold in configs/config.yaml: "
          f"retrieval.threshold = {chosen}")


if __name__ == "__main__":
    main()
