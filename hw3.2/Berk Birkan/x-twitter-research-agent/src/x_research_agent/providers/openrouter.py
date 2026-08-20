from __future__ import annotations

from typing import Any

import httpx

from x_research_agent.domain.schemas import ModelInfo


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        app_url: str,
        app_name: str,
        timeout: float = 60.0,
    ):
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "HTTP-Referer": app_url,
                "X-Title": app_name,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_tool_models(self) -> list[ModelInfo]:
        response = await self._request(
            "GET", "/models", params={"supported_parameters": "tools", "sort": "most-popular"}
        )
        models: list[ModelInfo] = []
        for item in response.get("data", []):
            supported = item.get("supported_parameters") or []
            if "tools" not in supported:
                continue
            pricing = item.get("pricing") or {}
            model_id = item["id"]
            models.append(
                ModelInfo(
                    id=model_id,
                    name=item.get("name") or model_id,
                    context_length=item.get("context_length"),
                    prompt_price=pricing.get("prompt"),
                    completion_price=pricing.get("completion"),
                    provider=model_id.split("/", 1)[0],
                    supports_structured_output="structured_outputs" in supported,
                    supported_parameters=supported,
                )
            )
        return sorted(
            models, key=lambda model: (not model.supports_structured_output, model.name.lower())
        )

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": 0.2,
        }
        return await self._request("POST", "/chat/completions", json=payload)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise OpenRouterError("OpenRouter is temporarily unreachable") from exc
        if response.status_code >= 400:
            try:
                data = response.json()
                message = data.get("error", {}).get("message") or data.get("message")
            except ValueError:
                message = None
            raise OpenRouterError(message or f"OpenRouter request failed ({response.status_code})")
        return response.json()
