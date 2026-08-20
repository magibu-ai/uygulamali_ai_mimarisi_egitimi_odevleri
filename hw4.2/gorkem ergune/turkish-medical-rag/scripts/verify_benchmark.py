"""Phase 5 audit: semantic verification of the benchmark via ChromaDB.

Positives: confirm the expected chunk (or its parent doc) is retrieved near the
top. Negatives: retrieve top-5 and print them for manual confirmation that no
retrieved chunk actually answers the question.

Writes artifacts/benchmark_verification.json (gitignored) and prints a report.
Does NOT modify the benchmark.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import load_config, resolve_path  # noqa: E402
from src.embeddings.embedder import Embedder  # noqa: E402
from src.vectorstore.chroma_store import ChromaStore  # noqa: E402

TOP_K = 10


def main() -> None:
    config = load_config()
    bench = json.loads(
        (resolve_path(config["paths"]["data_benchmark"]) / "benchmark.json")
        .read_text(encoding="utf-8")
    )
    embedder = Embedder.from_config(config).load()
    store = ChromaStore.from_config(config).connect(fresh=False)

    report = []
    print("\n===== POSITIVES (expected chunk retrieval) =====")
    pos_ok = 0
    for q in [x for x in bench["questions"] if x["type"] == "positive"]:
        emb = embedder.encode_queries([q["question"]])[0]
        results = store.search(emb, top_k=TOP_K)
        ids = [r["chunk_id"] for r in results]
        parents = [r["parent_id"] for r in results]
        exp_chunk = q["expected_chunk_ids"][0]
        exp_parent = q["expected_parent_ids"][0]
        chunk_rank = ids.index(exp_chunk) + 1 if exp_chunk in ids else None
        parent_rank = parents.index(exp_parent) + 1 if exp_parent in parents else None
        ok = parent_rank is not None and parent_rank <= 5
        pos_ok += ok
        print(f"  {q['id']} chunk_rank={chunk_rank} parent_rank={parent_rank} "
              f"top1_sim={results[0]['similarity']:.3f} | {q['question'][:45]}")
        report.append({"id": q["id"], "type": "positive", "chunk_rank": chunk_rank,
                       "parent_rank": parent_rank,
                       "top1_similarity": round(results[0]["similarity"], 4)})

    print(f"\npositives with expected doc in top-5: {pos_ok}/20")

    print("\n===== NEGATIVES (top-5 — must NOT answer) =====")
    for q in [x for x in bench["questions"] if x["type"] == "negative"]:
        emb = embedder.encode_queries([q["question"]])[0]
        results = store.search(emb, top_k=5)
        print(f"\n  {q['id']} [{q['target_topic']}] top1_sim={results[0]['similarity']:.3f}")
        print(f"    Q: {q['question']}")
        for r in results:
            print(f"      sim={r['similarity']:.3f} [{r['source']}] {r['title'][:55]}")
        report.append({"id": q["id"], "type": "negative",
                       "target_topic": q["target_topic"],
                       "top1_similarity": round(results[0]["similarity"], 4),
                       "top5": [{"chunk_id": r["chunk_id"], "title": r["title"],
                                 "similarity": round(r["similarity"], 4)} for r in results]})

    out = resolve_path("artifacts/benchmark_verification.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
