"""Threshold analysis over benchmark top-1 similarity scores (Phase 6).

Pure, dependency-light functions (no model / no ChromaDB) so the classification
and metric logic is fully unit-testable. The decision rule is:

    accept/retrieve  if  similarity >= threshold
    reject           if  similarity <  threshold
"""
from __future__ import annotations

from statistics import mean, median, pstdev
from typing import Any


def classify(similarity: float, threshold: float) -> bool:
    """Return True if the query is accepted (similarity >= threshold)."""
    return similarity >= threshold


def distribution_stats(scores: list[float]) -> dict[str, float]:
    """Summary statistics for a list of scores."""
    if not scores:
        return {"count": 0}
    return {
        "count": len(scores),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "mean": round(mean(scores), 4),
        "median": round(median(scores), 4),
        "std": round(pstdev(scores), 4) if len(scores) > 1 else 0.0,
    }


def confusion_at_threshold(
    positive_scores: list[float],
    negative_scores: list[float],
    threshold: float,
) -> dict[str, Any]:
    """Confusion matrix + derived metrics at a single threshold.

    Positive question accepted  -> TP;  rejected -> FN.
    Negative question rejected  -> TN;  accepted -> FP.
    """
    tp = sum(1 for s in positive_scores if classify(s, threshold))
    fn = len(positive_scores) - tp
    fp = sum(1 for s in negative_scores if classify(s, threshold))
    tn = len(negative_scores) - fp

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0          # sensitivity
    specificity = tn / (tn + fp) if (tn + fp) else 0.0     # negative rejection rate
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    far = fp / (fp + tn) if (fp + tn) else 0.0             # false acceptance rate
    frr = fn / (fn + tp) if (fn + tp) else 0.0             # false rejection rate

    return {
        "threshold": round(threshold, 4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1": round(f1, 4),
        "false_acceptance_rate": round(far, 4),
        "false_rejection_rate": round(frr, 4),
    }


def frange(start: float, stop: float, step: float) -> list[float]:
    """Inclusive float range on a rounded grid (avoids fp drift)."""
    n = int(round((stop - start) / step))
    return [round(start + i * step, 4) for i in range(n + 1)]


def sweep_thresholds(
    positive_scores: list[float],
    negative_scores: list[float],
    start: float,
    stop: float,
    step: float = 0.01,
) -> list[dict[str, Any]]:
    """Evaluate metrics across a fine grid of candidate thresholds."""
    return [
        confusion_at_threshold(positive_scores, negative_scores, t)
        for t in frange(start, stop, step)
    ]


def select_threshold(
    positive_scores: list[float],
    negative_scores: list[float],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pick a defensible threshold from swept candidates.

    Objective: prevent unanswerable questions reaching the LLM while retaining
    answerable ones. Ranking priority:
      1. highest specificity (negative rejection),
      2. then highest recall,
      3. then highest F1,
      4. tie-break: the most defensible value — the midpoint of the largest
         separating gap when perfect separation exists, otherwise the smallest
         threshold achieving the best (specificity, recall, F1).
    """
    best = max(
        candidates,
        key=lambda c: (c["specificity"], c["recall"], c["f1"], -c["threshold"]),
    )
    # If the score sets are perfectly separable, prefer the gap midpoint as the
    # most defensible, robust value.
    max_neg = max(negative_scores) if negative_scores else 0.0
    min_pos = min(positive_scores) if positive_scores else 0.0
    separable = min_pos > max_neg
    if separable:
        midpoint = round((min_pos + max_neg) / 2, 4)
        chosen = confusion_at_threshold(positive_scores, negative_scores, midpoint)
        return {
            "threshold": midpoint,
            "separable": True,
            "gap_low": round(max_neg, 4),
            "gap_high": round(min_pos, 4),
            "metrics": chosen,
            "rationale": (
                "Positive and negative top-1 scores are perfectly separable; "
                "threshold set to the midpoint of the separating gap for maximum "
                "robustness (equal margin to both classes)."
            ),
        }
    return {
        "threshold": best["threshold"],
        "separable": False,
        "gap_low": round(max_neg, 4),
        "gap_high": round(min_pos, 4),
        "metrics": best,
        "rationale": (
            "Scores overlap (no perfect separation). Chose the threshold with the "
            "highest specificity, then recall, then F1, preferring the smallest "
            "such value; the trade-off (any FP/FN) is reported explicitly."
        ),
    }
