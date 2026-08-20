"""Ollama HTTP API'si icin ince bir sarmalayici.

Ollama, bilgisayarinizda 11434 portunda calisan basit bir HTTP sunucusudur.
Ekstra bir kutuphaneye ihtiyacimiz yok: iki tane POST istegi her seyi yapar.

    POST /api/embed   -> metni vektore cevirir
    POST /api/chat    -> sohbet eder, gerektiginde arac cagirir
"""

import requests

import config

# ─────────────────────────────────────────
# EMBEDDING MODELLERI
# ─────────────────────────────────────────
#
# "onek" (prefix) meselesi: bazi embedding modelleri, metnin BELGE mi yoksa SORU mu
# oldugunu belirten kisa bir on ek ile egitilir. Bu oneki koymazsaniz model calisir
# ama isabet belirgin sekilde duser. EmbeddingGemma tam olarak boyle bir modeldir.
#
# "min_similarity" ise o modele ozel alaka esigidir. Neden model basina degisir?
# Cunku her modelin benzerlik skorlari farkli bir araliga yayilir; birinde 0.50
# "alakasiz" demekken digerinde "cok alakali" olabilir. Esigi tek bir sabit olarak
# yazmak, model degistirdiginizde sessizce bozulur.
#
# Buradaki degerler baslangic tahminidir. KENDI bilgi bankaniz icin dogru degeri
# 'python olcum_karsilastirma.py' calistirarak olcun ve buraya yazin.
EMBED_MODELS = {
    "magibu": {
        "name": "alibayram/embeddingmagibu-200m:latest",  # Turkce'ye ozel, 768 boyut
        "query_prefix": "",
        "doc_prefix": "",
        "min_similarity": 0.75,
    },
    "gemma": {
        "name": "embeddinggemma:latest",  # Google, cok dilli, 768 boyut
        "query_prefix": "task: search result | query: ",
        "doc_prefix": "title: none | text: ",
        "min_similarity": 0.48,
    },
    "bge": {
        "name": "bge-m3:latest",  # BAAI, cok dilli, 1024 boyut
        "query_prefix": "",
        "doc_prefix": "",
        "min_similarity": 0.55,
    },
}

CONNECTION_ERROR = (
    f"Ollama'ya baglanilamadi ({config.OLLAMA_BASE_URL}). "
    "Once 'ollama serve' komutunu calistirin ya da Ollama uygulamasini acin."
)


def _post(path: str, payload: dict, timeout: int | None = None) -> dict:
    """Ollama'ya POST atar, JSON cevabi dondurur."""
    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}{path}",
            json=payload,
            timeout=timeout or config.OLLAMA_TIMEOUT,
        )
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"Ollama {timeout or config.OLLAMA_TIMEOUT} saniyede yanit vermedi. "
            "Model ilk yuklemede yavas olabilir, tekrar deneyin."
        ) from exc
    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama hatasi ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def embed(
    texts: list[str],
    embed_key: str = config.EMBED_MODEL,
    kind: str = "doc",
) -> list[list[float]]:
    """Metin listesini vektor listesine cevirir.

    embed_key: EMBED_MODELS icindeki anahtar ("magibu", "gemma", "bge").
    kind:      "doc" (indekslenen bilgi parcasi) ya da "query" (kullanici sorusu).

    Ayni metni "doc" ve "query" olarak gomerseniz farkli vektorler alirsiniz;
    bu bir hata degil, modelin egitildigi bicimdir.
    """
    if embed_key not in EMBED_MODELS:
        raise ValueError(
            f"Bilinmeyen embedding modeli: {embed_key}. Secenekler: {list(EMBED_MODELS)}"
        )
    if kind not in {"doc", "query"}:
        raise ValueError(f"kind 'doc' ya da 'query' olmali, '{kind}' verildi.")

    model = EMBED_MODELS[embed_key]
    prefix = model["query_prefix"] if kind == "query" else model["doc_prefix"]
    try:
        data = _post("/api/embed", {"model": model["name"], "input": [prefix + t for t in texts]})
    except RuntimeError as exc:
        # En sik hata: model henuz indirilmemis. Kullaniciya cozumu soyle.
        if "not found" in str(exc).lower():
            raise RuntimeError(
                f"'{model['name']}' modeli kurulu degil. Once indirin:\n"
                f"    ollama pull {model['name']}"
            ) from exc
        raise
    return data["embeddings"]


def chat(
    messages: list[dict],
    model: str | None = None,
    tools: list[dict] | None = None,
    temperature: float | None = None,
    seed: int | None = None,
) -> dict:
    """Sohbet mesajlarini modele gonderir ve model mesajini dondurur.

    Donen sozlukte 'content' (metin) ve varsa 'tool_calls' (arac cagrilari) bulunur.

    seed: Ornekleme tohumu. Ayni seed + ayni girdi = AYNI cikti. Normal sohbette
    gerekmez; olcum yaparken sarttir. Sabit tohum olmadan ayni testi ust uste
    calistirdiginizda farkli sonuc alirsiniz ve bir prompt degisikliginin ise
    yarayip yaramadigini ANLAYAMAZSINIZ (olculdu: ayni test %25, %31, %44).
    """
    payload = {
        "model": model or config.CHAT_MODEL,
        "messages": messages,
        "stream": False,                     # tek parca cevap; parse etmesi kolay
        "think": False,                      # dusunme blogunu kapat — qwen3 aksi halde <think> uretir
        "keep_alive": config.KEEP_ALIVE,     # model GPU'da kalsin, her soruda yeniden yuklenmesin
        "options": {
            "temperature": config.TEMPERATURE if temperature is None else temperature,
            "num_ctx": config.NUM_CTX,             # baglam tasip eski mesajlar sessizce dusmesin
            "num_predict": config.NUM_PREDICT,     # tekrar dongusu sonsuza kadar surmesin
            "repeat_penalty": config.REPEAT_PENALTY,
        },
    }
    if tools:
        payload["tools"] = tools
    if seed is not None:
        payload["options"]["seed"] = seed

    try:
        return _post("/api/chat", payload)["message"]
    except RuntimeError as exc:
        # Her model "think" parametresini desteklemez (orn. llama3.1, mistral).
        # Destekleyen modellerde kapatmak istiyoruz, desteklemeyende ise geri cekiliyoruz.
        if "think" not in str(exc).lower():
            raise
        payload.pop("think")
        return _post("/api/chat", payload)["message"]
