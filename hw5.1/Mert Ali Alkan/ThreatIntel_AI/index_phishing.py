"""MITRE ATT&CK verilerini indirir, Phishing tekniklerini filtreler, vektörler ve ChromaDB'ye yazar.

Kullanım:
    python3 index_phishing.py
    python3 index_phishing.py --model gemma --reset
"""

import argparse
import time
import requests
import re
import chromadb

import phishing_rag
import ollama_client

URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
BATCH_SIZE = 32

parser = argparse.ArgumentParser(description="MITRE ATT&CK Phishing verilerini vektor veritabanina yaz.")
parser.add_argument(
    "--model",
    default="gemma",
    choices=list(ollama_client.EMBED_MODELS.keys()),
    help="Hangi embedding modeli kullanilsin (varsayilan gemma)",
)
parser.add_argument("--reset", action="store_true", help="Koleksiyonu sifirdan olustur")
args = parser.parse_args()

print(f"[1/3] MITRE ATT&CK STIX verisi indiriliyor...")
try:
    response = requests.get(URL, timeout=30)
    data = response.json()
except Exception as e:
    print(f"Hata: Veri indirilemedi ({e})")
    exit(1)

# "Phishing" ile ilgili attack-pattern'leri sec (T1566 ve varyasyonlari vs.)
objects = data.get("objects", [])
attack_patterns = [obj for obj in objects if obj.get("type") == "attack-pattern"]

phishing_patterns = []
for ap in attack_patterns:
    name = ap.get("name", "")
    desc = ap.get("description", "")
    if "Phishing" in name or "phish" in desc.lower() or "Social Engineering" in name:
        phishing_patterns.append(ap)

print(f"      {len(phishing_patterns)} phishing taktigi bulundu.")

print("[2/3] Teknikler parcalara bolunuyor...")
documents = []
metadatas = []
ids = []

for article_index, item in enumerate(phishing_patterns):
    name = item.get("name", "Bilinmeyen")
    desc = item.get("description", "Aciklama yok.")
    
    # URL ve ID bul
    url = "-"
    mitre_id = "-"
    ext_refs = item.get("external_references", [])
    for ref in ext_refs:
        if ref.get("source_name") == "mitre-attack":
            url = ref.get("url", "-")
            mitre_id = ref.get("external_id", "-")
            break
            
    # Markdown tag'lerini vs. kismen temizle (tam temizlik guzel olur ama baslangic icin yeterli)
    clean_desc = re.sub(r'<[^>]+>', '', desc)
    
    text_to_chunk = f"Teknik: {name} ({mitre_id})\nAciklama: {clean_desc}"
    
    for chunk_index, chunk in enumerate(phishing_rag.chunk_text(text_to_chunk, size=200, overlap=50)):
        documents.append(chunk)
        metadatas.append(
            {"title": f"{name} ({mitre_id})", "url": url, "article_index": article_index}
        )
        ids.append(f"{article_index}-{chunk_index}")

print(f"      {len(documents)} parca olustu.")

client = chromadb.PersistentClient(path=phishing_rag.DB_PATH)
embed_key = args.model
name = f"phishing_taktikleri_{embed_key}"

if args.reset:
    try:
        client.delete_collection(name)
        print("      Eski koleksiyon silindi.")
    except Exception:
        pass

collection = phishing_rag.get_collection(embed_key)
print(f"[3/3] '{ollama_client.EMBED_MODELS[embed_key]['name']}' ile vektorler uretiliyor...")
started = time.time()

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

print(f"\n      Bitti: '{name}' koleksiyonunda {collection.count()} parca "
      f"({time.time() - started:.0f} sn).")

print("\nHazir. Simdi projeyi calistirabilirsiniz.")
