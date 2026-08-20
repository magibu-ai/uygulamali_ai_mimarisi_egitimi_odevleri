import sys
import logging
from typing import List
from datasets import load_dataset, get_dataset_split_names
from ollama_embedder import OllamaEmbedder
from vector_db import LocalVectorDB
from semantic_chunker import SemanticChunker

# Ensure UTF-8 console output reconfiguration for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATASET_NAME = "alibayram/turkish-hospital-medical-articles"

def ingest_hf_dataset(limit: int = 20, reset_db: bool = False):
    """
    Fetches articles from Hugging Face dataset ('alibayram/turkish-hospital-medical-articles'),
    applies Semantic Chunking, generates 768d Ollama embeddings, and persists them into ChromaDB.
    """
    print("=" * 70)
    print(f" Hugging Face Dataset Ingestion: '{DATASET_NAME}' ")
    print("=" * 70)

    # 1. Initialize services
    embedder = OllamaEmbedder(batch_size=32, timeout=120)
    vector_db = LocalVectorDB()
    semantic_chunker = SemanticChunker(embedder=embedder)

    if reset_db:
        print("\n[!] Resetting ChromaDB collection...")
        vector_db.reset()

    # 2. Get available dataset splits
    try:
        splits = get_dataset_split_names(DATASET_NAME)
        logger.info(f"Available hospital dataset splits: {splits}")
    except Exception as e:
        logger.warning(f"Failed to retrieve split names, using fallback list: {e}")
        splits = ['acibadem', 'medicana', 'memorial', 'medipol', 'medicalpark', 'florence']

    processed_articles = 0
    skipped_articles = 0
    failed_articles = 0
    all_chunks_to_insert = []

    print(f"\n[1] Fetching {limit} articles from Hugging Face & applying Semantic Chunking...\n")

    for split_name in splits:
        if processed_articles >= limit:
            break

        logger.info(f"--- Processing hospital split: '{split_name}' ---")
        try:
            ds = load_dataset(DATASET_NAME, split=split_name, streaming=True)
        except Exception as e:
            logger.warning(f"Failed to load split '{split_name}': {e}")
            continue

        for item in ds:
            if processed_articles >= limit:
                break

            url = item.get("url", "")
            title = str(item.get("title", "") or "").strip()
            
            # Robust content column key retrieval (content, article, text)
            raw_content = item.get("content") or item.get("article") or item.get("text") or ""
            article_text = str(raw_content).strip()

            # Skip empty or short texts
            if not article_text or len(article_text) < 100:
                skipped_articles += 1
                continue

            processed_articles += 1
            full_text = f"{title}\n{article_text}" if title else article_text

            logger.info(f"[{processed_articles}/{limit}] ({split_name}) Processing article: '{title[:45]}...'")

            try:
                # Apply Semantic Chunking
                chunks = semantic_chunker.chunk_document(full_text, url=url)
                all_chunks_to_insert.extend(chunks)
            except Exception as err:
                logger.error(f"Error processing article '{title[:30]}': {err}")
                failed_articles += 1
                continue

            # Batch insert every ~25 chunks
            if len(all_chunks_to_insert) >= 25:
                vector_db.add_chunks_batch(all_chunks_to_insert)
                logger.info(f"   [+] Persisted {len(all_chunks_to_insert)} chunks to ChromaDB.")
                all_chunks_to_insert = []

    # Insert remaining chunks
    if all_chunks_to_insert:
        vector_db.add_chunks_batch(all_chunks_to_insert)
        logger.info(f"   [+] Persisted remaining {len(all_chunks_to_insert)} chunks to ChromaDB.")

    print("\n" + "=" * 70)
    print(" [OK] INGESTION COMPLETED ")
    print("=" * 70)
    print(f" • Processed Articles Count : {processed_articles}")
    print(f" • Failed/Error Articles    : {failed_articles}")
    print(f" • Skipped Short Articles   : {skipped_articles}")
    print(f" • Total Vector DB Count    : {vector_db.count()}")
    print("=" * 70)

if __name__ == "__main__":
    ingest_hf_dataset(limit=20, reset_db=False)
