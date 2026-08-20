-- Wikipedia-TR-2023-Embedded-Dump için minimal, bağımsız şema.
-- db.py'nin sorguladığı documents/document_chunks tablolarının sadece bu
-- ödev için gereken kolonlarını içerir (asıl knowledge_graph uygulamasının
-- workspace/user tabloları burada yok — tek başına ayağa kalkması için).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

CREATE TABLE documents (
    id          UUID PRIMARY KEY,
    title       VARCHAR(255),
    source_url  TEXT
);

CREATE TABLE document_chunks (
    id               UUID PRIMARY KEY,
    document_id      UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_type       VARCHAR(20) NOT NULL,
    parent_chunk_id  UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    ordinal          INTEGER NOT NULL,
    text             TEXT NOT NULL,
    char_start       INTEGER,
    char_end         INTEGER,
    token_count      INTEGER,
    embedding        VECTOR(1024)
);

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);
CREATE INDEX ix_document_chunks_parent_chunk_id ON document_chunks (parent_chunk_id);

-- Dense arama: sadece child chunk'lar embedding taşır, retrieval hedefi bunlardır.
CREATE INDEX document_chunks_embedding_hnsw_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE chunk_type = 'child';

-- Sparse arama: ParadeDB BM25 tam metin indeksi.
CREATE INDEX document_chunks_bm25_idx
    ON document_chunks USING bm25 (id, text)
    WITH (key_field = 'id');
