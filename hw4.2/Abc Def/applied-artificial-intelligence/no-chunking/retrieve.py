import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer


model = SentenceTransformer(
    "alibayram/embeddingmagibu-200m",
    trust_remote_code=True
)

question_vector = model.encode("Pil nedir?", normalize_embeddings=True)
cutoff_similarity = 0.5

with psycopg2.connect(dbname="pc", user="pc", password="", host="localhost", port="5432") as conn:
    register_vector(conn)
    cur = conn.cursor()

    query = """
            SELECT url, chunk_text,  1 - (chunk_vector <=> %s) AS similarity
            FROM medical_data_wout_chunk
            WHERE 1 - (chunk_vector <=> %s) >= %s
            ORDER BY similarity DESC;
         """
    cur.execute(query, (question_vector, question_vector, cutoff_similarity))

    rows = cur.fetchall()
    for row in rows:
        print(f"Url: {row[0]}, Similarity: {row[2]:.4f}, Text: {row[1][:10]}...")
