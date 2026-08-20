"""Ollama HTTP API'si icin ince bir sarmalayici.

Ollama bilgisayarda 11434 portunda calisan basit bir HTTP sunucusudur; sohbet ve
arac cagirma icin tek bir POST yeterlidir:

    POST /api/chat -> sohbet eder, gerektiginde arac cagirir

Embedding tarafi bilincli olarak Ollama'da degil: ders kitaplari 11,7 milyon
karakter tutuyor ve yaklasik 14 bin parca uretiyor. sentence-transformers,
Apple Silicon'da MPS hizlandirmasiyla bu hacmi toplu (batch) halde belirgin
sekilde daha hizli isliyor. Sohbet modeli ise tamamen yerel Ollama uzerinde.
"""

from __future__ import annotations

import os

import requests

BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Arac cagirabilen (tool calling) yerel sohbet modeli.
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma4")

BAGLANTI_HATASI = (
    f"Ollama'ya baglanilamadi ({BASE_URL}). "
    "Once 'ollama serve' komutunu calistirin ya da Ollama uygulamasini acin."
)


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    try:
        yanit = requests.post(f"{BASE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as hata:
        raise RuntimeError(BAGLANTI_HATASI) from hata
    if yanit.status_code != 200:
        raise RuntimeError(f"Ollama hatasi ({yanit.status_code}): {yanit.text[:300]}")
    return yanit.json()


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:
    """Sohbet mesajlarini modele gonderir, model mesajini dondurur.

    Donen sozlukte "content" (metin) ve varsa "tool_calls" (arac cagrilari) bulunur.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # tek parca cevap
        "think": False,  # dusunme blogunu kapat, cikti sade kalsin
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload)["message"]


def modeller() -> list[str]:
    """Yuklu Ollama modellerini listeler (tanilama icin)."""
    try:
        veri = requests.get(f"{BASE_URL}/api/tags", timeout=10).json()
        return [m["name"] for m in veri.get("models", [])]
    except requests.RequestException:
        return []
