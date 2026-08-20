"""Ollama HTTP API'si icin ince bir sarmalayici.

Ollama, bilgisayarda 11434 portunda calisan basit bir HTTP sunucusudur.
Ekstra kutuphaneye gerek yok: tek bir POST istegi her seyi yapar.

    POST /api/chat -> sohbet eder, gerektiginde arac cagirir
"""

import os

import requests

BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Arac cagirabilen (tool calling) sohbet modeli.
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b")

CONNECTION_ERROR = (
    f"Ollama'ya baglanilamadi ({BASE_URL}). "
    "Once 'ollama serve' komutunu calistirin ya da Ollama uygulamasini acin."
)


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    try:
        response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    if response.status_code != 200:
        raise RuntimeError(f"Ollama hatasi ({response.status_code}): {response.text[:300]}")
    return response.json()


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.0,
    think: bool = False,
) -> dict:
    """Sohbet mesajlarini modele gonderir ve model mesajini dondurur.

    Donen sozlukte "content" (metin) ve varsa "tool_calls" (arac cagrilari) bulunur.

    temperature 0: arac argumanlarinin (sehir adi, mesafe, kilo) uydurulmasini
    degil, kullanicinin verdigi degerlerin aynen gecirilmesini isteriz. 0.1'de
    ayni soru bazen sicaklik_c gibi opsiyonel alanlari uydurarak geliyordu.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,  # qwen3 dusunme blogunu kapat, ciktiyi sade tut
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]
