from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b")


def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(method, f"{BASE_URL}{path}", timeout=180, **kwargs)
    response.raise_for_status()
    return response.json()


def list_models() -> list[str]:
    data = _request("GET", "/api/tags")
    return sorted(model["name"] for model in data.get("models", []))


def chat(messages: list[dict], model: str, tools: list[dict] | None = None) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096,
            "num_predict": 768,
        },
    }
    if tools:
        payload["tools"] = tools
    return _request("POST", "/api/chat", json=payload)["message"]
