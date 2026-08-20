import itertools

import psycopg2
from datasets import load_dataset
from huggingface_hub import login
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import nltk
import ssl
import numpy as np

# SSL'i kapat
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Türkçe cümle bölücü için gerekli veriyi indirin (İlk kullanımda zorunludur)
nltk.download('punkt')
nltk.download('punkt_tab')  # Güncel nltk sürümleri için gereklidir

model_name = "alibayram/embeddingmagibu-200m"
model = SentenceTransformer(
    model_name,
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def get_chunk_list(txt):
    sentences = nltk.tokenize.sent_tokenize(txt, language='turkish')
    sentences = [s.strip() for s in sentences if s.strip()]

    embeddings = model.encode(sentences)

    # 5. Calculate cosine distances between consecutive sentences
    distances = []
    for i in range(len(embeddings) - 1):
        # Compute similarity matrix for consecutive pairs
        sim = model.similarity(embeddings[i], embeddings[i + 1]).item()
        # Convert similarity score to a distance metric
        distances.append(1 - sim)

    # 6. Establish a breakpoint threshold (e.g., 85th percentile of distances)
    threshold_percentile = 85
    breakpoint_threshold = np.percentile(distances, threshold_percentile)

    # 7. Group the sentences into semantically cohesive chunks
    chunks = []
    current_chunk = [sentences[0]]

    for i, distance in enumerate(distances):
        if distance > breakpoint_threshold:
            # High distance indicates a topic shift; start a new chunk
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i + 1]]
        else:
            # Low distance indicates continuous context; append to current chunk
            current_chunk.append(sentences[i + 1])

    # Append the last remaining chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

# Get dataset
login(token="")

streamed_dataset = load_dataset("umutertugrul/turkish-hospital-medical-articles", streaming=True)
raw_stream = next(iter(streamed_dataset.values()))
data_list = list(itertools.islice(raw_stream, 100))
print(f"Successfully retrieved {len(data_list)}.")

if len(data_list) == 0:
    print("Error - No data received")
    exit(1)

with psycopg2.connect(dbname="pc", user="pc", password="", host="localhost", port="5432") as conn:
    register_vector(conn)
    cur = conn.cursor()
    insert_query = "INSERT INTO medical_data_semantic_chunk (url, chunk_text, chunk_vector) VALUES (%s, %s, %s);"

    for data in data_list:
        text = data['text']

        text_chunks = get_chunk_list(text)

        embedding_list = model.encode(text_chunks, normalize_embeddings=True)

        print(f"Generated {len(embedding_list)} embeddings.")
        print(f"Embedding shape: {embedding_list.shape}")

        for i in range(len(text_chunks)):
            cur.execute(insert_query, (data['url'], text_chunks[i], embedding_list[i]))

        conn.commit()