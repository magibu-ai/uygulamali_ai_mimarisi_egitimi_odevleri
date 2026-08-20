"""Minimal OpenRouter client; the user's key is never persisted."""

from __future__ import annotations

import json
from typing import Any

import httpx


class OpenRouterClient:
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    models_endpoint = "https://openrouter.ai/api/v1/models"

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://huggingface.co/spaces/berkbirkan/dynamic-agentic-rag-demo",
            "X-Title": "Dynamic Traditional and Agentic RAG",
        }

    def complete(self, messages: list[dict[str, str]], *, model: str, api_key: str, json_mode: bool = False) -> str:
        if not api_key.strip():
            raise ValueError("OpenRouter API key gerekli.")
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 600}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=90) as client:
            response = client.post(
                self.endpoint,
                headers=self._headers(api_key),
                json=payload,
            )
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def json(self, messages: list[dict[str, str]], *, model: str, api_key: str) -> dict:
        try:
            content = self.complete(messages, model=model, api_key=api_key, json_mode=True)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {400, 404, 422}:
                raise
            content = self.complete(messages, model=model, api_key=api_key, json_mode=False)
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Model geçerli JSON grader sonucu döndürmedi.")
        return json.loads(content[start : end + 1])

    def list_models(self, api_key: str, *, free_only: bool = False) -> list[tuple[str, str]]:
        if not api_key.strip():
            raise ValueError("Model listesini almak için OpenRouter API key gerekli.")
        with httpx.Client(timeout=30) as client:
            response = client.get(self.models_endpoint, headers=self._headers(api_key), params={"output_modalities": "text", "sort": "pricing-low-to-high"})
            response.raise_for_status()
        choices = [("OpenRouter Free Router — $0", "openrouter/free")]
        for item in response.json().get("data", []):
            pricing = item.get("pricing") or {}
            prompt = float(pricing.get("prompt") or 0)
            completion = float(pricing.get("completion") or 0)
            is_free = prompt == 0 and completion == 0
            if free_only and not is_free:
                continue
            suffix = "$0" if is_free else f"${prompt * 1_000_000:.2f}/${completion * 1_000_000:.2f} per 1M"
            choices.append((f"{item.get('name', item['id'])} — {suffix}", item["id"]))
        seen = set()
        return [choice for choice in choices if not (choice[1] in seen or seen.add(choice[1]))]
