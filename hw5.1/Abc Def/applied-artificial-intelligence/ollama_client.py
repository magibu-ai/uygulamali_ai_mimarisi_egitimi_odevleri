"""Ollama HTTP API'si icin ince bir sarmalayici.

Ollama, bilgisayarinizda 11434 portunda calisan basit bir HTTP sunucusudur.
Ekstra bir kutuphaneye ihtiyacimiz yok: iki tane POST istegi her seyi yapar.

    POST /api/embed   -> metni vektore cevirir
    POST /api/chat    -> sohbet eder, gerektiginde arac cagirir
"""

import os

import requests

BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

CONNECTION_ERROR = (
    f"Ollama'ya baglanilamadi ({BASE_URL}). "
    "Once 'ollama serve' komutunu calistirin ya da Ollama uygulamasini acin."
)


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    """Ollama'ya POST atar, JSON cevabi dondurur."""
    try:
        response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    if response.status_code != 200:
        raise RuntimeError(f"Ollama hatasi ({response.status_code}): {response.text[:300]}")
    return response.json()

def chat(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:
    """Sohbet mesajlarini modele gonderir ve model mesajini dondurur.

    Donen sozlukte "content" (metin) ve varsa "tool_calls" (arac cagrilari) bulunur.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,   # tek parca cevap; ogrenmesi daha kolay
        "think": False,    # dusunme blogunu kapat, ciktiyi sade tut
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]
