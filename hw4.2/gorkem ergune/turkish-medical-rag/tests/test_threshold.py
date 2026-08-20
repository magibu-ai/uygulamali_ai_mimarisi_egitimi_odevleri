"""Phase 6 tests: threshold classification, metrics, and selection logic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import load_config, resolve_path
from src.evaluation.threshold import (
    classify,
    confusion_at_threshold,
    distribution_stats,
    frange,
    select_threshold,
    sweep_thresholds,
)


# --- classification / boundary ------------------------------------------- #

def test_classify_boundary_is_inclusive():
    # accept if similarity >= threshold
    assert classify(0.50, 0.50) is True
    assert classify(0.4999, 0.50) is False
    assert classify(0.51, 0.50) is True


# --- confusion matrix / metrics ------------------------------------------ #

def test_confusion_perfect_separation():
    pos = [0.7, 0.8, 0.9]
    neg = [0.2, 0.3, 0.4]
    m = confusion_at_threshold(pos, neg, 0.55)
    assert (m["tp"], m["tn"], m["fp"], m["fn"]) == (3, 3, 0, 0)
    assert m["accuracy"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["specificity"] == 1.0
    assert m["f1"] == 1.0
    assert m["false_acceptance_rate"] == 0.0
    assert m["false_rejection_rate"] == 0.0


def test_confusion_with_overlap():
    pos = [0.4, 0.6, 0.8]   # at t=0.5 -> 0.4 is FN
    neg = [0.3, 0.55]       # at t=0.5 -> 0.55 is FP
    m = confusion_at_threshold(pos, neg, 0.5)
    assert m["tp"] == 2 and m["fn"] == 1
    assert m["tn"] == 1 and m["fp"] == 1
    assert m["false_rejection_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["false_acceptance_rate"] == pytest.approx(1 / 2, abs=1e-3)


def test_metric_rates_definitions():
    pos = [0.6, 0.7]
    neg = [0.4, 0.5]
    m = confusion_at_threshold(pos, neg, 0.55)
    # recall = TP/(TP+FN), specificity = TN/(TN+FP)
    assert m["recall"] == pytest.approx(m["tp"] / (m["tp"] + m["fn"]))
    assert m["specificity"] == pytest.approx(m["tn"] / (m["tn"] + m["fp"]))


# --- distribution stats -------------------------------------------------- #

def test_distribution_stats():
    s = distribution_stats([0.2, 0.4, 0.6])
    assert s["count"] == 3
    assert s["min"] == 0.2 and s["max"] == 0.6
    assert s["mean"] == 0.4 and s["median"] == 0.4
    assert s["std"] >= 0.0


# --- grid / sweep -------------------------------------------------------- #

def test_frange_inclusive_grid():
    g = frange(0.50, 0.55, 0.01)
    assert g == [0.50, 0.51, 0.52, 0.53, 0.54, 0.55]


def test_sweep_covers_grid():
    sweep = sweep_thresholds([0.7], [0.3], 0.30, 0.70, 0.01)
    assert len(sweep) == 41
    assert all("f1" in c for c in sweep)


# --- selection logic ----------------------------------------------------- #

def test_select_threshold_separable_prefers_midpoint():
    pos = [0.70, 0.80, 0.90]
    neg = [0.30, 0.40, 0.50]
    sweep = sweep_thresholds(pos, neg, 0.30, 0.90, 0.01)
    sel = select_threshold(pos, neg, sweep)
    assert sel["separable"] is True
    assert sel["threshold"] == pytest.approx(0.60, abs=1e-6)  # midpoint of gap
    assert sel["metrics"]["specificity"] == 1.0
    assert sel["metrics"]["recall"] == 1.0


def test_select_threshold_overlap_reports_tradeoff():
    pos = [0.45, 0.60, 0.80]
    neg = [0.40, 0.55]  # overlaps positives
    sweep = sweep_thresholds(pos, neg, 0.40, 0.80, 0.01)
    sel = select_threshold(pos, neg, sweep)
    assert sel["separable"] is False
    # prioritizes specificity: threshold must reject both negatives
    assert sel["metrics"]["specificity"] == 1.0


# --- config + benchmark integrity ---------------------------------------- #

def test_benchmark_results_integrity_if_present():
    """If the evaluation artifact exists, it must contain 30 coherent records."""
    path = resolve_path("artifacts/benchmark_results.json")
    if not Path(path).exists():
        pytest.skip("benchmark_results.json not generated yet")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    results = data["results"]
    assert len(results) == 30
    assert sum(r["type"] == "positive" for r in results) == 20
    assert sum(r["type"] == "negative" for r in results) == 10
    for r in results:
        assert len(r["top5_chunk_ids"]) == 5
        assert len(r["top5_similarities"]) == 5
        assert 0.0 <= r["top1_similarity"] <= 1.0001
