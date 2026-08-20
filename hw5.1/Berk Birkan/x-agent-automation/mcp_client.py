from __future__ import annotations

import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class RemoteMCPClient:
    def __init__(self, url: str, api_key: str) -> None:
        self.url = url
        self.headers = {"x-api-key": api_key}

    @staticmethod
    def explain_error(exc: BaseException) -> str:
        """ExceptionGroup icindeki asil HTTP/MCP hatasini okunur hale getirir."""
        nested = getattr(exc, "exceptions", None)
        if nested:
            details = [RemoteMCPClient.explain_error(item) for item in nested]
            return "; ".join(dict.fromkeys(detail for detail in details if detail))
        response = getattr(exc, "response", None)
        if response is not None:
            if response.status_code == 401:
                return "Xquik API anahtari gecersiz veya yetkisiz (HTTP 401)."
            return f"Xquik MCP HTTP {response.status_code}: {response.text[:300]}"
        return str(exc) or exc.__class__.__name__

    async def list_ollama_tools(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=60) as http_client:
                async with streamable_http_client(self.url, http_client=http_client) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.list_tools()
        except BaseException as exc:
            raise RuntimeError(self.explain_error(exc)) from exc
        tools = []
        for tool in result.tools:
            parameters = getattr(tool, "inputSchema", None)
            if parameters is None:
                parameters = getattr(tool, "input_schema", None)
            if parameters is None:
                raise ValueError(f"{tool.name} araci bir input semasi dondurmedi.")
            tools.append({"type": "function", "function": {
                "name": tool.name,
                "description": tool.description or "MCP araci",
                "parameters": parameters,
            }})
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=90) as http_client:
                async with streamable_http_client(self.url, http_client=http_client) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments)
        except BaseException as exc:
            raise RuntimeError(self.explain_error(exc)) from exc
        blocks = []
        for item in result.content:
            text = getattr(item, "text", None)
            blocks.append(text if text else json.dumps(item.model_dump(mode="json"), ensure_ascii=False))
        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        if structured is not None:
            blocks.append(json.dumps(structured, ensure_ascii=False))
        output = "\n".join(blocks) or "MCP araci bos sonuc dondurdu."
        is_error = getattr(result, "isError", None)
        if is_error is None:
            is_error = getattr(result, "is_error", False)
        return f"MCP arac hatasi: {output}" if is_error else output
