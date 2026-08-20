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
            FROM medical_data_sentence_chunk
            WHERE 1 - (chunk_vector <=> %s) >= %s
            ORDER BY similarity DESC;
         """
    cur.execute(query, (question_vector, question_vector, cutoff_similarity))

    rows = cur.fetchall()
    url_set = set()
    for row in rows:
        url = row[0]
        if url not in url_set:
            print(f"Url: {url}, Similarity: {row[2]:.4f}, Text: {row[1][:10]}...")
            url_set.add(url)

