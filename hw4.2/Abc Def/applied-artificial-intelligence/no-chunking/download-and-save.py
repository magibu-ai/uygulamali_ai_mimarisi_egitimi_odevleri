import itertools

import psycopg2
from datasets import load_dataset
from huggingface_hub import login
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

# Get dataset
login(token="")

streamed_dataset = load_dataset("umutertugrul/turkish-hospital-medical-articles", streaming=True)
raw_stream = next(iter(streamed_dataset.values()))
data_list = list(itertools.islice(raw_stream, 100))
print(f"Successfully retrieved {len(data_list)}.")

if len(data_list) == 0:
    print("Error - No data received")
    exit(1)

model = SentenceTransformer(
    "alibayram/embeddingmagibu-200m",
    trust_remote_code=True
)

with psycopg2.connect(dbname="pc", user="pc", password="", host="localhost", port="5432") as conn:
    register_vector(conn)
    cur = conn.cursor()
    insert_query = "INSERT INTO medical_data_wout_chunk (url, chunk_text, chunk_vector) VALUES (%s, %s, %s);"

    for data in data_list:
        chunk = data['text']
        embeddings = model.encode(chunk, normalize_embeddings=True)

        cur.execute(insert_query, (data['url'], chunk, embeddings))

        conn.commit()