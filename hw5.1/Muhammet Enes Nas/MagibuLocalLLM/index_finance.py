"""Finans bilgi bankasini parcalar, vektorler ve ChromaDB'ye yazar.

Kullanim:
    python index_finance.py                          # varsayilan embedding modeli
    python index_finance.py --model magibu --reset    # sifirdan indeksle
    python index_finance.py --model all --reset       # tum modelleri indeksle (karsilastirma icin)
"""

import argparse
import json
import time

import chromadb

import config
import finance_rag
import ollama_client

BATCH_SIZE = 16

parser = argparse.ArgumentParser(description="Finans bilgi bankasini vektor veritabanina yaz.")
parser.add_argument(
    "--model",
    default=config.EMBED_MODEL,
    choices=[*ollama_client.EMBED_MODELS, "all"],
    help="Hangi embedding modeli kullanilsin ('all' = hepsi)",
)
parser.add_argument("--reset", action="store_true", help="Koleksiyonu sifirdan olustur")
parser.add_argument("--kb", default=config.KB_PATH, help="Bilgi bankasi JSON dosyasi")
args = parser.parse_args()


print(f"[1/3] Bilgi bankasi okunuyor: {args.kb}")
with open(args.kb, encoding="utf-8") as handle:
    articles = json.load(handle)
print(f"      {len(articles)} kayit alindi.")


print("[2/3] Kayitlar parcalara bolunuyor...")
documents: list[str] = []
metadatas: list[dict] = []
ids: list[str] = []
for article_index, row in enumerate(articles):
    # Basligi metnin basina ekliyoruz: parca tek basina arandiginda neyden
    # bahsettigi belli olsun, boylece isabet artar.
    full_text = f"{row['title']}. {row['text']}"
    for chunk_index, chunk in enumerate(finance_rag.chunk_text(full_text)):
        documents.append(chunk)
        metadatas.append(
            {
                "title": row["title"],
                "url": row.get("url", "-"),
                "source": row.get("source", "-"),
                "article_index": article_index,
            }
        )
        ids.append(f"{article_index}-{chunk_index}")
print(f"      {len(documents)} parca olustu.")


embed_keys = list(ollama_client.EMBED_MODELS) if args.model == "all" else [args.model]
client = chromadb.PersistentClient(path=config.DB_PATH)

for embed_key in embed_keys:
    name = f"finans_bilgi_{embed_key}"
    if args.reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass  # koleksiyon zaten yoksa sorun degil

    collection = finance_rag.get_collection(embed_key)
    model_name = ollama_client.EMBED_MODELS[embed_key]["name"]
    print(f"[3/3] '{model_name}' ile vektorler uretiliyor...")
    started = time.time()

    try:
        for start in range(0, len(documents), BATCH_SIZE):
            batch = documents[start : start + BATCH_SIZE]
            collection.add(
                ids=ids[start : start + BATCH_SIZE],
                documents=batch,
                metadatas=metadatas[start : start + BATCH_SIZE],
                embeddings=ollama_client.embed(batch, embed_key, kind="doc"),
            )
            done = min(start + BATCH_SIZE, len(documents))
            print(f"      {done}/{len(documents)} parca ({time.time() - started:.0f} sn)", end="\r")
    except RuntimeError as exc:
        print(f"\n      ATLANDI ({embed_key}): {exc}\n")
        continue

    print(f"\n      Bitti: '{name}' koleksiyonunda {collection.count()} parca "
          f"({time.time() - started:.0f} sn).")

print("\nHazir. Once olcun:  python olcum_karsilastirma.py")
print("Sonra sohbeti baslatin:  python main.py")
