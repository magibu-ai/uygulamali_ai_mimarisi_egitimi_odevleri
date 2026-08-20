"""Vector search with a cosine-similarity threshold gate.

A query is embedded with the *query* prompt and compared against the stored
chunk vectors (cosine similarity). If the best match scores below
``SIMILARITY_THRESHOLD`` the system refuses instead of returning a (possibly
irrelevant) chunk — this is what stops the downstream LLM from hallucinating an
answer to an out-of-scope question.

CLI:  python src/search.py "sorunuz" [--threshold 0.5] [--k 5]
"""
import argparse
from dataclasses import dataclass, field
from typing import List, Optional

import config as C


@dataclass
class Hit:
    chunk_id: str
    url: str
    title: str
    similarity: float
    text: str


@dataclass
class SearchResult:
    query: str
    answered: bool
    top_similarity: float
    threshold: float
    hits: List[Hit] = field(default_factory=list)
    message: Optional[str] = None  # set to the refusal text when answered is False


_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=str(C.CHROMA_DIR))
        _collection = client.get_collection(C.COLLECTION_NAME)
    return _collection


def search(
    query: str,
    k: int = C.TOP_K,
    threshold: float = C.SIMILARITY_THRESHOLD,
) -> SearchResult:
    from embedder import embed_query

    qvec = embed_query(query)
    res = _get_collection().query(
        query_embeddings=[qvec.tolist()],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    hits: List[Hit] = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        # Chroma cosine distance == 1 - cosine_similarity.
        sim = 1.0 - float(dist)
        hits.append(
            Hit(
                chunk_id=meta.get("parent_id", ""),
                url=meta.get("url", ""),
                title=meta.get("title", ""),
                similarity=sim,
                text=doc,
            )
        )

    top_sim = hits[0].similarity if hits else 0.0
    answered = top_sim >= threshold
    return SearchResult(
        query=query,
        answered=answered,
        top_similarity=top_sim,
        threshold=threshold,
        hits=hits if answered else [],
        message=None if answered else C.REFUSAL_MESSAGE,
    )


def _cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--threshold", type=float, default=C.SIMILARITY_THRESHOLD)
    ap.add_argument("--k", type=int, default=C.TOP_K)
    args = ap.parse_args()

    r = search(args.query, k=args.k, threshold=args.threshold)
    print(f"\nSoru: {r.query}")
    print(f"En yüksek benzerlik: {r.top_similarity:.3f}  (eşik: {r.threshold})")
    if not r.answered:
        print(f"\n>> {r.message}")
        return
    print(f"\nBulunan {len(r.hits)} parça:\n")
    for i, h in enumerate(r.hits, 1):
        print(f"[{i}] sim={h.similarity:.3f}  {h.title}")
        print(f"    {h.url}")
        print(f"    {h.text[:200]}...\n")


if __name__ == "__main__":
    _cli()
