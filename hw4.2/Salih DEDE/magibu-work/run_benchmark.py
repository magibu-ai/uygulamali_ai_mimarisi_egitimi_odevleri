"""benchmark.json'daki soruları RAG pipeline'ından geçirip answered/refused durumuna göre TP/FP/TN/FN skorlarını hesaplar ve sonuçları bir JSON dosyasına yazar."""

import argparse
import json
import time
from pathlib import Path

import explain
from rag import run as run_rag

HERE = Path(__file__).parent


def classify(label: str, status: str) -> str:
    answered = status == "answered"
    if label == "answerable":
        return "TP" if answered else "FN"
    return "FP" if answered else "TN"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(HERE / "benchmark.json"))
    parser.add_argument("--output", default=str(HERE / "benchmark_results.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()

    data = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    items = data["items"][: args.limit] if args.limit else data["items"]

    counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    results = []

    for i, item in enumerate(items, 1):
        t0 = time.time()
        outcome = run_rag(item["question"], max_attempts=args.max_attempts)
        elapsed = time.time() - t0

        verdict = classify(item["label"], outcome["status"])
        counts[verdict] += 1

        print(f"[{i}/{len(items)}] {verdict}  ({elapsed:.1f}s)  {item['id']}: {item['question']}")

        results.append(
            {
                "id": item["id"],
                "label": item["label"],
                "category": item.get("category"),
                "question": item["question"],
                "status": outcome["status"],
                "answer": outcome["answer"],
                "verdict": verdict,
                "attempts": len(outcome["trace"]),
                "trace": outcome["trace"],
            }
        )

    tp, fp, tn, fn = counts["TP"], counts["FP"], counts["TN"], counts["FN"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(items) if items else 0.0

    summary = {
        "n_items": len(items),
        "counts": counts,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }

    Path(args.output).write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    explain.print_confusion_matrix(counts, summary)
    explain.print_category_breakdown(results)
    print(f"\nDetaylı sonuçlar: {args.output}")


if __name__ == "__main__":
    main()
