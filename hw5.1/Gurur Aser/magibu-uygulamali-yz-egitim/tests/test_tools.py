from __future__ import annotations

from dataclasses import dataclass

from les8.tools import MAX_SEARCH_RESULTS, TOOL_SCHEMAS, PantryTools


@dataclass
class FakePantryError(Exception):
    code: str
    message: str


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def list_items(self, expiring_within_days: int = 7, include_expired: bool = True):
        self.calls.append(("list_items", (expiring_within_days, include_expired), {}))
        return {"items": [{"id": "egg-1"}], "today": "2026-08-12", "count": 1}

    def add_item(self, **kwargs):
        self.calls.append(("add_item", (), kwargs))
        return {"item": {"id": "new-1", **kwargs}}

    def consume_item(self, item_id: str, quantity: float):
        self.calls.append(("consume_item", (item_id, quantity), {}))
        return {"item": {"id": item_id, "quantity": 1}, "deleted": False}

    def remove_item(self, item_id: str):
        self.calls.append(("remove_item", (item_id,), {}))
        return {"removed_item": {"id": item_id}}


class FakeDDGS:
    def __init__(self, *args, **kwargs) -> None:
        self.init_args = args
        self.init_kwargs = kwargs
        self.calls: list[tuple[str, dict]] = []

    def text(self, query: str, **kwargs):
        self.calls.append((query, kwargs))
        return [
            {
                "title": "  Tarif başlığı  ",
                "href": "https://example.test/recipe",
                "body": "  Güvenilmeyen açıklama " + ("x" * 500),
                "extra": "must not escape",
            },
            {"title": "İkinci", "url": "https://example.test/two", "snippet": "Kısa"},
        ]


def test_tool_schemas_have_exact_public_contract():
    names = [item["function"]["name"] for item in TOOL_SCHEMAS]
    assert names == [
        "list_pantry",
        "internet_search",
        "add_pantry_item",
        "consume_pantry_item",
        "remove_pantry_item",
    ]
    for item in TOOL_SCHEMAS:
        parameters = item["function"]["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
    assert set(
        next(item for item in TOOL_SCHEMAS if item["function"]["name"] == "add_pantry_item")["function"]["parameters"]["required"]
    ) == {"name", "quantity", "unit", "category", "expires_on"}
    assert MAX_SEARCH_RESULTS == 3


def test_registry_delegates_all_pantry_tools_without_mutation_gate():
    store = FakeStore()
    tools = PantryTools(store, ddgs_client=FakeDDGS())
    registry = tools.registry()
    assert set(registry) == {
        "list_pantry",
        "internet_search",
        "add_pantry_item",
        "consume_pantry_item",
        "remove_pantry_item",
    }

    assert registry["list_pantry"](3, False)["count"] == 1
    assert registry["add_pantry_item"]("yumurta", 2, "adet", "süt ürünleri", "2026-08-20")["item"]["id"] == "new-1"
    assert registry["consume_pantry_item"]("egg-1", 1)["deleted"] is False
    assert registry["remove_pantry_item"]("egg-1")["removed_item"]["id"] == "egg-1"
    assert [call[0] for call in store.calls] == ["list_items", "add_item", "consume_item", "remove_item"]


def test_internet_search_uses_turkish_safe_capped_provider_and_whitelists_results():
    provider = FakeDDGS()
    result = PantryTools(FakeStore(), ddgs_client=provider).internet_search("  domates tarifi  ", 2)

    assert provider.calls == [
        (
            "domates tarifi",
            {"region": "tr-tr", "safesearch": "moderate", "max_results": 2, "backend": "auto"},
        )
    ]
    assert result["query"] == "domates tarifi"
    assert result["count"] == 2
    assert result["results"][0].keys() == {"title", "url", "snippet"}
    assert result["results"][0]["title"] == "Tarif başlığı"
    assert len(result["results"][0]["snippet"]) <= 400
    assert result["results"][1] == {"title": "İkinci", "url": "https://example.test/two", "snippet": "Kısa"}


def test_invalid_search_arguments_return_structured_validation_errors():
    tools = PantryTools(FakeStore(), ddgs_client=FakeDDGS())
    for query, limit in (("", 3), ("x" * 241, 3), ("query", 0), ("query", 4), ("query", True)):
        result = tools.internet_search(query, limit)
        assert result["error"]["code"] == "VALIDATION_ERROR", result


def test_provider_failure_returns_search_error_without_leaking_exception():
    class BrokenDDGS:
        def text(self, *_args, **_kwargs):
            raise RuntimeError("secret proxy token")

    result = PantryTools(FakeStore(), ddgs_client=BrokenDDGS()).internet_search("tarif", 3)
    assert result == {"error": {"code": "SEARCH_ERROR", "message": "İnternet araması başarısız."}}


def test_pantry_error_is_structured_and_unexpected_store_errors_are_sanitized():
    class BrokenStore(FakeStore):
        def add_item(self, **_kwargs):
            raise FakePantryError("VALIDATION_ERROR", "quantity invalid")

        def remove_item(self, _item_id):
            raise RuntimeError("database path secret")

    tools = PantryTools(BrokenStore(), ddgs_client=FakeDDGS())
    assert tools.add_pantry_item("yumurta", 0, "adet", "gıda", "2026-08-20") == {
        "error": {"code": "VALIDATION_ERROR", "message": "quantity invalid"}
    }
    assert tools.remove_pantry_item("egg-1") == {
        "error": {"code": "STORAGE_ERROR", "message": "Envanter işlemi tamamlanamadı."}
    }
