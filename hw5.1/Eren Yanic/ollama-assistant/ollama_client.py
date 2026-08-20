"""Ollama's HTTP API, wrapped in the two calls this assistant actually needs.

Ollama is a plain HTTP server on port 11434. POST /api/chat carries the conversation
and the tool definitions; the reply is a message that either holds text or a list of
tool calls. That is the whole protocol.
"""

from __future__ import annotations

import requests

import config

CONNECTION_ERROR = (
    f"Could not reach Ollama at {config.OLLAMA_HOST}. "
    "Start it with 'ollama serve' (or open the Ollama app) and try again."
)


def _post(path: str, payload: dict, timeout: int) -> dict:
    try:
        response = requests.post(f"{config.OLLAMA_HOST}{path}", json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"Ollama did not answer within {timeout} s.") from exc
    if response.status_code != 200:
        raise RuntimeError(f"Ollama error ({response.status_code}): {response.text[:300]}")
    return response.json()


def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> dict:
    """Send the conversation to the model and return its reply message.

    The returned dict holds "content" (text) and, when the model wants to act,
    "tool_calls".
    """
    payload = {
        "model": model or config.CHAT_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,  # no reasoning block: it would eat the small context window
        "options": {
            "temperature": config.TEMPERATURE,
            "num_ctx": config.NUM_CTX,
        },
        "keep_alive": config.KEEP_ALIVE,
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload, config.OLLAMA_TIMEOUT)["message"]


def installed_models() -> list[str]:
    """Model names Ollama has locally. Raises RuntimeError when Ollama is unreachable."""
    try:
        response = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(CONNECTION_ERROR) from exc
    return [model["name"] for model in response.json().get("models", [])]
