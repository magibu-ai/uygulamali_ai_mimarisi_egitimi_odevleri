"""HF'deki embedding'li Wikipedia TR 2023 dump'ını indirip Postgres'teki documents/document_chunks tablolarına toplu olarak yükleyen script."""

import os
import sys

import psycopg2
import psycopg2.extras
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE = 1000

DSN = dict(
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5433"),
    dbname=os.environ.get("POSTGRES_DB", "knowledge_graph"),
    user=os.environ.get("POSTGRES_USER", "kg"),
    password=os.environ.get("POSTGRES_PASSWORD", "kg"),
)

DOC_SQL = "INSERT INTO documents (id, title, source_url) VALUES %s ON CONFLICT (id) DO NOTHING"

CHUNK_SQL = """
    INSERT INTO document_chunks
        (id, document_id, chunk_type, parent_chunk_id, ordinal, text,
         char_start, char_end, token_count, embedding)
    VALUES %s
    ON CONFLICT (id) DO NOTHING
"""
CHUNK_TEMPLATE = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)"


def _vector_literal(embedding):
    if embedding is None:
        return None
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def _flush(cur, doc_batch, chunk_batch):
    if doc_batch:
        psycopg2.extras.execute_values(cur, DOC_SQL, doc_batch)
    if chunk_batch:
        psycopg2.extras.execute_values(cur, CHUNK_SQL, chunk_batch, template=CHUNK_TEMPLATE)


def load(hf_repo: str, limit: int | None = None):
    ds = load_dataset(hf_repo, split="train", streaming=True)
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    doc_batch, chunk_batch, seen_docs = [], [], set()
    total = 0

    for row in ds:
        if row["document_id"] not in seen_docs:
            seen_docs.add(row["document_id"])
            doc_batch.append((row["document_id"], row["title"], row["wikipedia_url"]))

        chunk_batch.append(
            (
                row["chunk_id"],
                row["document_id"],
                row["chunk_type"],
                row["parent_chunk_id"],
                row["ordinal"],
                row["text"],
                row.get("char_start"),
                row.get("char_end"),
                row.get("token_count"),
                _vector_literal(row.get("embedding")),
            )
        )

        if len(chunk_batch) >= BATCH_SIZE:
            _flush(cur, doc_batch, chunk_batch)
            conn.commit()
            total += len(chunk_batch)
            print(f"  {total} chunk yüklendi...")
            doc_batch, chunk_batch = [], []

        if limit and total + len(chunk_batch) >= limit:
            break

    _flush(cur, doc_batch, chunk_batch)
    conn.commit()
    total += len(chunk_batch)

    cur.close()
    conn.close()
    print(f"Bitti: {total} chunk, {len(seen_docs)} makale yüklendi.")


if __name__ == "__main__":
    repo = os.environ.get("HF_DATASET_REPO")
    if not repo:
        sys.exit(
            "HF_DATASET_REPO tanımlı değil. Dataset Hugging Face'e yüklendikten sonra "
            "repo id'sini .env dosyasına ekleyin (bkz. .env.example)."
        )
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    load(repo, limit=n)
