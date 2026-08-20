"""Gerçek Türkçe hastane makalelerini internetten indirir ve ChromaDB'ye yazar.

Veri kaynağı, Hugging Face üzerindeki gerçek bir veri setidir (Acıbadem sağlık
ansiklopedisi makaleleri).  Veri UYDURULMAZ; doğrudan bu setten çekilir:

    umutertugrul/turkish-hospital-medical-articles

Bu set "gated" (kapılı) olduğundan bir kereye mahsus giriş yapmanız gerekir:

    huggingface-cli login

Akış:
    1. Makaleler indirilir.
    2. Her makale, kelime pencerelerine (chunk) bölünür.
    3. embeddinggemma ile vektörlere çevrilip Chroma koleksiyonuna yazılır.

Kullanım:
    python3 veri_indeksle.py                 # 300 makale (varsayılan)
    python3 veri_indeksle.py --limit 500     # daha fazla makale
    python3 veri_indeksle.py --reset         # koleksiyonu sıfırdan kur
"""

import argparse
import time

import chromadb
from datasets import load_dataset

import ollama_client
import triyaj_rag

DATASET = "umutertugrul/turkish-hospital-medical-articles"
SPLIT = "acibadem"
BATCH_SIZE = 32
MIN_ARTICLE_CHARS = 400  # çok kısa (içeriksiz) makaleleri ele

parser = argparse.ArgumentParser(description="Tıbbi makaleleri vektör veritabanına yaz.")
parser.add_argument("--limit", type=int, default=300, help="Kaç makale indekslensin (varsayılan 300)")
parser.add_argument("--reset", action="store_true", help="Koleksiyonu sıfırdan oluştur")
args = parser.parse_args()

print(f"[1/3] Veri seti internetten indiriliyor: {DATASET} (bölüm: {SPLIT})")
dataset = load_dataset(DATASET, split=SPLIT)

# Yeterince içeriği olan makaleleri sırayla al.
articles: list[dict] = []
for row in dataset:
    text = (row.get("text") or "").strip()
    if len(text) >= MIN_ARTICLE_CHARS:
        articles.append({"title": row["title"], "url": row["url"], "text": text})
    if len(articles) >= args.limit:
        break
print(f"      {len(articles)} makale alındı.")

print("[2/3] Makaleler parçalara bölünüyor...")
documents: list[str] = []
metadatas: list[dict] = []
ids: list[str] = []
for article_index, article in enumerate(articles):
    for chunk_index, chunk in enumerate(triyaj_rag.chunk_text(article["text"])):
        documents.append(chunk)
        metadatas.append({"title": article["title"], "url": article["url"]})
        ids.append(f"{article_index}-{chunk_index}")
print(f"      {len(documents)} parça oluştu (makale başına ~{len(documents) // max(len(articles), 1)}).")

client = chromadb.PersistentClient(path=triyaj_rag.DB_PATH)
if args.reset:
    try:
        client.delete_collection(triyaj_rag.COLLECTION_NAME)
        print("      Eski koleksiyon silindi (--reset).")
    except Exception:
        pass  # koleksiyon zaten yoksa sorun değil

collection = triyaj_rag.get_collection()

print(f"[3/3] '{ollama_client.EMBED_MODEL['name']}' ile vektörler üretiliyor...")
started = time.time()
for start in range(0, len(documents), BATCH_SIZE):
    batch = documents[start : start + BATCH_SIZE]
    collection.add(
        ids=ids[start : start + BATCH_SIZE],
        documents=batch,
        metadatas=metadatas[start : start + BATCH_SIZE],
        embeddings=ollama_client.embed(batch, kind="doc"),
    )
    done = min(start + BATCH_SIZE, len(documents))
    print(f"      {done}/{len(documents)} parça ({time.time() - started:.0f} sn)", end="\r")

print(f"\n      Bitti: '{triyaj_rag.COLLECTION_NAME}' koleksiyonunda "
      f"{collection.count()} parça ({time.time() - started:.0f} sn).")
print("\nHazır. Şimdi sohbeti başlatın:  python3 chat.py")
