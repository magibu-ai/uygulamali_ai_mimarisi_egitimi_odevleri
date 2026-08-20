from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from x_research_agent.domain.schemas import (
    ResearchConstraints,
    SearchPage,
    SortMode,
    XAuthor,
    XPost,
)


class XquikError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class XquikClient:
    """Strict read-only client. Only explicit GET methods are implemented."""

    def __init__(self, api_key: str, *, base_url: str, timeout: float = 30.0):
        if not api_key.strip():
            raise ValueError("Xquik API key is required")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "x-api-key": api_key.strip(),
                "xquik-api-contract": "2026-04-29",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def __aenter__(self) -> XquikClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check_connection(self) -> dict[str, Any]:
        data = await self._get("/account")
        credit = data.get("credit_info") or data.get("creditInfo") or {}
        return {
            "connected": True,
            "plan": data.get("plan"),
            "credit_balance": credit.get("balance"),
        }

    async def search_posts(
        self,
        *,
        search_call_id: str,
        query: str,
        limit: int,
        constraints: ResearchConstraints,
        cursor: str | None = None,
    ) -> SearchPage:
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        if not 1 <= limit <= 200:
            raise ValueError("Xquik search limit must be between 1 and 200")
        effective_query = self._apply_constraints(query, constraints)
        params: dict[str, str | int] = {
            "q": effective_query,
            "limit": limit,
            "queryType": self._query_type(constraints.sort),
        }
        if cursor:
            params["cursor"] = cursor
        data = await self._get("/x/tweets/search", params=params)
        posts = [self._normalize_post(item) for item in data.get("tweets", [])]
        return SearchPage(
            search_call_id=search_call_id,
            query=effective_query,
            posts=posts,
            has_more=bool(data.get("has_more", data.get("has_next_page", False))),
            next_cursor=data.get("next_cursor"),
        )

    async def get_post(self, post_id_or_url: str) -> XPost:
        post_id = self._extract_post_id(post_id_or_url)
        data = await self._get(f"/x/tweets/{post_id}")
        tweet = data.get("tweet", data)
        if "author" not in tweet and data.get("author"):
            tweet = {**tweet, "author": data["author"]}
        return self._normalize_post(tweet)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = await self._client.get(path, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise XquikError("Xquik is temporarily unreachable", retryable=True) from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = payload.get("error", {})
            if isinstance(error, dict):
                code = error.get("code") or error.get("type")
                detail = error.get("message")
            else:
                code = error
                detail = payload.get("message")
            safe_message = detail or code or f"Xquik request failed ({response.status_code})"
            raise XquikError(
                str(safe_message),
                status_code=response.status_code,
                retryable=response.status_code in {424, 429, 500, 502, 503, 504},
            )
        return response.json()

    @staticmethod
    def _apply_constraints(query: str, constraints: ResearchConstraints) -> str:
        parts = [query.strip()]
        if constraints.language:
            parts.append(f"lang:{constraints.language}")
        if constraints.start_date:
            parts.append(f"since:{constraints.start_date.isoformat()}")
        if constraints.end_date:
            parts.append(f"until:{constraints.end_date.isoformat()}")
        if not constraints.include_retweets:
            parts.append("-is:retweet")
        return " ".join(parts)

    @staticmethod
    def _query_type(sort: SortMode) -> str:
        return {SortMode.LATEST: "Latest", SortMode.TOP: "Top"}.get(sort, "Top")

    @staticmethod
    def _extract_post_id(value: str) -> str:
        raw = value.strip()
        if "/" not in raw:
            post_id = raw
        else:
            parsed = urlparse(raw)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                status_index = parts.index("status")
                post_id = parts[status_index + 1]
            except (ValueError, IndexError) as exc:
                raise ValueError("Invalid X post URL") from exc
        if not post_id.isdigit() or not 5 <= len(post_id) <= 30:
            raise ValueError("X post ID must be numeric")
        return post_id

    @staticmethod
    def _normalize_post(item: dict[str, Any]) -> XPost:
        author_data = item.get("author") or {}
        username = author_data.get("username") or "unknown"
        created_raw = item.get("created") or item.get("created_at") or item.get("createdAt")
        created_at: datetime | None = None
        if isinstance(created_raw, (int, float)):
            created_at = datetime.fromtimestamp(created_raw, tz=timezone.utc)
        elif isinstance(created_raw, str):
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                created_at = None
        post_id = str(item.get("id", ""))
        return XPost(
            id=post_id,
            text=item.get("text") or "",
            author=XAuthor(
                id=str(author_data["id"]) if author_data.get("id") is not None else None,
                username=username,
                name=author_data.get("name"),
            ),
            created_at=created_at,
            language=item.get("language") or item.get("lang"),
            like_count=item.get("like_count", item.get("likeCount")),
            repost_count=item.get("retweet_count", item.get("retweetCount")),
            reply_count=item.get("reply_count", item.get("replyCount")),
            view_count=item.get("view_count", item.get("viewCount")),
            url=f"https://x.com/{username}/status/{post_id}",
        )
