import httpx
import pytest

from x_research_agent.providers.openrouter import OpenRouterClient


@pytest.mark.asyncio
async def test_model_catalog_excludes_models_without_tools_and_badges_structured_output():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["supported_parameters"] == "tools"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "vendor/structured",
                        "name": "Structured",
                        "context_length": 100_000,
                        "supported_parameters": ["tools", "structured_outputs"],
                        "pricing": {"prompt": "0.1", "completion": "0.2"},
                    },
                    {
                        "id": "vendor/tools-only",
                        "name": "Tools Only",
                        "supported_parameters": ["tools"],
                        "pricing": {},
                    },
                    {
                        "id": "vendor/no-tools",
                        "name": "No Tools",
                        "supported_parameters": ["temperature"],
                        "pricing": {},
                    },
                ]
            },
        )

    client = OpenRouterClient(
        "sk-or-test",
        base_url="https://openrouter.test/api/v1",
        app_url="https://example.test",
        app_name="Test",
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://openrouter.test/api/v1", transport=httpx.MockTransport(handler)
    )
    models = await client.list_tool_models()
    await client.aclose()

    assert [model.id for model in models] == ["vendor/structured", "vendor/tools-only"]
    assert models[0].supports_structured_output is True
    assert models[1].supports_structured_output is False
