import itertools

import psycopg2
from datasets import load_dataset
from huggingface_hub import login
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import nltk
import ssl

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

    return [s.strip() for s in sentences if s.strip()]

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
    insert_query = "INSERT INTO medical_data_sentence_chunk (url, chunk_text, chunk_vector) VALUES (%s, %s, %s);"

    for data in data_list:
        text = data['text']

        text_chunks = get_chunk_list(text)

        embedding_list = model.encode(text_chunks, normalize_embeddings=True)

        print(f"Generated {len(embedding_list)} embeddings.")
        print(f"Embedding shape: {embedding_list.shape}")

        for i in range(len(text_chunks)):
            cur.execute(insert_query, (data['url'], text_chunks[i], embedding_list[i]))

        conn.commit()