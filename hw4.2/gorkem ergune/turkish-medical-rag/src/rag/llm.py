"""LLM abstraction for the RAG answering layer (Phase 7).

The pipeline depends only on the ``LLMClient`` protocol, so it is never coupled
to a single provider and can be driven by a fake client in tests (no network).

  * ``FakeLLMClient``      — records calls, returns a canned answer (offline).
  * ``AnthropicLLMClient`` — Claude API (lazy import; not a hard dependency).
  * ``build_llm_client``   — build the configured client from config.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal LLM interface: a system prompt + user prompt -> text answer."""

    def generate(self, system: str, user: str) -> str:  # pragma: no cover - protocol
        ...


class FakeLLMClient:
    """Deterministic offline client. Records every call for assertions."""

    def __init__(self, answer: str = "SAHTE_CEVAP"):
        self.answer = answer
        self.calls: list[dict[str, str]] = []

    def generate(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.answer

    @property
    def call_count(self) -> int:
        return len(self.calls)


class AnthropicLLMClient:
    """Claude API client. ``anthropic`` is imported lazily so it is only needed
    when this provider is actually used."""

    def __init__(
        self,
        model: str,
        max_output_tokens: int = 1024,
        temperature: float | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
    ):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.api_key_env = api_key_env

    def generate(self, system: str, user: str) -> str:
        import anthropic

        api_key = os.environ.get(self.api_key_env)
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        # Only send temperature when configured — Opus 4.x reject sampling params.
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        response = client.messages.create(**kwargs)
        return "".join(b.text for b in response.content if b.type == "text").strip()


def build_llm_client(config: dict[str, Any]) -> LLMClient:
    """Construct the LLM client described by ``llm`` in the config."""
    llm = config["llm"]
    provider = llm.get("provider", "fake")
    if provider == "fake":
        return FakeLLMClient()
    if provider == "anthropic":
        return AnthropicLLMClient(
            model=llm["model"],
            max_output_tokens=llm["max_output_tokens"],
            temperature=llm.get("temperature"),
            api_key_env=llm.get("api_key_env", "ANTHROPIC_API_KEY"),
        )
    raise ValueError(f"Unknown llm provider: {provider!r}")
