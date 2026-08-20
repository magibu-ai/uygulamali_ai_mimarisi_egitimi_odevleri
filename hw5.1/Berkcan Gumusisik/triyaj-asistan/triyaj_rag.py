"""Tıbbi bilgi tabanı üzerinde RAG: parçalama, vektör arama ve TOPRAKLANMIŞ cevap.

Bu dosyanın tek amacı var: model, SADECE bilgi tabanındaki metinlerde yazanı
söylesin; kendi kafasından tıbbi bilgi uydurmasın.  Bunu iki kapı ile sağlarız:

    1. ARAMA KAPISI   -> benzerlik eşiğin altındaysa LLM hiç çağrılmaz.
    2. ÜRETİM KAPISI  -> LLM'e "sadece bu metinlerden cevapla" talimatı verilir.

İkisinden biri geçilemezse cevap: REFUSAL ("Bu konuda bilgi tabanımda ...").

Not: Bu bir triyaj (yönlendirme) asistanıdır; tanı koymaz, ilaç dozu önermez.
Aciliyet kararı için ayrıca tools.py içindeki aciliyet_degerlendir aracına bakın.
"""

import os

import chromadb

import ollama_client

# Vektörler bu klasöre diske yazılır; silmek indeksi sıfırlar.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
COLLECTION_NAME = "tibbi_bilgi"

REFUSAL = "Bu konuda bilgi tabanımda güvenilir bir bilgi bulunmuyor."

SYSTEM_PROMPT = f"""Sen bir tıbbi bilgilendirme asistanısın.

Kurallar:
1. SADECE aşağıda verilen bilgi parçalarındaki bilgiyi kullan.
2. Genel tıp bilgini KESİNLİKLE ekleme. Metinde yoksa, senin için yoktur.
3. Parçalar soruyu cevaplamaya yetmiyorsa, aynen şu cümleyi yaz ve başka hiçbir
   şey ekleme:
{REFUSAL}
4. Cevabını Türkçe, kısa ve sade yaz. KESİN TANI KOYMA, ilaç dozu önerme.
5. Uygun olduğunda kişiyi bir hekime ya da acile yönlendir.
"""


def chunk_text(text: str, size: int = 180, overlap: int = 40) -> list[str]:
    """Uzun metni, uçları birbirine binen kelime pencerelerine böler.

    Bindirme (overlap) sayesinde bir cümle tam iki parçanın arasına düşüp
    kaybolmaz.
    """
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def get_collection():
    """Bilgi tabanının Chroma koleksiyonunu açar/oluşturur."""
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # mesafe = 1 - kosinüs benzerliği
        embedding_function=None,  # vektörleri biz üretiyoruz (Ollama ile)
    )


def search(question: str, k: int = 4) -> list[dict]:
    """Soruyu vektöre çevirip en yakın k parçayı getirir."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_vector = ollama_client.embed([question], kind="query")[0]
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "title": meta.get("title", "-"),
                "url": meta.get("url", "-"),
                "similarity": 1.0 - distance,
            }
        )
    return hits


def answer_medical(question: str, k: int = 4) -> dict:
    """Tıbbi soruyu SADECE bilgi tabanına dayanarak cevaplar."""
    hits = search(question, k)

    # --- 1. KAPI: arama ---
    # Hiçbir parça eşiği geçemediyse LLM'i hiç çağırmayız; uyduramaz.
    threshold = ollama_client.EMBED_MODEL["min_similarity"]
    relevant = [h for h in hits if h["similarity"] >= threshold]
    if not relevant:
        return {"answer": REFUSAL, "sources": [], "grounded": False}

    # --- 2. KAPI: üretim ---
    context = "\n\n".join(
        f"[{i}] {h['title']}\n{h['text']}" for i, h in enumerate(relevant, start=1)
    )
    message = ollama_client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"BİLGİ PARÇALARI:\n{context}\n\nSORU: {question}"},
        ],
        temperature=0.0,  # yaratıcılık yok, sadece metne sadakat
    )
    answer = (message.get("content") or "").strip() or REFUSAL

    # Model reddettiyse kaynak göstermenin anlamı yok.
    grounded = REFUSAL[:25].lower() not in answer.lower()

    # Aynı yazıdan birden fazla parça gelmiş olabilir; her kaynak bir kez,
    # en yüksek benzerlik skoruyla görünsün.
    sources: list[dict] = []
    if grounded:
        seen: set[str] = set()
        for hit in relevant:  # relevant zaten benzerliğe göre sıralı
            if hit["url"] not in seen:
                seen.add(hit["url"])
                sources.append(
                    {
                        "title": hit["title"],
                        "url": hit["url"],
                        "similarity": round(hit["similarity"], 3),
                    }
                )

    return {"answer": answer, "sources": sources, "grounded": grounded}
