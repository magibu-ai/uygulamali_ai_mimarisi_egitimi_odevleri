"""Postgres/pgvector/ParadeDB üzerinden dense ve sparse chunk aramasını yapan erişim katmanı; füzyon ve child→parent genişletme rag.py'de yapılır."""

import os

import psycopg2
import psycopg2.extras

_POOL_DSN = dict(
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5433"),
    dbname=os.environ.get("POSTGRES_DB", "knowledge_graph"),
    user=os.environ.get("POSTGRES_USER", "kg"),
    password=os.environ.get("POSTGRES_PASSWORD", "kg"),
)


def get_connection():
    return psycopg2.connect(**_POOL_DSN)


def dense_search(query_vector, k=15):
    """Cosine benzerliğine göre en yakın child chunk'ları döner."""
    vector_literal = "[" + ",".join(f"{x:.8f}" for x in query_vector) + "]"
    sql = """
        SELECT id, document_id, parent_chunk_id, text,
               1 - (embedding <=> %s::vector) AS score
        FROM document_chunks
        WHERE chunk_type = 'child'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (vector_literal, vector_literal, k))
        return cur.fetchall()


def sparse_search(query_text, k=15):
    """ParadeDB BM25 ile en alakalı child chunk'ları döner."""
    sql = """
        SELECT id, document_id, parent_chunk_id, text, paradedb.score(id) AS score
        FROM document_chunks
        WHERE text @@@ paradedb.match('text', %s) AND chunk_type = 'child'
        ORDER BY score DESC
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (query_text, k))
        return cur.fetchall()


def get_parent_chunks(parent_chunk_ids):
    """parent_chunk_id -> {"text": ..., "document_id": ...} eşlemesi döner."""
    ids = list({pid for pid in parent_chunk_ids if pid})
    if not ids:
        return {}
    sql = "SELECT id, document_id, text FROM document_chunks WHERE id = ANY(%s::uuid[])"
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (ids,))
        return {row["id"]: row for row in cur.fetchall()}


def get_documents(document_ids):
    """document_id -> {"title": ..., "source_url": ...} eşlemesi döner."""
    ids = list({did for did in document_ids if did})
    if not ids:
        return {}
    sql = "SELECT id, title, source_url FROM documents WHERE id = ANY(%s::uuid[])"
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (ids,))
        return {row["id"]: row for row in cur.fetchall()}
