"""Build the vector index.

Pipeline: load Acibadem articles -> sample -> chunk -> embed -> store in
ChromaDB and export a Hugging Face-ready parquet (url, chunk_text, chunk_vector,
plus parent/meta columns).

Run:  python src/build_index.py
"""
import hashlib
import shutil

import pandas as pd

import config as C
from chunking import chunk_text
from embedder import embed_documents, get_tokenizer


def _load_articles() -> pd.DataFrame:
    src = f"hf://datasets/{C.DATASET_REPO}/{C.HOSPITAL_FILE}"
    print(f"Loading {src} ...")
    df = pd.read_parquet(src)
    df = df[["url", "title", "text"]].copy()
    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.len() >= C.MIN_ARTICLE_CHARS]
    df = df.dropna(subset=["url", "text"]).drop_duplicates(subset=["url"])
    print(f"  {len(df)} eligible articles (>= {C.MIN_ARTICLE_CHARS} chars)")
    sampled = df.sample(n=min(C.N_ARTICLES, len(df)), random_state=C.RANDOM_SEED)
    sampled = sampled.reset_index(drop=True)
    print(f"  sampled {len(sampled)} articles (seed={C.RANDOM_SEED})")
    return sampled


def _parent_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def build_chunks(articles: pd.DataFrame) -> pd.DataFrame:
    count_tokens = get_tokenizer()
    rows = []
    for _, art in articles.iterrows():
        pid = _parent_id(art["url"])
        pieces = chunk_text(
            art["text"],
            count_tokens,
            max_tokens=C.MAX_TOKENS_PER_CHUNK,
            overlap_tokens=C.CHUNK_OVERLAP_TOKENS,
            min_tokens=C.MIN_CHUNK_TOKENS,
        )
        for i, piece in enumerate(pieces):
            rows.append(
                {
                    "chunk_id": f"{pid}_{i:03d}",
                    "parent_id": pid,
                    "url": art["url"],
                    "title": art["title"],
                    "__source": C.SOURCE_NAME,
                    "chunk_index": i,
                    "n_tokens": count_tokens(piece),
                    "chunk_text": piece,
                }
            )
    chunks = pd.DataFrame(rows)
    print(
        f"  {len(chunks)} chunks from {articles.shape[0]} articles "
        f"(avg {len(chunks)/max(1,articles.shape[0]):.1f} chunks/article, "
        f"avg {chunks['n_tokens'].mean():.0f} tokens/chunk)"
    )
    return chunks


def embed_and_store(chunks: pd.DataFrame) -> pd.DataFrame:
    import chromadb

    texts = chunks["chunk_text"].tolist()
    print(f"Embedding {len(texts)} chunks with {C.EMBED_MODEL} ...")
    vectors = embed_documents(texts)
    assert vectors.shape[1] == C.EMBED_DIM, vectors.shape
    chunks = chunks.copy()
    chunks["chunk_vector"] = [v.tolist() for v in vectors]

    # --- ChromaDB (rebuild fresh) ---
    if C.CHROMA_DIR.exists():
        shutil.rmtree(C.CHROMA_DIR)
    client = chromadb.PersistentClient(path=str(C.CHROMA_DIR))
    coll = client.create_collection(
        name=C.COLLECTION_NAME, metadata={"hnsw:space": C.DISTANCE_SPACE}
    )
    B = 512
    for s in range(0, len(chunks), B):
        part = chunks.iloc[s : s + B]
        coll.add(
            ids=part["chunk_id"].tolist(),
            embeddings=[v for v in vectors[s : s + B]],
            documents=part["chunk_text"].tolist(),
            metadatas=[
                {
                    "url": rec["url"],
                    "title": rec["title"],
                    "parent_id": rec["parent_id"],
                    "__source": rec["__source"],
                    "chunk_index": int(rec["chunk_index"]),
                }
                for rec in part.to_dict("records")
            ],
        )
    print(f"  stored {coll.count()} vectors in ChromaDB ({C.CHROMA_DIR})")
    return chunks


def main():
    C.DATA_DIR.mkdir(exist_ok=True)
    articles = _load_articles()
    chunks = build_chunks(articles)
    chunks = embed_and_store(chunks)

    out_cols = [
        "chunk_id", "parent_id", "url", "title", "__source",
        "chunk_index", "n_tokens", "chunk_text", "chunk_vector",
    ]
    chunks[out_cols].to_parquet(C.CHUNKS_PARQUET, index=False)
    print(f"  wrote {C.CHUNKS_PARQUET} ({len(chunks)} rows)")
    print("Done.")


if __name__ == "__main__":
    main()
