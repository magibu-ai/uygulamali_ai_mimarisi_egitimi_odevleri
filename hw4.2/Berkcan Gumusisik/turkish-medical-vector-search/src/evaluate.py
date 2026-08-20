"""Benchmark the index and derive the optimal similarity threshold.

For every test question we embed the query, pull the top-K chunks, and record
the best cosine similarity. Positives should score high (answerable), negatives
low (must be refused). We then sweep the threshold and report precision / recall
/ F1 / accuracy for the answer-vs-refuse decision, plus retrieval accuracy for
the positives (did the correct source article show up).

Run:  python src/evaluate.py
"""
import json

import numpy as np

import config as C
from search import search


def _load():
    data = json.loads(C.TEST_QUESTIONS.read_text(encoding="utf-8"))
    return data["positive"], data["negative"]


def _score_all(k=C.TOP_K):
    positives, negatives = _load()
    rows = []
    for q in positives:
        # threshold=0 -> never refuse, so we always get the hits back to inspect.
        r = search(q["question"], k=k, threshold=0.0)
        urls = [h.url for h in r.hits]
        rows.append(
            {
                "id": q["id"], "label": "positive", "question": q["question"],
                "top_sim": r.top_similarity,
                "expected_url": q["expected_url"],
                "top1_url": urls[0] if urls else "",
                "hit_in_topk": q["expected_url"] in urls,
                "hit_at_1": bool(urls) and urls[0] == q["expected_url"],
            }
        )
    for q in negatives:
        r = search(q["question"], k=k, threshold=0.0)
        rows.append(
            {
                "id": q["id"], "label": "negative", "question": q["question"],
                "top_sim": r.top_similarity,
                "expected_url": None, "top1_url": r.hits[0].url if r.hits else "",
                "hit_in_topk": None, "hit_at_1": None,
            }
        )
    return rows


def _sweep(rows, lo=0.20, hi=0.70, step=0.01):
    pos = [r["top_sim"] for r in rows if r["label"] == "positive"]
    neg = [r["top_sim"] for r in rows if r["label"] == "negative"]
    P, N = len(pos), len(neg)
    table = []
    for thr in np.round(np.arange(lo, hi + 1e-9, step), 2):
        tp = sum(s >= thr for s in pos)          # positive answered
        fn = P - tp                               # positive wrongly refused
        fp = sum(s >= thr for s in neg)           # negative wrongly answered
        tn = N - fp                               # negative correctly refused
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        acc = (tp + tn) / (P + N)
        table.append(
            {"threshold": float(thr), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
             "precision": round(prec, 3), "recall": round(rec, 3),
             "f1": round(f1, 3), "accuracy": round(acc, 3)}
        )
    return table


def _recommend(rows, table):
    """Prefer a threshold in the separating gap (midpoint); else best F1/accuracy."""
    pos = [r["top_sim"] for r in rows if r["label"] == "positive"]
    neg = [r["top_sim"] for r in rows if r["label"] == "negative"]
    min_pos, max_neg = min(pos), max(neg)
    if min_pos > max_neg:  # clean separation
        return round((min_pos + max_neg) / 2, 3), "gap-midpoint (perfect separation)"
    # Overlap present: find the plateau that maximises accuracy (positives
    # answered + negatives refused weigh equally) and, within it, precision — a
    # medical assistant should err toward refusing an out-of-scope question. Then
    # pick the MIDPOINT of that plateau so the operating point sits as far as
    # possible from both the highest negative and the lowest retained positive
    # (maximum robustness), rather than on a fragile edge.
    max_acc = max(r["accuracy"] for r in table)
    band = [r for r in table if r["accuracy"] == max_acc]
    max_prec = max(r["precision"] for r in band)
    band = [r for r in band if r["precision"] == max_prec]
    thr = round((band[0]["threshold"] + band[-1]["threshold"]) / 2, 2)
    return thr, "midpoint of max-accuracy / max-precision plateau (robust, medical: avoid hallucination)"


