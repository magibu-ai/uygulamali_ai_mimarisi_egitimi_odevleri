import os

import requests


BASE_URL = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)


CHAT_MODEL = os.getenv(
    "OLLAMA_CHAT_MODEL",
    "gemma4:12b"
)


CONNECTION_ERROR = (
    f"Ollama'ya bağlanılamadı ({BASE_URL}). "
    "Ollama'nın çalıştığından emin olun."
)


def _post(
    path: str,
    payload: dict,
    timeout: int = 600
) -> dict:

    try:

        response = requests.post(
            f"{BASE_URL}{path}",
            json=payload,
            timeout=timeout
        )

    except requests.exceptions.ConnectionError as exc:

        raise RuntimeError(
            CONNECTION_ERROR
        ) from exc

    if response.status_code != 200:

        raise RuntimeError(
            f"Ollama hatası ({response.status_code}): "
            f"{response.text[:300]}"
        )

    return response.json()


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1
) -> dict:

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature
        }
    }

    if tools:
        payload["tools"] = tools

    result = _post(
        "/api/chat",
        payload
    )

    return result["message"]