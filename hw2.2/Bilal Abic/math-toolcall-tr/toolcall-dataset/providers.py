"""OpenAI ve Gemini icin tek istemci.

Gemini, OpenAI uyumlu endpoint uzerinden cagrildigi icin iki saglayici da ayni
kod yolunu kullanir. Tek bagimlilik: openai SDK.
"""
import json
import random
import re
import time

from openai import OpenAI

import config

_clients: dict[str, OpenAI] = {}


class ProviderError(RuntimeError):
    pass


def client(provider: str) -> OpenAI:
    if provider not in _clients:
        cfg = config.PROVIDERS.get(provider)
        if not cfg:
            raise ProviderError(f"Bilinmeyen saglayici: {provider}")
        if not cfg["api_key"]:
            raise ProviderError(f"{provider.upper()}_API_KEY tanimli degil (.env)")
        _clients[provider] = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    return _clients[provider]


def model_of(provider: str) -> str:
    return config.PROVIDERS[provider]["model"]


def _extract_json(text: str) -> dict:
    """Model bazen JSON'u kod blogu icinde dondurur; temizleyip parse et."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : start + (end - start + 1)])


def _is_reasoning(model: str) -> bool:
    """gpt-5*, o1/o3/o4* ailesi dusunme butcesi parametresini destekler."""
    return model.startswith(("gpt-5", "o1", "o3", "o4", "codex"))


def complete_json(provider: str, system: str, user: str) -> dict:
    """Modeli cagirip JSON sozluk dondur. Gecici hatalarda yeniden dener."""
    cli = client(provider)
    model = model_of(provider)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": config.TEMPERATURE,
        "max_completion_tokens": config.MAX_TOKENS,
    }
    # Matematiksel dogruluk icin mini modellerde dusunme butcesi kritik.
    if provider == "openai" and _is_reasoning(model):
        kwargs["reasoning_effort"] = config.REASONING_EFFORT

    last_err: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = cli.chat.completions.create(**kwargs)
            return _extract_json(resp.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            msg = str(exc)
            # Bazi modeller bu parametreleri desteklemez; cikarip tekrar dene.
            for bad in ("temperature", "reasoning_effort", "max_completion_tokens",
                        "response_format"):
                if bad in msg and bad in kwargs:
                    kwargs.pop(bad)
                    break
            else:
                time.sleep(2**attempt + random.random())
    raise ProviderError(f"[{provider}] {config.MAX_RETRIES} denemede basarisiz: {last_err}")
