"""Phishing taktikleri uzerinde RAG: parcalama, vektor arama ve TOPRAKLANMIS cevap.

Bu dosyanin amaci modelin sadece MITRE ATT&CK'deki phishing verilerini kullanarak 
olayin hangi taktiklere benzedigini soylemesini saglamaktir.
"""

import os
import chromadb
import ollama_client

# Vektorler bu klasorde diske yazilir
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

REFUSAL = "Bilinen MITRE ATT&CK phishing taktigi bulunamadi."

SYSTEM_PROMPT = f"""Sen bir siber guvenlik asistanisin ve phishing (kimlik avi) analizi yapiyorsun.

Kurallar:
1. Asagida verilen Ingilizce MITRE ATT&CK makale parcalarini kullanarak, sorgudaki (genellikle Turkce olan) saldirinin hangi tekniklere benzedigini soyle.
2. Tam kelime eslemesi arama, anlamsal (davranis) benzerligi ara! Ornegin sorguda "linke tiklatma", "URL'ye gitme" geciyorsa bu MITRE'daki "Spearphishing Link" veya "Malicious Link" taktikleriyle dogrudan eslesir. "Dosya indirme", "ekli dosya" geciyorsa "Attachment" ile eslesir.
3. Eger sorguda anlatilan senaryo, parcalardaki herhangi bir teknigin davranisiyla dolayli yoldan da olsa ortusuyorsa mutlaka o teknikle eslestir.
4. Parcalar gercekten hicbir sekilde ilgisiz ise o zaman aynen su cumleyi yaz: {REFUSAL}
5. Cevabini Turkce ve net bir sekilde yaz. Hangi tekniklerin goruldugunu ve NEDEN eslestirdigini acikla.
6. Eslesme bulduysan asla '{REFUSAL}' yazma.
"""

def chunk_text(text: str, size: int = 220, overlap: int = 40) -> list[str]:
    """Uzun metni, ucları birbirine binen kelime pencerelerine boler."""
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks

def get_collection(embed_key: str = ollama_client.DEFAULT_EMBED):
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(
        name=f"phishing_taktikleri_{embed_key}",
        metadata={"hnsw:space": "cosine"}, 
        embedding_function=None,            
    )

def search(question: str, embed_key: str = ollama_client.DEFAULT_EMBED, k: int = 4) -> list[dict]:
    collection = get_collection(embed_key)
    if collection.count() == 0:
        return []

    query_vector = ollama_client.embed([question], embed_key, kind="query")[0]
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
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

def answer_phishing(question: str, embed_key: str = ollama_client.DEFAULT_EMBED, k: int = 6) -> dict:
    hits = search(question, embed_key, k)

    relevant = hits
    if not relevant:
        return {"answer": REFUSAL, "sources": [], "grounded": False}

    context = "\n\n".join(
        f"[{i}] {h['title']}\n{h['text']}" for i, h in enumerate(relevant, start=1)
    )
    message = ollama_client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"MITRE ATT&CK TAKTIKLERI:\n{context}\n\nANALIZ EDILECEK E-POSTA/DURUM: {question}"},
        ],
        temperature=0.0,
    )
    answer = (message.get("content") or "").strip() or REFUSAL

    grounded = REFUSAL.split("—")[0].strip().lower() not in answer.lower()

    sources: list[dict] = []
    if grounded:
        seen: set[str] = set()
        for hit in relevant:
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
