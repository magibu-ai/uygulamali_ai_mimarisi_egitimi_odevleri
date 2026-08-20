from datetime import date

import httpx
import pytest

from x_research_agent.domain.schemas import ResearchConstraints
from x_research_agent.providers.xquik import XquikClient, XquikError


@pytest.mark.asyncio
async def test_search_is_read_only_and_enforces_constraints():
    seen_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={
                "tweets": [
                    {
                        "id": "123456789",
                        "text": "Useful result",
                        "created": 1_700_000_000,
                        "like_count": 3,
                        "author": {"id": "42", "username": "alice", "name": "Alice"},
                    }
                ],
                "has_more": True,
                "next_cursor": "next-page",
            },
        )

    client = XquikClient("xq_test", base_url="https://xquik.test/api/v1")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://xquik.test/api/v1",
        transport=httpx.MockTransport(handler),
        headers={"x-api-key": "xq_test", "xquik-api-contract": "2026-04-29"},
    )
    page = await client.search_posts(
        search_call_id="src_1",
        query="OpenRouter pricing",
        limit=10,
        constraints=ResearchConstraints(
            language="en",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 8, 1),
            include_retweets=False,
        ),
    )
    await client.aclose()

    assert seen_request is not None
    assert seen_request.method == "GET"
    query = seen_request.url.params["q"]
    assert "lang:en" in query
    assert "since:2026-07-01" in query
    assert "until:2026-08-01" in query
    assert "-is:retweet" in query
    assert page.posts[0].url == "https://x.com/alice/status/123456789"
    assert page.next_cursor == "next-page"


@pytest.mark.asyncio
async def test_xquik_errors_do_not_expose_api_key():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthenticated"})

    client = XquikClient("xq_super_secret", base_url="https://xquik.test/api/v1")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://xquik.test/api/v1", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(XquikError) as error:
        await client.check_connection()
    await client.aclose()

    assert "xq_super_secret" not in str(error.value)
