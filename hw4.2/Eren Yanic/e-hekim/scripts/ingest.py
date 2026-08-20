#!/usr/bin/env python
"""Build the e-hekim vector index.

    uv run python scripts/ingest.py

Pipeline: load the 14 hospital splits -> clean and deduplicate -> select 1,000
articles balanced across sources -> chunk -> embed with the document prompt ->
write to ChromaDB -> export the publishable parquet (url, chunk_text,
chunk_vector, + metadata).

The Hugging Face token is read from ``.env`` and used only to fetch the source
dataset. It is never printed.
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
import pandas as pd

from ehekim.config import (
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    EMBEDDING_MODEL_ID,
    PROJECT_ROOT,
    SOURCE_DATASET_ID,
    TARGET_ARTICLE_COUNT,
    get_settings,
    operator_secrets,
)
from ehekim.corpus import (
    SELECTION_SEED,
    build_chunk_records,
    clean_articles,
    load_raw_articles,
    select_articles,
)
from ehekim.embedding import Embedder
from ehekim.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")

DATA_DIR = PROJECT_ROOT / "data"
PARQUET_PATH = DATA_DIR / "ehekim_chunks.parquet"
MANIFEST_PATH = DATA_DIR / "ingest_manifest.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="e-hekim ingestion")
    p.add_argument("--articles", type=int, default=TARGET_ARTICLE_COUNT,
                   help="Number of articles to select (default: 1000).")
    p.add_argument("--batch-size", type=int, default=16, help="Embedding batch size.")
    p.add_argument("--device", default=None, help="Force a torch device (cuda/cpu).")
    p.add_argument("--seed", type=int, default=SELECTION_SEED)
    p.add_argument("--no-parquet", action="store_true", help="Skip the parquet export.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    started = time.time()

    token = operator_secrets().get("HUGGINGFACE_TOKEN")
    logger.info("Kaynak veri kümesi indiriliyor: %s", SOURCE_DATASET_ID)
    raw = load_raw_articles(SOURCE_DATASET_ID, token=token)
    logger.info("Ham makale sayısı: %s", len(raw))

    cleaned = clean_articles(raw)
    logger.info("Temizleme sonrası: %s makale", len(cleaned))

    selected = select_articles(cleaned, target=args.articles, seed=args.seed)
    per_source = selected.groupby("source").size().to_dict()
    logger.info("Seçilen makale: %s | kaynak dağılımı: %s", len(selected), per_source)

    logger.info("Embedding modeli yükleniyor: %s", EMBEDDING_MODEL_ID)
    embedder = Embedder(device=args.device, batch_size=args.batch_size)

    logger.info("Parçalama başlıyor (hedef=%s, örtüşme=%s token)",
                CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS)
    t0 = time.time()
    records = build_chunk_records(selected, embedder.tokenizer)
    if not records:
        logger.error("Hiç parça üretilemedi.")
        return 1
    token_counts = np.array([r.token_count for r in records])
    logger.info(
        "%s parça üretildi (%.1fs) | token ort=%.1f medyan=%s min=%s maks=%s",
        len(records), time.time() - t0, token_counts.mean(),
        int(np.median(token_counts)), token_counts.min(), token_counts.max(),
    )

    logger.info("Vektörler hesaplanıyor (%s)...", embedder.device)
    t0 = time.time()
    vectors = embedder.encode_documents(
        [r.chunk_text for r in records],
        titles=[r.title for r in records],
        show_progress=True,
    )
    logger.info("Embedding tamamlandı: %s vektör, %.1fs", vectors.shape[0], time.time() - t0)

    if vectors.shape[1] != embedder.dimension:
        logger.error("Beklenmeyen vektör boyutu: %s", vectors.shape[1])
        return 1

    logger.info("ChromaDB koleksiyonu yeniden oluşturuluyor: %s", settings.collection_name)
    store = VectorStore(settings.chroma_dir, settings.collection_name)
    store.recreate()
    store.add(
        ids=[r.chunk_id for r in records],
        embeddings=vectors,
        documents=[r.chunk_text for r in records],
        metadatas=[r.metadata() for r in records],
    )
    indexed = store.count()
    logger.info("Dizine eklendi: %s parça", indexed)
    if indexed != len(records):
        logger.error("Dizin sayısı uyuşmuyor: %s != %s", indexed, len(records))
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_parquet:
        # Column order matches the delivery schema: url, chunk_text, chunk_vector
        # first, optional metadata after.
        frame = pd.DataFrame(
            {
                "url": [r.url for r in records],
                "chunk_text": [r.chunk_text for r in records],
                "chunk_vector": [v.astype(np.float32).tolist() for v in vectors],
                "chunk_id": [r.chunk_id for r in records],
                "parent_id": [r.parent_id for r in records],
                "title": [r.title for r in records],
                "__source": [r.source for r in records],
                "chunk_index": [r.chunk_index for r in records],
                "token_count": [r.token_count for r in records],
            }
        )
        frame.to_parquet(PARQUET_PATH, index=False)
        size_mb = PARQUET_PATH.stat().st_size / 1e6
        logger.info("Parquet yazıldı: %s (%.1f MB)", PARQUET_PATH, size_mb)

    manifest = {
        "source_dataset": SOURCE_DATASET_ID,
        "embedding_model": EMBEDDING_MODEL_ID,
        "embedding_dim": int(vectors.shape[1]),
        "selection_seed": args.seed,
        "raw_articles": int(len(raw)),
        "cleaned_articles": int(len(cleaned)),
        "selected_articles": int(len(selected)),
        "articles_per_source": {k: int(v) for k, v in per_source.items()},
        "chunks": len(records),
        "chunk_target_tokens": CHUNK_TARGET_TOKENS,
        "chunk_overlap_tokens": CHUNK_OVERLAP_TOKENS,
        "chunk_min_tokens": CHUNK_MIN_TOKENS,
        "token_stats": {
            "mean": float(token_counts.mean()),
            "median": float(np.median(token_counts)),
            "p95": float(np.percentile(token_counts, 95)),
            "min": int(token_counts.min()),
            "max": int(token_counts.max()),
        },
        "chunks_per_article": round(len(records) / max(1, len(selected)), 2),
        "collection": settings.collection_name,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Manifest yazıldı: %s", MANIFEST_PATH)
    logger.info("Bitti (%.1fs).", time.time() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
