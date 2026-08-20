"""LLM provider layer.

Every supported provider speaks the OpenAI Chat Completions wire format, so a
single ``openai.OpenAI`` client covers all of them — only ``base_url`` and the
per-request parameters differ. That keeps the dependency surface at one SDK
(as specified) while still offering more than one model family.

Credential discipline: the key arrives as a function argument, is handed to a
short-lived client, and is never stored on module state, never logged, and
never included in an exception. All upstream error text passes through
:func:`~ehekim.security.redact` before it can reach a client or a log handler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from .security import redact, validate_api_key

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """A sanitised, user-presentable upstream failure."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(redact(message))
        self.status_code = status_code


@dataclass(frozen=True)
class ModelSpec:
    key: str            # UI-facing identifier, "<provider>:<model>"
    provider: str
    model: str          # value sent to the API
    label: str
    family: str
    supports_thinking: bool = False


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    base_url: str
    key_prefix_hint: str
    console_url: str
    models: tuple[ModelSpec, ...] = field(default_factory=tuple)


def _deepseek(model: str, label: str) -> ModelSpec:
    return ModelSpec(
        key=f"deepseek:{model}",
        provider="deepseek",
        model=model,
        label=label,
        family="DeepSeek",
        supports_thinking=True,
    )


def _openrouter(model: str, label: str, family: str) -> ModelSpec:
    return ModelSpec(
        key=f"openrouter:{model}",
        provider="openrouter",
        model=model,
        label=label,
        family=family,
    )


PROVIDERS: dict[str, ProviderSpec] = {
    "deepseek": ProviderSpec(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        key_prefix_hint="sk-…",
        console_url="https://platform.deepseek.com/api_keys",
        models=(
            _deepseek("deepseek-v4-flash", "DeepSeek V4 Flash"),
            _deepseek("deepseek-v4-pro", "DeepSeek V4 Pro"),
        ),
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        key_prefix_hint="sk-or-v1-…",
        console_url="https://openrouter.ai/keys",
        models=(
            _openrouter("anthropic/claude-haiku-4.5", "Claude Haiku 4.5", "Anthropic"),
            _openrouter("openai/gpt-4.1-mini", "GPT-4.1 mini", "OpenAI"),
            _openrouter("google/gemini-2.5-flash", "Gemini 2.5 Flash", "Google"),
            _openrouter("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", "Meta"),
        ),
    ),
}

DEFAULT_MODEL_KEY = "deepseek:deepseek-v4-flash"

# DeepSeek documents low | high | max and maps "medium" onto "high" for
# OpenAI-compatibility. The project sends "medium" as specified in the brief;
# see README, "LLM configuration".
DEEPSEEK_REASONING_EFFORT = "medium"

MODELS: dict[str, ModelSpec] = {
    spec.key: spec for provider in PROVIDERS.values() for spec in provider.models
}


def get_model_spec(key: str | None) -> ModelSpec:
    resolved = key or DEFAULT_MODEL_KEY
    spec = MODELS.get(resolved)
    if spec is None:
        raise LLMError(f"Bilinmeyen model: {resolved!r}", status_code=400)
    return spec


def catalog() -> list[dict[str, Any]]:
    """Provider/model catalogue for the frontend. Contains no secrets."""
    return [
        {
            "id": provider.id,
            "label": provider.label,
            "key_hint": provider.key_prefix_hint,
            "console_url": provider.console_url,
            "models": [
                {
                    "key": m.key,
                    "label": m.label,
                    "family": m.family,
                    "supports_thinking": m.supports_thinking,
                }
                for m in provider.models
            ],
        }
        for provider in PROVIDERS.values()
    ]


@dataclass(frozen=True)
class LLMResult:
    content: str
    model: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None


def _build_client(spec: ModelSpec, api_key: str, timeout: float):
    from openai import OpenAI

    provider = PROVIDERS[spec.provider]
    headers: dict[str, str] = {}
    if spec.provider == "openrouter":
        # OpenRouter attributes traffic with these; both are static, non-secret.
        headers = {"HTTP-Referer": "http://127.0.0.1:8000", "X-Title": "e-hekim"}
    return OpenAI(
        api_key=api_key,
        base_url=provider.base_url,
        timeout=timeout,
        max_retries=1,
        default_headers=headers or None,
    )


def generate(
    *,
    model_key: str | None,
    api_key: str,
    messages: Sequence[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: float = 180.0,
) -> LLMResult:
    """Run one chat completion. Raises :class:`LLMError` with sanitised text."""
    spec = get_model_spec(model_key)
    key = validate_api_key(api_key)

    kwargs: dict[str, Any] = {
        "model": spec.model,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if spec.supports_thinking:
        # Thinking mode on, medium effort — per the project brief.
        kwargs["reasoning_effort"] = DEEPSEEK_REASONING_EFFORT
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

    client = _build_client(spec, key, timeout)
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 - normalised below
        raise _normalise_error(exc) from None

    choice = response.choices[0].message
    content = (choice.content or "").strip()
    reasoning = getattr(choice, "reasoning_content", None) or None

    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None) if usage else None
    return LLMResult(
        content=content,
        model=spec.model,
        reasoning=reasoning.strip() if isinstance(reasoning, str) else None,
        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
    )


def _normalise_error(exc: Exception) -> LLMError:
    """Map SDK exceptions to a sanitised LLMError with a sensible status."""
    import openai

    if isinstance(exc, openai.AuthenticationError):
        return LLMError(
            "Sağlayıcı API anahtarını reddetti. Anahtarı ve seçilen sağlayıcıyı kontrol edin.",
            status_code=401,
        )
    if isinstance(exc, openai.PermissionDeniedError):
        return LLMError(
            "API anahtarının bu modele erişim izni yok.", status_code=403
        )
    if isinstance(exc, openai.RateLimitError):
        return LLMError(
            "Sağlayıcı hız sınırına ulaşıldı veya bakiye yetersiz. Daha sonra tekrar deneyin.",
            status_code=429,
        )
    if isinstance(exc, openai.APITimeoutError):
        return LLMError("Sağlayıcı zaman aşımına uğradı.", status_code=504)
    if isinstance(exc, openai.APIConnectionError):
        return LLMError("Sağlayıcıya bağlanılamadı.", status_code=502)
    if isinstance(exc, openai.BadRequestError):
        return LLMError(f"Sağlayıcı isteği reddetti: {exc}", status_code=400)
    if isinstance(exc, openai.APIStatusError):
        status = getattr(exc, "status_code", 502) or 502
        return LLMError(f"Sağlayıcı hatası ({status}).", status_code=502)
    # Unknown failure: log a redacted trace locally, tell the client nothing
    # that could contain a credential.
    logger.error("Beklenmeyen sağlayıcı hatası: %s", redact(exc))
    return LLMError("Model çağrısı beklenmedik bir hatayla sonuçlandı.", status_code=502)
