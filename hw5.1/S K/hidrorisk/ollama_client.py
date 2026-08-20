"""Ollama HTTP API'si icin ince bir sarmalayici.

Ollama, bilgisayarda 11434 portunda calisan yerel bir HTTP sunucusudur.

POST /api/chat -> sohbet eder ve gerektiginde arac cagirir
"""

import os

import requests


BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Tool calling destekli yerel sohbet modeli.
CHAT_MODEL = os.getenv(
    "OLLAMA_CHAT_MODEL",
    "qwen3:4b-instruct-2507-q4_K_M",
)

CONNECTION_ERROR = (
    f"Ollama'ya baglanilamadi ({BASE_URL}). "
    "Once Ollama uygulamasini acin."
)


def _post(path: str, payload: dict, timeout: int = 600) -> dict:
    """Ollama'ya POST istegi atar ve JSON cevabini dondurur."""

    try:
        response = requests.post(
            f"{BASE_URL}{path}",
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama hatasi ({response.status_code}): "
            f"{response.text[:300]}"
        )

    return response.json()


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:
    """Mesajlari Ollama modeline gonderir ve model mesajini dondurur.

    Donen sozlukte "content" ve varsa "tool_calls" bulunur.
    """

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
        },
    }

    if tools:
        payload["tools"] = tools

    return _post("/api/chat", payload)["message"]