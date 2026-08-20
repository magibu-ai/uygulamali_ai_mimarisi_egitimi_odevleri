import itertools

import psycopg2
from datasets import load_dataset
from huggingface_hub import login
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

model_name = "alibayram/embeddingmagibu-200m"
model = SentenceTransformer(
    model_name,
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# With an 8k context window, a larger chunk size like 2000 keeps deep semantic context intact.
CHUNK_SIZE = 2000
OVERLAP = 200

def get_chunk_list(txt):
    # Convert the text into token IDs
    token_list = tokenizer.encode(txt, add_special_tokens=False)

    # Slice tokens into overlapping chunks
    token_ch = []
    for i in range(0, len(token_list), CHUNK_SIZE - OVERLAP):
        chunk_text = token_list[i: i + CHUNK_SIZE]
        token_ch.append(chunk_text)
        if i + CHUNK_SIZE >= len(token_list):
            break

    # Decode token segments back into text strings
    text_ch = [tokenizer.decode(chunk, skip_special_tokens=True) for chunk in token_ch]
    return text_ch

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
    insert_query = "INSERT INTO medical_data_token_chunk (url, chunk_text, chunk_vector) VALUES (%s, %s, %s);"

    for data in data_list:
        text = data['text']

        text_chunks = get_chunk_list(text)

        embedding_list = model.encode(text_chunks, normalize_embeddings=True)

        print(f"Generated {len(embedding_list)} embeddings.")
        print(f"Embedding shape: {embedding_list.shape}")

        for i in range(len(text_chunks)):
            cur.execute(insert_query, (data['url'], text_chunks[i], embedding_list[i]))

        conn.commit()