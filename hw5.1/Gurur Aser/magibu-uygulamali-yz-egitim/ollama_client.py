"""Small, deterministic adapter around the Ollama Python 0.6.2 client.

The adapter keeps the rest of the application independent from Ollama's
Pydantic response objects.  Ollama's local ``chat`` endpoint does not expose an
OpenAI-style ``tool_choice`` argument, so the optional argument is accepted for
the agent/test boundary but intentionally not forwarded to the SDK.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, Self

MODEL = "qwen3.5:9b-q4_K_M"
MODEL_OPTIONS: dict[str, Any] = {
    "num_ctx": 8192,
    "temperature": 0.2,
    "seed": 42,
    "num_predict": 768,
}


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _arguments(value: Any) -> dict[str, Any]:
    """Normalize SDK mappings and defensive JSON-string arguments."""

    if isinstance(value, Mapping):
        return dict(value)
    if value in (None, ""):
        return {}
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _normalize_tool_call(call: Any) -> dict[str, Any]:
    function = _read(call, "function", {})
    normalized: dict[str, Any] = {
        "function": {
            "name": str(_read(function, "name", "") or ""),
            "arguments": _arguments(_read(function, "arguments", {})),
        }
    }
    # Ollama 0.6.2's Message.ToolCall does not define id/type.  Preserve them
    # when a compatible fake/HTTP mapping provides them, but never require them.
    for key in ("id", "type"):
        value = _read(call, key, None)
        if value is not None:
            normalized[key] = value
    return normalized


def normalize_message(value: Any) -> dict[str, Any]:
    """Return a plain assistant message from a dict or Ollama SDK object."""

    # A ChatResponse contains ``message``; a test double may already be a
    # message mapping/object, so accept both forms.
    message = _read(value, "message", None)
    if message is None:
        message = value
    normalized: dict[str, Any] = {
        "role": str(_read(message, "role", "assistant") or "assistant"),
        "content": str(_read(message, "content", "") or ""),
    }
    thinking = _read(message, "thinking", None)
    if thinking:
        normalized["thinking"] = str(thinking)
    calls = _read(message, "tool_calls", None) or []
    if calls:
        normalized["tool_calls"] = [_normalize_tool_call(call) for call in calls]
    return normalized


class OllamaClient:
    """Bounded local Ollama client used by :class:`chat.PantryAgent`."""

    def __init__(self, *, model: str = MODEL, client: Any | None = None):
        self.model = model
        if client is None:
            try:
                from ollama import Client
            except ImportError as exc:  # pragma: no cover - install/runtime boundary
                raise RuntimeError("ollama==0.6.2 kurulmalı ve Ollama çalışıyor olmalı.") from exc
            client = Client()
        self._client = client

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        """Call local ``/api/chat`` once and return a plain message mapping."""

        del tool_choice  # Ollama 0.6.2 has no tool_choice request field.
        response = self._client.chat(
            model=self.model,
            messages=list(messages),
            tools=list(tools),
            stream=False,
            think=False,
            options=dict(MODEL_OPTIONS),
        )
        return normalize_message(response)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


__all__ = [
    "MODEL",
    "MODEL_OPTIONS",
    "OllamaClient",
    "normalize_message",
]
