"""Ollama Python SDK yanitlarini uygulama icin sade bir bicime donusturur."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import ollama


class OllamaUnavailableError(RuntimeError):
    """Ollama sunucusuna veya modele ulasilamadiginda kullanilir."""


class OllamaClient:
    def __init__(
        self,
        model: str = "llama3.2:3b",
        host: str = "http://127.0.0.1:11434",
        timeout: float = 300,
    ) -> None:
        """Secilen model ve baglanti ayarlariyla Ollama SDK istemcisini kurar."""

        self.model = model
        self.client = ollama.Client(host=host, timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ollama sohbetini calistirip tool-call yanitlarini ortak formata cevirir."""

        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": 0},
            "keep_alive": -1,
        }
        if tools:
            request["tools"] = tools
        if format_schema:
            request["format"] = format_schema

        try:
            response = self.client.chat(**request)
        except Exception as error:
            raise OllamaUnavailableError(
                f"Ollama yanit vermedi. Sunucunun acik ve '{self.model}' "
                "modelinin yuklu oldugunu kontrol edin."
            ) from error

        message = response.message
        calls: list[dict[str, Any]] = []
        for call in message.tool_calls or []:
            arguments = call.function.arguments
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"_raw": arguments}
            calls.append(
                {
                    "id": getattr(call, "id", None) or str(uuid4()),
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": arguments or {},
                    },
                }
            )
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": calls,
        }
