"""Ollama HTTP API'si için ince bir sarmalayıcı.

Ollama, bilgisayarınızda 11434 portunda çalışan yerel bir HTTP sunucusudur.
Ekstra bir SDK'ya ihtiyacımız yok: iki POST isteği her şeyi yapar.

    POST /api/embed   -> metni vektöre çevirir (embeddinggemma)
    POST /api/chat    -> sohbet eder, gerektiğinde araç çağırır (qwen2.5)

Neden iki ayrı model?  Embedding modeli metnin "anlamını" sayılara çevirir ki
benzer soruları veritabanında bulabilelim.  Sohbet modeli ise konuşur ve araç
çağırır.  Bu ikisi farklı işlere optimize edilmiştir; ayırmak doğaldır.
"""

import os

import requests

BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Araç çağırabilen (tool calling) yerel sohbet modeli.
# qwen2.5:14b daha akıcı Türkçe ve daha kararlı araç çağırma verir; daha hafif
# bir makinede "qwen2.5:7b" da çalışır (OLLAMA_CHAT_MODEL ile değiştirin).
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:14b")

# Embedding modeli.  "önek" (prefix) meselesi: EmbeddingGemma, metnin BELGE mi
# yoksa SORU mu olduğunu belirten kısa bir ön ek ile eğitilmiştir.  Bu öneki
# koymazsanız model yine çalışır ama isabet belirgin şekilde düşer.
# "min_similarity" bu modele özel alaka eşiğidir: benzerlik bu değerin altındaysa
# soruyu "bilgi tabanımda yok" diye reddederiz.  Değer olcum_karsilastirma.py ile
# ölçülerek seçilmiştir.
EMBED_MODEL = {
    "name": "embeddinggemma:latest",
    "query_prefix": "task: search result | query: ",
    "doc_prefix": "title: none | text: ",
    "min_similarity": 0.55,
}

CONNECTION_ERROR = (
    f"Ollama'ya bağlanılamadı ({BASE_URL}). "
    "Önce 'ollama serve' komutunu çalıştırın ya da Ollama uygulamasını açın."
)


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    """Ollama'ya POST atar, JSON cevabı döndürür."""
    try:
        response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama hatası ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def embed(texts: list[str], kind: str = "doc") -> list[list[float]]:
    """Metin listesini vektör listesine çevirir.

    kind: "doc" (indekslenen bilgi parçası) ya da "query" (kullanıcı sorusu).
    Aynı metni "doc" ve "query" olarak gömerseniz farklı vektörler alırsınız;
    bu bir hata değil, modelin eğitildiği biçimdir.
    """
    if kind not in {"doc", "query"}:
        raise ValueError(f"kind 'doc' ya da 'query' olmalı, '{kind}' verildi.")

    prefix = EMBED_MODEL["query_prefix"] if kind == "query" else EMBED_MODEL["doc_prefix"]
    data = _post(
        "/api/embed",
        {"model": EMBED_MODEL["name"], "input": [prefix + t for t in texts]},
    )
    return data["embeddings"]


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:
    """Sohbet mesajlarını modele gönderir ve model mesajını döndürür.

    Dönen sözlükte "content" (metin) ve varsa "tool_calls" (araç çağrıları) olur.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # tek parça cevap; takip etmesi kolay
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]
