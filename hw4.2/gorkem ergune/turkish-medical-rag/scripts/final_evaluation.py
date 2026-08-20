"""Phase 8: final evaluation of the frozen benchmark through the full pipeline.

Runs all 30 official benchmark questions through the REAL retrieval pipeline
(E5 query embedding -> ChromaDB cosine top-k -> threshold gate at the frozen
0.575) and the RAG pipeline with a FakeLLMClient for STRUCTURAL verification
(no LLM API call). Deterministic retrieval/gate metrics are computed from the
real similarities. Existing per-phase artifacts are read as the source of truth.

Nothing is recalibrated or modified. Writes artifacts/final_evaluation.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import Embedder  # noqa: E402
from src.evaluation.threshold import confusion_at_threshold, distribution_stats  # noqa: E402
from src.rag.llm import FakeLLMClient  # noqa: E402
from src.rag.pipeline import RAGPipeline  # noqa: E402
from src.vectorstore.chroma_store import ChromaStore  # noqa: E402


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    config = load_config()
    art = resolve_path(config["paths"]["artifacts"])

    bench = _read_json(
        resolve_path(config["paths"]["data_benchmark"]) / "benchmark.json"
    )
    ds_stats = _read_json(art / "dataset_statistics.json")
    chunk_stats = _read_json(art / "chunk_statistics.json")
    emb_stats = _read_json(art / "embedding_statistics.json")
    thr_stats = _read_json(art / "threshold_analysis.json")

    threshold = config["retrieval"]["threshold"]
    top_k = config["retrieval"]["top_k"]

    embedder = Embedder.from_config(config).load()
    store = ChromaStore.from_config(config).connect(fresh=False)
    # Structural only: a FakeLLMClient is used regardless of config provider so
    # no API call is made. Results are labeled structural/offline.
    pipeline = RAGPipeline(
        embedder=embedder, store=store, llm=FakeLLMClient(),
        threshold=threshold, top_k=top_k,
        rejection_message=config["rejection_message"],
        max_context_chars=config["rag"]["max_context_chars"],
    )

    pos_top1, neg_top1 = [], []
    parent_rank1 = evidence_top5 = 0
    per_question = []
    struct_accepted_have_sources = struct_accepted_llm_called = 0
    struct_rejected_no_llm = struct_rejected_exact_msg = 0

    for q in bench["questions"]:
        # real retrieval for rank/evidence checks
        emb = embedder.encode_queries([q["question"]])[0]
        hits = store.search(emb, top_k=top_k)
        top5_ids = [h["chunk_id"] for h in hits]
        top5_parents = [h["parent_id"] for h in hits]
        top1 = float(hits[0]["similarity"])

        # structural RAG pass (fake LLM, no API)
        res = pipeline.answer(q["question"])

        rec = {"id": q["id"], "type": q["type"], "top1_similarity": round(top1, 4),
               "accepted": res["accepted"], "llm_called": res["llm_called"]}

        if q["type"] == "positive":
            pos_top1.append(top1)
            exp_chunk = q["expected_chunk_ids"][0]
            exp_parent = q["expected_parent_ids"][0]
            p1 = top5_parents[0] == exp_parent
            e5 = exp_chunk in top5_ids
            parent_rank1 += p1
            evidence_top5 += e5
            rec.update({"expected_parent_rank1": p1, "expected_evidence_in_top5": e5})
            if res["accepted"]:
                struct_accepted_have_sources += bool(res["sources"])
                struct_accepted_llm_called += bool(res["llm_called"])
        else:
            neg_top1.append(top1)
            if not res["accepted"]:
                struct_rejected_no_llm += (res["llm_called"] is False)
                struct_rejected_exact_msg += (res["answer"] == config["rejection_message"])
        per_question.append(rec)

    gate = confusion_at_threshold(pos_top1, neg_top1, threshold)
    n_pos, n_neg = len(pos_top1), len(neg_top1)

    final = {
        "generated_by": "scripts/final_evaluation.py (Phase 8)",
        "dataset": {
            "dataset_name": ds_stats["dataset_name"],
            "total_source_documents": ds_stats["total_source_documents"],
            "valid_unique_documents": ds_stats["valid_unique_documents"],
            "selected_documents": ds_stats["selected_documents"],
            "chunks": chunk_stats["chunk_count"],
            "seed": ds_stats["seed"],
            "splits": len(ds_stats["splits"]),
        },
        "embedding": {
            "model": emb_stats["model_name"],
            "revision": emb_stats["model_revision"],
            "dimension": emb_stats["embedding_dim"],
            "normalization": emb_stats["normalize"],
            "device": emb_stats["device"],
        },
        "retrieval": {
            "top_k": top_k,
            "similarity_metric": "cosine (similarity = 1 - chroma_distance)",
            "threshold": threshold,
        },
        "benchmark": {"total": n_pos + n_neg, "positive": n_pos, "negative": n_neg},
        "retrieval_metrics": {
            "positive_expected_parent_rank1_rate": round(parent_rank1 / n_pos, 4),
            "positive_expected_chunk_top5_rate": round(evidence_top5 / n_pos, 4),
            "positive_expected_parent_rank1_count": parent_rank1,
            "positive_expected_chunk_top5_count": evidence_top5,
        },
        "gate_metrics": {k: gate[k] for k in (
            "tp", "tn", "fp", "fn", "accuracy", "precision", "recall",
            "specificity", "f1", "false_acceptance_rate", "false_rejection_rate")},
        "score_statistics": {
            "positive_top1": distribution_stats(pos_top1),
            "negative_top1": distribution_stats(neg_top1),
        },
        "threshold": {
            "value": threshold,
            "calibration_source": "Phase 6 — frozen 30-question benchmark (top-1 cosine)",
            "separation_margin_min_pos_minus_max_neg": thr_stats[
                "min_positive_minus_max_negative_margin"],
            "separable": thr_stats["selection"]["separable"],
            "robustness_perfect_band": ["0.57", "0.58"],
            "robustness_neighbors": thr_stats["robustness_neighbors"],
        },
        "rag_answer_evaluation": {
            "mode": "structural/offline (FakeLLMClient — NO real LLM API call)",
            "llm_provider_configured": config["llm"]["provider"],
            "real_llm_api_used": False,
            "note": (
                "No ANTHROPIC_API_KEY available; per Phase 8 rules the RAG answer "
                "layer is verified structurally only. FakeLLM results are NOT "
                "substituted for real LLM answers."
            ),
            "accepted_positives_with_sources": struct_accepted_have_sources,
            "accepted_positives_llm_called": struct_accepted_llm_called,
            "rejected_negatives_no_llm_call": struct_rejected_no_llm,
            "rejected_negatives_exact_message": struct_rejected_exact_msg,
        },
        "limitations": [
            "Threshold calibrated on only 30 benchmark questions (no held-out set).",
            "Narrow separation margin of 0.0161 (min positive 0.583 vs max negative 0.567).",
            "Negatives are relatively easy, clean out-of-domain topics.",
            "No independent held-out validation of the threshold.",
            "Retrieval gate uses top-1 cosine similarity only.",
            "CPU / model-version numerical variation (~1e-6).",
            "Not medically validated.",
            "Real LLM answer evaluation depends on external API availability (absent here).",
        ],
        "per_question": per_question,
    }

    out = art / "final_evaluation.json"
    out.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"gate: TP={gate['tp']} TN={gate['tn']} FP={gate['fp']} FN={gate['fn']} "
          f"acc={gate['accuracy']} f1={gate['f1']}")
    print(f"positive parent_rank1: {parent_rank1}/{n_pos} | evidence_top5: {evidence_top5}/{n_pos}")
    print(f"structural RAG: accepted+sources={struct_accepted_have_sources}, "
          f"rejected+no_llm={struct_rejected_no_llm}")


if __name__ == "__main__":
    main()
