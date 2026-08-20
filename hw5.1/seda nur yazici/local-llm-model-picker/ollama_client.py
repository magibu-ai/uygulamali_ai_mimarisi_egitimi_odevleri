"""Ollama HTTP API istemcisi."""

import os

import requests


BASE_URL = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

CHAT_MODEL = os.getenv(
    "OLLAMA_CHAT_MODEL",
    "qwen3:4b-instruct-2507-q4_K_M",
)


def _request(
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 600,
) -> dict:

    try:

        response = requests.request(
            method=method,
            url=f"{BASE_URL}{path}",
            json=payload,
            timeout=timeout,
        )

    except requests.exceptions.ConnectionError as exc:

        raise RuntimeError(
            f"Ollama'ya bağlanılamadı: {BASE_URL}"
        ) from exc

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Ollama isteği başarısız: {exc}"
        ) from exc

    if response.status_code != 200:

        raise RuntimeError(
            f"Ollama HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    return response.json()


def chat_raw(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,

        # Qwen thinking modunu kapatıyoruz.
        "think": False,

        "keep_alive": "10m",

        "options": {
            "temperature": temperature,
            "num_predict": 512,
        },
    }

    if tools:
        payload["tools"] = tools

    return _request(
        "POST",
        "/api/chat",
        payload,
    )


def chat(
    messages: list[dict],
    model: str = CHAT_MODEL,
    tools: list[dict] | None = None,
    temperature: float = 0.1,
) -> dict:

    response = chat_raw(
        messages=messages,
        model=model,
        tools=tools,
        temperature=temperature,
    )

    return response.get(
        "message",
        {},
    )


def list_models() -> list[dict]:

    result = _request(
        "GET",
        "/api/tags",
    )

    return result.get(
        "models",
        [],
    )


def show_model(
    model_name: str,
) -> dict:

    return _request(
        "POST",
        "/api/show",
        {
            "model": model_name,
        },
    )


def running_models() -> list[dict]:

    result = _request(
        "GET",
        "/api/ps",
    )

    return result.get(
        "models",
        [],
    )