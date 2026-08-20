"""OpenAI-compatible Hugging Face Inference Router client."""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

MODEL_ID = "deepseek-ai/DeepSeek-V4-Flash:fireworks-ai"
ROUTER_BASE_URL = "https://router.huggingface.co/v1"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2
MAX_COMPLETION_TOKENS = 4096


def _read_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


class HFRouterClient:
    """Thin adapter that normalizes SDK objects to plain tool messages."""

    def __init__(
        self,
        token: str | None = None,
        *,
        model: str = MODEL_ID,
        client: Any | None = None,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        max_tokens: int = MAX_COMPLETION_TOKENS,
    ):
        self.token = token or os.getenv("HF_TOKEN")
        self.model = model
        self._client = client
        try:
            timeout_value = float(timeout)
        except (TypeError, ValueError):
            timeout_value = REQUEST_TIMEOUT_SECONDS
        self.timeout = max(1.0, min(timeout_value, REQUEST_TIMEOUT_SECONDS))
        try:
            retries_value = int(max_retries)
        except (TypeError, ValueError):
            retries_value = MAX_RETRIES
        self.max_retries = max(0, min(retries_value, MAX_RETRIES))
        try:
            tokens_value = int(max_tokens)
        except (TypeError, ValueError):
            tokens_value = MAX_COMPLETION_TOKENS
        self.max_tokens = max(1, min(tokens_value, MAX_COMPLETION_TOKENS))

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.token:
                raise RuntimeError("HF_TOKEN is required for a live Inference Router request")
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - requirements install path.
                raise RuntimeError("Install openai to use the HF Inference Router") from exc
            self._client = OpenAI(
                base_url=ROUTER_BASE_URL,
                api_key=self.token,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        tool_choice: str | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "tools": list(tools),
            "max_tokens": self.max_tokens,
        }
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        response = self.client.chat.completions.create(**kwargs)
        choices = _read_attr(response, "choices", [])
        if not choices:
            raise RuntimeError("HF Router returned no choices")
        message = _read_attr(choices[0], "message", choices[0])
        normalized: dict[str, Any] = {
            "role": _read_attr(message, "role", "assistant"),
            "content": _read_attr(message, "content", "") or "",
        }
        calls = _read_attr(message, "tool_calls", None) or []
        if calls:
            normalized["tool_calls"] = []
            for index, call in enumerate(calls):
                function = _read_attr(call, "function", {})
                arguments = _read_attr(function, "arguments", "{}")
                if not isinstance(arguments, str):
                    import json

                    arguments = json.dumps(arguments, ensure_ascii=False)
                normalized["tool_calls"].append(
                    {
                        "id": _read_attr(call, "id", f"call-{index + 1}"),
                        "type": _read_attr(call, "type", "function"),
                        "function": {
                            "name": _read_attr(function, "name", ""),
                            "arguments": arguments,
                        },
                    }
                )
        return normalized


# A descriptive alias makes the dependency boundary explicit to callers.
HFInferenceClient = HFRouterClient
HFChatClient = HFRouterClient

__all__ = [
    "HFChatClient",
    "HFInferenceClient",
    "HFRouterClient",
    "MAX_COMPLETION_TOKENS",
    "MAX_RETRIES",
    "MODEL_ID",
    "REQUEST_TIMEOUT_SECONDS",
    "ROUTER_BASE_URL",
]
