#!/usr/bin/env python
"""Threshold calibration and retrieval benchmark.

    uv run python scripts/benchmark.py

Runs the 30-question evaluation set (20 answerable, 10 out-of-scope) through the
real retrieval path and sweeps the cosine similarity threshold to find the value
that best separates them. Writes a JSON result file and a Markdown report that
feeds the README's "Threshold Analysis" section.

With ``--with-rag`` it additionally exercises the full LLM path on a couple of
questions using DEEPSEEK_API_KEY from .env, to prove the generation side works
end to end. That flag is for the operator only; the web app never reads a key
from the environment.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ehekim  # noqa: F401  (applies the torch/Triton compatibility fix first)

import numpy as np

from ehekim.config import (
    EMBEDDING_MODEL_ID,
    PROJECT_ROOT,
    REFUSAL_MESSAGE_TR,
    get_settings,
    operator_secrets,
)
from ehekim.embedding import Embedder
from ehekim.retrieval import build_rag_messages, expand_context, search
from ehekim.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("benchmark")

DATA_DIR = PROJECT_ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "benchmark_questions.json"
RESULTS_PATH = DATA_DIR / "benchmark_results.json"
REPORT_PATH = DATA_DIR / "threshold_report.md"
# Flat, viewer-friendly rendering of the 30-question evaluation set. The JSON
# above is nested (positive/negative arrays) and therefore does not render in the
# Hugging Face dataset viewer; this parquet does.
QUESTIONS_PARQUET_PATH = DATA_DIR / "benchmark_questions.parquet"

# Retrieval depth used for the analysis. Wider than the UI default so the sweep
# can see what a permissive threshold would have admitted.
ANALYSIS_TOP_K = 10
SWEEP = np.round(np.arange(0.20, 0.901, 0.01), 2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="e-hekim threshold benchmark")
    p.add_argument("--top-k", type=int, default=ANALYSIS_TOP_K)
    p.add_argument("--device", default=None)
    p.add_argument("--with-rag", action="store_true",
                   help="Also call the LLM on two questions (needs DEEPSEEK_API_KEY in .env).")
    return p.parse_args()


def evaluate(embedder: Embedder, store: VectorStore, questions: dict, top_k: int) -> list[dict]:
    """Retrieve once per question; the sweep then reuses these scores."""
    rows: list[dict] = []
    for label, items in (("positive", questions["positive"]), ("negative", questions["negative"])):
        for item in items:
            outcome = search(
                embedder=embedder,
                store=store,
                query=item["question"],
                top_k=top_k,
                threshold=0.0,  # keep everything; the sweep applies the cut
            )
            hits = outcome.hits
            expected_url = item.get("expected_url")
            expected_rank = None
            if expected_url:
                for rank, hit in enumerate(hits, start=1):
                    if hit.url == expected_url:
                        expected_rank = rank
                        break
            rows.append(
                {
                    "id": item["id"],
                    "label": label,
                    "question": item["question"],
                    "expected_url": expected_url,
                    "expected_rank": expected_rank,
                    "expected_similarity": (
                        hits[expected_rank - 1].similarity if expected_rank else None
                    ),
                    "best_similarity": hits[0].similarity if hits else 0.0,
                    "top_url": hits[0].url if hits else None,
                    "top_title": hits[0].title if hits else None,
                    "similarities": [round(h.similarity, 4) for h in hits],
                }
            )
    return rows


def sweep_thresholds(rows: list[dict]) -> list[dict]:
    """Score the answer/refuse decision at every candidate threshold."""
    positives = [r for r in rows if r["label"] == "positive"]
    negatives = [r for r in rows if r["label"] == "negative"]

    table: list[dict] = []
    for threshold in SWEEP:
        # A positive is answered correctly only if the system both decides to
        # answer AND has the right source document above the cut. That is a
        # stricter (and more honest) success criterion than "did not refuse".
        tp = sum(
            1 for r in positives
            if r["best_similarity"] >= threshold
            and r["expected_similarity"] is not None
            and r["expected_similarity"] >= threshold
        )
        answered_positives = sum(1 for r in positives if r["best_similarity"] >= threshold)
        fn = len(positives) - answered_positives
        fp = sum(1 for r in negatives if r["best_similarity"] >= threshold)
        tn = len(negatives) - fp

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / len(positives) if positives else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        accuracy = (answered_positives + tn) / len(rows)

        table.append(
            {
                "threshold": float(threshold),
                "answered_positives": answered_positives,
                "grounded_positives": tp,
                "missed_positives": fn,
                "false_answers_on_negatives": fp,
                "correct_refusals": tn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "accuracy": round(accuracy, 4),
            }
        )
    return table


def choose_threshold(table: list[dict]) -> tuple[float, dict]:
    """Pick the most robust threshold among those achieving the best F1.

    Several adjacent thresholds usually tie at the optimum. Taking the midpoint
    of the widest tied run keeps the operating point as far as possible from
    both failure modes, instead of sitting on a cliff edge.
    """
    best_f1 = max(row["f1"] for row in table)
    tied = [row["threshold"] for row in table if row["f1"] == best_f1]

    runs: list[list[float]] = []
    current = [tied[0]]
    for value in tied[1:]:
        if round(value - current[-1], 2) <= 0.011:
            current.append(value)
        else:
            runs.append(current)
            current = [value]
    runs.append(current)

    widest = max(runs, key=len)
    chosen = round(float(np.median(widest)), 2)
    row = min(table, key=lambda r: abs(r["threshold"] - chosen))
    return chosen, row


def render_report(rows: list[dict], table: list[dict], chosen: float, chosen_row: dict,
                  stats: dict) -> str:
    lines: list[str] = []
    lines.append("# Eşik Analizi (Threshold Analysis)\n")
    lines.append(f"- Embedding modeli: `{EMBEDDING_MODEL_ID}` (768 boyut, kosinüs)")
    lines.append(f"- Değerlendirme kümesi: {stats['n_positive']} pozitif + {stats['n_negative']} negatif soru")
    lines.append(f"- Seçilen eşik: **{chosen:.2f}**\n")

    lines.append("## Ayrışma (separation)\n")
    lines.append("| Grup | En yüksek benzerlik (ort.) | Min | Maks |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| Pozitif ({stats['n_positive']}) | {stats['pos_mean']:.4f} | "
                 f"{stats['pos_min']:.4f} | {stats['pos_max']:.4f} |")
    lines.append(f"| Negatif ({stats['n_negative']}) | {stats['neg_mean']:.4f} | "
                 f"{stats['neg_min']:.4f} | {stats['neg_max']:.4f} |")
    lines.append("")
    lines.append(f"Ayrışma boşluğu: en düşük pozitif **{stats['pos_min']:.4f}** ile "
                 f"en yüksek negatif **{stats['neg_max']:.4f}** arasında "
                 f"**{stats['gap']:.4f}** fark var.\n")

    lines.append("## Eşik taraması\n")
    lines.append("| Eşik | Yanıtlanan poz. | Doğru kaynakla | Kaçırılan poz. | Negatife yanlış yanıt | F1 | Doğruluk |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    shown = [r for r in table if abs(r["threshold"] * 100 % 5) < 1e-6 or r["threshold"] == chosen]
    for row in shown:
        marker = " **←**" if row["threshold"] == chosen_row["threshold"] else ""
        lines.append(
            f"| {row['threshold']:.2f}{marker} | {row['answered_positives']}/{stats['n_positive']} | "
            f"{row['grounded_positives']}/{stats['n_positive']} | {row['missed_positives']} | "
            f"{row['false_answers_on_negatives']}/{stats['n_negative']} | "
            f"{row['f1']:.3f} | {row['accuracy']:.3f} |"
        )
    lines.append("")

    failures = [r for r in rows if r["label"] == "positive" and r["expected_rank"] is None]
    lines.append("## Kaynak makale geri çağırma (retrieval)\n")
    hit_at_1 = sum(1 for r in rows if r["label"] == "positive" and r["expected_rank"] == 1)
    hit_at_5 = sum(1 for r in rows
                   if r["label"] == "positive" and r["expected_rank"] is not None and r["expected_rank"] <= 5)
    lines.append(f"- Beklenen kaynak ilk sırada: **{hit_at_1}/{stats['n_positive']}**")
    lines.append(f"- Beklenen kaynak ilk 5'te: **{hit_at_5}/{stats['n_positive']}**")
    lines.append(f"- Beklenen kaynak ilk {ANALYSIS_TOP_K}'da bulunamadı: **{len(failures)}**\n")

    lines.append("## Soru bazında en yüksek benzerlik\n")
    lines.append("| ID | Tür | Soru | En yüksek benzerlik | Beklenen kaynak sırası |")
    lines.append("|---|---|---|---:|---:|")
    for row in rows:
        rank = row["expected_rank"] if row["expected_rank"] else ("—" if row["label"] == "negative" else "bulunamadı")
        question = row["question"] if len(row["question"]) <= 62 else row["question"][:59] + "…"
        lines.append(
            f"| {row['id']} | {'poz' if row['label'] == 'positive' else 'neg'} | {question} | "
            f"{row['best_similarity']:.4f} | {rank} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_questions_parquet(questions: dict, rows: list[dict], threshold: float) -> int:
    """Write the 30-question set as one flat table, with measured outcomes.

    One row per question, positives and negatives together, so a reader can see
    the whole evaluation set and how the system actually scored on it without
    cloning the repository.
    """
    import pandas as pd

    by_id = {row["id"]: row for row in rows}
    records: list[dict] = []

    for label, items in (("positive", questions["positive"]), ("negative", questions["negative"])):
        for item in items:
            measured = by_id.get(item["id"], {})
            best = measured.get("best_similarity")
            answered = bool(best is not None and best >= threshold)
            # A positive is correct when the system answers it; a negative is
            # correct when the system refuses.
            correct = answered if label == "positive" else not answered
            records.append(
                {
                    "id": item["id"],
                    "label": label,
                    "question": item["question"],
                    "topic": item.get("topic", ""),
                    "expected_answer": item.get("expected_answer", ""),
                    "expected_url": item.get("expected_url", ""),
                    "rationale": item.get("rationale", ""),
                    "best_similarity": round(float(best), 4) if best is not None else None,
                    "expected_source_rank": measured.get("expected_rank"),
                    "top_match_title": measured.get("top_title") or "",
                    "top_match_url": measured.get("top_url") or "",
                    "threshold": threshold,
                    "system_decision": "answer" if answered else "refuse",
                    "expected_decision": "answer" if label == "positive" else "refuse",
                    "correct": correct,
                }
            )

    frame = pd.DataFrame.from_records(records)
    frame.to_parquet(QUESTIONS_PARQUET_PATH, index=False)
    return len(frame)


def run_rag_probe(embedder: Embedder, store: VectorStore, questions: dict, threshold: float) -> list[dict]:
    """Exercise the generation path once on a positive and once on a negative."""
    from ehekim import llm

    api_key = operator_secrets().get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY yok; RAG denemesi atlanıyor.")
        return []

    probes = [questions["positive"][0], questions["negative"][0]]
    out: list[dict] = []
    for item in probes:
        outcome = search(embedder=embedder, store=store, query=item["question"],
                         top_k=5, threshold=threshold)
        if not outcome.grounded:
            out.append({"id": item["id"], "refused_before_llm": True, "answer": REFUSAL_MESSAGE_TR,
                        "best_similarity": outcome.best_similarity})
            logger.info("[%s] eşiğin altında -> LLM çağrılmadı.", item["id"])
            continue
        # Same path the API uses: expand after the gate, then generate.
        passages = expand_context(store, outcome.hits)
        result = llm.generate(
            model_key=llm.DEFAULT_MODEL_KEY,
            api_key=api_key,
            messages=build_rag_messages(outcome.query, passages),
            timeout=180.0,
        )
        out.append({"id": item["id"], "refused_before_llm": False, "answer": result.content,
                    "model": result.model, "reasoning_tokens": result.reasoning_tokens,
                    "context_passages": len(passages),
                    "best_similarity": outcome.best_similarity})
        logger.info("[%s] yanıt alındı (%s): %s", item["id"], result.model, result.content[:160])
    return out


def main() -> int:
    args = parse_args()
    settings = get_settings()
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    store = VectorStore(settings.chroma_dir, settings.collection_name)
    if store.count() == 0:
        logger.error("Koleksiyon boş. Önce scripts/ingest.py çalıştırın.")
        return 1
    logger.info("Koleksiyon: %s parça", store.count())

    embedder = Embedder(device=args.device, batch_size=16)
    started = time.time()
    rows = evaluate(embedder, store, questions, args.top_k)
    logger.info("%s soru değerlendirildi (%.1fs)", len(rows), time.time() - started)

    pos = np.array([r["best_similarity"] for r in rows if r["label"] == "positive"])
    neg = np.array([r["best_similarity"] for r in rows if r["label"] == "negative"])
    stats = {
        "n_positive": int(len(pos)),
        "n_negative": int(len(neg)),
        "pos_mean": float(pos.mean()), "pos_min": float(pos.min()), "pos_max": float(pos.max()),
        "neg_mean": float(neg.mean()), "neg_min": float(neg.min()), "neg_max": float(neg.max()),
        "gap": float(pos.min() - neg.max()),
    }
    logger.info("Pozitif ort=%.4f min=%.4f | Negatif ort=%.4f maks=%.4f | boşluk=%.4f",
                stats["pos_mean"], stats["pos_min"], stats["neg_mean"], stats["neg_max"], stats["gap"])

    table = sweep_thresholds(rows)
    chosen, chosen_row = choose_threshold(table)
    logger.info("Seçilen eşik: %.2f (F1=%.3f, doğruluk=%.3f, negatife yanlış yanıt=%s)",
                chosen, chosen_row["f1"], chosen_row["accuracy"],
                chosen_row["false_answers_on_negatives"])

    missing = [r["id"] for r in rows if r["label"] == "positive" and r["expected_rank"] is None]
    if missing:
        logger.warning("Beklenen kaynağı ilk %s içinde bulunamayan pozitif sorular: %s",
                       args.top_k, ", ".join(missing))

    rag_probe = run_rag_probe(embedder, store, questions, chosen) if args.with_rag else []

    RESULTS_PATH.write_text(json.dumps(
        {
            "embedding_model": EMBEDDING_MODEL_ID,
            "collection_chunks": store.count(),
            "analysis_top_k": args.top_k,
            "chosen_threshold": chosen,
            "chosen_row": chosen_row,
            "separation": stats,
            "per_question": rows,
            "sweep": table,
            "rag_probe": rag_probe,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_report(rows, table, chosen, chosen_row, stats), encoding="utf-8")
    n_questions = write_questions_parquet(questions, rows, chosen)
    logger.info("Yazıldı: %s, %s ve %s (%s soru)",
                RESULTS_PATH.name, REPORT_PATH.name, QUESTIONS_PARQUET_PATH.name, n_questions)

    correct = sum(
        1 for r in rows
        if (r["label"] == "positive") == (r["best_similarity"] >= chosen)
    )
    logger.info("Değerlendirme kümesi doğruluğu @%.2f: %s/%s", chosen, correct, len(rows))

    if chosen_row["false_answers_on_negatives"] > 0:
        logger.warning("Seçilen eşikte %s negatif soru hâlâ yanıtlanıyor.",
                       chosen_row["false_answers_on_negatives"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
