"""Tool-calling boundary for the local pantry assistant.

The storage layer owns pantry validation and persistence.  This module keeps the
model-facing contract stable, turns storage/provider failures into safe
structured results, and sanitizes third-party search rows before they reach the
model context.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

MAX_SEARCH_RESULTS = 3
MAX_SEARCH_QUERY_CHARS = 240
MAX_RESULT_TITLE_CHARS = 160
MAX_RESULT_URL_CHARS = 500
MAX_RESULT_SNIPPET_CHARS = 400
SEARCH_TIMEOUT_SECONDS = 5


def _error(code: str, message: str) -> dict[str, Any]:
    """Return the one error shape consumed by the agent and CLI."""

    return {"error": {"code": str(code), "message": str(message)}}


def _validation(message: str) -> dict[str, Any]:
    return _error("VALIDATION_ERROR", message)


def _store_failure(exc: BaseException) -> dict[str, Any]:
    """Map PantryError-like exceptions while hiding unexpected internals."""

    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None)
    if code is not None and message is not None:
        return _error(str(code), str(message))
    return _error("STORAGE_ERROR", "Envanter işlemi tamamlanamadı.")


def _safe_store_call(method: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result = method(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - storage boundary returns safe errors
        return _store_failure(exc)
    if not isinstance(result, Mapping):
        return _error("STORAGE_ERROR", "Envanter işlemi tamamlanamadı.")
    return dict(result)


def _valid_search_args(query: Any, max_results: Any) -> tuple[str, int] | dict[str, Any]:
    if not isinstance(query, str):
        return _validation("query bir metin olmalıdır.")
    canonical = query.strip()
    if not canonical:
        return _validation("query boş olamaz.")
    if len(canonical) > MAX_SEARCH_QUERY_CHARS:
        return _validation(f"query en fazla {MAX_SEARCH_QUERY_CHARS} karakter olabilir.")
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return _validation("max_results 1 ile 3 arasında bir tam sayı olmalıdır.")
    if not 1 <= max_results <= MAX_SEARCH_RESULTS:
        return _validation("max_results 1 ile 3 arasında olmalıdır.")
    return canonical, max_results


def _clean_search_result(value: Any) -> dict[str, str] | None:
    """Whitelist and bound provider fields; discard unusable rows."""

    if not isinstance(value, Mapping):
        return None
    title_value = value.get("title", "")
    url_value = value.get("href", value.get("url", ""))
    snippet_value = value.get("body", value.get("snippet", ""))
    title = str(title_value or "").strip()[:MAX_RESULT_TITLE_CHARS]
    url = str(url_value or "").strip()[:MAX_RESULT_URL_CHARS]
    snippet = str(snippet_value or "").strip()[:MAX_RESULT_SNIPPET_CHARS]
    # Search output is untrusted content.  Never pass executable/non-web schemes
    # to the model as if they were safe links.
    if url and not url.lower().startswith(("https://", "http://")):
        url = ""
    if not title and not url and not snippet:
        return None
    return {"title": title, "url": url, "snippet": snippet}


def _make_ddgs_client(injected: Any | None) -> Any:
    if injected is None:
        from ddgs import DDGS

        return DDGS(timeout=SEARCH_TIMEOUT_SECONDS)
    # Tests and embedders may inject a DDGS instance, a class, or a factory.
    if isinstance(injected, type):
        try:
            return injected(timeout=SEARCH_TIMEOUT_SECONDS)
        except TypeError:
            return injected()
    if hasattr(injected, "text"):
        return injected
    if callable(injected):
        try:
            return injected(timeout=SEARCH_TIMEOUT_SECONDS)
        except TypeError:
            return injected()
    return injected


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_pantry",
            "description": (
                "Kiler envanterini son kullanma tarihi önceliğiyle listeler. "
                "Tarif önermeden veya stok hakkında konuşmadan önce kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expiring_within_days": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 365,
                        "default": 7,
                        "description": "Bugünden itibaren kaç gün içindeki ürünler listelensin (0-365).",
                    },
                    "include_expired": {
                        "type": "boolean",
                        "default": True,
                        "description": "Geçmiş son kullanma tarihli ürünler dahil edilsin mi?",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": (
                "Tarif veya güncel mutfak bilgisi için güvenli DuckDuckGo araması yapar. "
                "Sonuçlar yalnızca arama parçacıklarıdır; doğrulanmış gıda güvenliği hükmü değildir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": MAX_SEARCH_QUERY_CHARS},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_RESULTS,
                        "default": MAX_SEARCH_RESULTS,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_pantry_item",
            "description": "Envantere ürün ekler; uygulama bu çağrıdan önce kullanıcı onayı istemelidir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "quantity": {"type": "number", "exclusiveMinimum": 0},
                    "unit": {"type": "string", "minLength": 1, "maxLength": 32},
                    "category": {"type": "string", "minLength": 1, "maxLength": 40},
                    "expires_on": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                },
                "required": ["name", "quantity", "unit", "category", "expires_on"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consume_pantry_item",
            "description": "Envanterden ürün tüketir; miktar stoktan fazla olamaz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "quantity": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": ["item_id", "quantity"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_pantry_item",
            "description": "Bir envanter kaydını siler; uygulama bu çağrıdan önce kullanıcı onayı istemelidir.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "string", "minLength": 1}},
                "required": ["item_id"],
                "additionalProperties": False,
            },
        },
    },
]


class PantryTools:
    """Model-facing tools backed by one PantryStore instance."""

    def __init__(self, store: Any, *, ddgs_client: Any | None = None):
        self.store = store
        self._ddgs_client = ddgs_client

    def list_pantry(self, expiring_within_days: int = 7, include_expired: bool = True) -> dict[str, Any]:
        if (
            isinstance(expiring_within_days, bool)
            or not isinstance(expiring_within_days, int)
            or not 0 <= expiring_within_days <= 365
        ):
            return _validation("expiring_within_days 0 ile 365 arasında bir tam sayı olmalıdır.")
        if not isinstance(include_expired, bool):
            return _validation("include_expired boolean olmalıdır.")
        return _safe_store_call(self.store.list_items, expiring_within_days, include_expired)

    def internet_search(self, query: str, max_results: int = MAX_SEARCH_RESULTS) -> dict[str, Any]:
        checked = _valid_search_args(query, max_results)
        if not isinstance(checked, tuple):
            return checked
        canonical, limit = checked
        try:
            provider = _make_ddgs_client(self._ddgs_client)
            raw_results = provider.text(
                canonical,
                region="tr-tr",
                safesearch="moderate",
                max_results=limit,
                backend="auto",
            )
            if raw_results is None:
                raw_results = []
            if isinstance(raw_results, (str, bytes, Mapping)):
                raise TypeError("search provider returned an invalid result collection")
            results: list[dict[str, str]] = []
            for item in raw_results:
                cleaned = _clean_search_result(item)
                if cleaned is not None:
                    results.append(cleaned)
                if len(results) >= limit:
                    break
            return {"query": canonical, "results": results, "count": len(results)}
        except Exception:  # noqa: BLE001 - provider failures become safe model-visible errors
            return _error("SEARCH_ERROR", "İnternet araması başarısız.")

    def add_pantry_item(
        self,
        name: str,
        quantity: float,
        unit: str,
        category: str,
        expires_on: str,
    ) -> dict[str, Any]:
        return _safe_store_call(
            self.store.add_item,
            name=name,
            quantity=quantity,
            unit=unit,
            category=category,
            expires_on=expires_on,
        )

    def consume_pantry_item(self, item_id: str, quantity: float) -> dict[str, Any]:
        return _safe_store_call(self.store.consume_item, item_id, quantity)

    def remove_pantry_item(self, item_id: str) -> dict[str, Any]:
        return _safe_store_call(self.store.remove_item, item_id)

    def registry(self) -> dict[str, Callable[..., dict[str, Any]]]:
        return {
            "list_pantry": self.list_pantry,
            "internet_search": self.internet_search,
            "add_pantry_item": self.add_pantry_item,
            "consume_pantry_item": self.consume_pantry_item,
            "remove_pantry_item": self.remove_pantry_item,
        }

__all__ = [
    "MAX_RESULT_SNIPPET_CHARS",
    "MAX_RESULT_TITLE_CHARS",
    "MAX_RESULT_URL_CHARS",
    "MAX_SEARCH_QUERY_CHARS",
    "MAX_SEARCH_RESULTS",
    "TOOL_SCHEMAS",
    "PantryTools",
]