def main():
    C.OUTPUT_DIR.mkdir(exist_ok=True)
    rows = _score_all()
    table = _sweep(rows)
    rec_thr, rec_reason = _recommend(rows, table)

    pos = [r for r in rows if r["label"] == "positive"]
    neg = [r for r in rows if r["label"] == "negative"]
    pos_sims = [r["top_sim"] for r in pos]
    neg_sims = [r["top_sim"] for r in neg]

    print("\n=== Per-question top-1 cosine similarity ===")
    print("POSITIVES (should be answered):")
    for r in sorted(pos, key=lambda x: -x["top_sim"]):
        flag = "OK " if r["hit_at_1"] else ("~top" + str(r["hit_in_topk"])[0] if r["hit_in_topk"] else "MISS")
        print(f"  {r['id']}  sim={r['top_sim']:.3f}  [{flag}]  {r['question'][:52]}")
    print("NEGATIVES (should be refused):")
    for r in sorted(neg, key=lambda x: -x["top_sim"]):
        print(f"  {r['id']}  sim={r['top_sim']:.3f}         {r['question'][:52]}")

    print("\n=== Similarity distribution ===")
    print(f"  positive: min={min(pos_sims):.3f}  mean={np.mean(pos_sims):.3f}  max={max(pos_sims):.3f}")
    print(f"  negative: min={min(neg_sims):.3f}  mean={np.mean(neg_sims):.3f}  max={max(neg_sims):.3f}")
    gap = min(pos_sims) - max(neg_sims)
    print(f"  separation gap (min_pos - max_neg) = {gap:+.3f}")

    print("\n=== Threshold sweep (selected rows) ===")
    print("  thr   TP FN FP TN   prec  rec   F1    acc")
    for r in table:
        if abs((r["threshold"] * 100) % 5) < 1e-6:  # every 0.05
            print(f"  {r['threshold']:.2f}  {r['tp']:2d} {r['fn']:2d} {r['fp']:2d} {r['tn']:2d}  "
                  f"{r['precision']:.2f}  {r['recall']:.2f}  {r['f1']:.2f}  {r['accuracy']:.2f}")

    hit1 = sum(r["hit_at_1"] for r in pos) / len(pos)
    hitk = sum(r["hit_in_topk"] for r in pos) / len(pos)
    at_rec = next(r for r in table if abs(r["threshold"] - rec_thr) < 0.005) if any(
        abs(r["threshold"] - rec_thr) < 0.005 for r in table) else None
    print(f"\n=== Retrieval accuracy (positives) ===")
    print(f"  correct article @top-1 : {hit1*100:.0f}%")
    print(f"  correct article @top-{C.TOP_K} : {hitk*100:.0f}%")
    print(f"\n>>> RECOMMENDED THRESHOLD = {rec_thr}  ({rec_reason})")
    if at_rec:
        print(f"    at this threshold: precision={at_rec['precision']} recall={at_rec['recall']} "
              f"F1={at_rec['f1']} accuracy={at_rec['accuracy']}")

    # persist
    C.BENCHMARK_JSON.write_text(json.dumps({
        "per_question": rows,
        "distribution": {
            "positive": {"min": min(pos_sims), "mean": float(np.mean(pos_sims)), "max": max(pos_sims)},
            "negative": {"min": min(neg_sims), "mean": float(np.mean(neg_sims)), "max": max(neg_sims)},
            "separation_gap": gap,
        },
        "retrieval_accuracy": {"top1": hit1, f"top{C.TOP_K}": hitk},
        "recommended_threshold": rec_thr,
        "recommendation_reason": rec_reason,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    import csv
    with open(C.THRESHOLD_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0].keys()))
        w.writeheader()
        w.writerows(table)
    print(f"\nWrote {C.BENCHMARK_JSON.name} and {C.THRESHOLD_CSV.name} to {C.OUTPUT_DIR}")


if __name__ == "__main__":
    main()
