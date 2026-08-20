from __future__ import annotations

from typing import Any

from tools.tool_router import ToolRouter


SAMPLE_PRODUCT = {
    "barcode": "3017620422003",
    "name": "Sample Hazelnut Spread",
    "brand": "Sample Brand",
    "ingredients_text": "Sugar, hazelnuts",
    "allergens": ["en:nuts"],
    "nutrition_grade": "e",
    "nutriments": {
        "sugars_100g": 56.3,
        "fat_100g": 30.9,
        "salt_100g": 0.1,
        "proteins_100g": 6.3,
        "energy_kcal_100g": 539.0,
    },
    "image_url": None,
}


class FakeOpenFoodFactsClient:
    def search_products(self, query: str, **kwargs: Any):
        return [SAMPLE_PRODUCT]

    def get_product(self, barcode: str):
        if barcode == SAMPLE_PRODUCT["barcode"]:
            return SAMPLE_PRODUCT
        return None


def test_unknown_tool_is_rejected(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")
    result = router.execute("delete_database", {})
    assert result["success"] is False
    assert result["error"] == "UNKNOWN_TOOL"


def test_extra_arguments_are_rejected(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")
    result = router.execute(
        "get_product_details",
        {"barcode": SAMPLE_PRODUCT["barcode"], "invented": True},
    )
    assert result["success"] is False
    assert result["error"] == "INVALID_ARGUMENTS"


def test_unverified_product_is_not_added(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")
    result = router.execute(
        "add_to_shopping_list", {"barcode": "12345678", "quantity": 1}
    )
    assert result["success"] is False
    assert result["error"] == "PRODUCT_NOT_FOUND"


def test_add_and_read_shopping_list(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")

    first = router.execute(
        "add_to_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 2},
    )
    second = router.execute(
        "add_to_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 1},
    )
    shopping_list = router.execute("get_shopping_list", {})

    assert first["success"] is True
    assert second["quantity"] == 3
    assert shopping_list["count"] == 1
    assert shopping_list["items"][0]["quantity"] == 3


def test_numeric_barcode_is_defensively_normalized(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")
    result = router.execute(
        "get_product_details",
        {"barcode": int(SAMPLE_PRODUCT["barcode"])},
    )
    assert result["success"] is True
    assert result["product"]["barcode"] == SAMPLE_PRODUCT["barcode"]


class SearchThenOfflineClient:
    def __init__(self):
        self.get_calls = 0

    def search_products(self, query: str, **kwargs: Any):
        return [SAMPLE_PRODUCT]

    def get_product(self, barcode: str):
        self.get_calls += 1
        raise AssertionError("Verified search result should be reused from cache")


def test_add_reuses_verified_search_result_without_second_api_request(isolated_database):
    client = SearchThenOfflineClient()
    router = ToolRouter(client, "test-user")

    search_result = router.execute("search_products", {"query": "sample"})
    add_result = router.execute(
        "add_to_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 1},
    )

    assert search_result["success"] is True
    assert add_result["success"] is True
    assert client.get_calls == 0


def test_ensure_set_and_remove_quantity(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")

    ensured = router.execute(
        "ensure_in_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "minimum_quantity": 1},
    )
    ensured_again = router.execute(
        "ensure_in_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "minimum_quantity": 1},
    )
    set_result = router.execute(
        "set_shopping_list_quantity",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 3},
    )
    removed = router.execute(
        "remove_from_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 1},
    )
    shopping_list = router.execute("get_shopping_list", {})

    assert ensured["quantity"] == 1
    assert ensured_again["quantity"] == 1
    assert ensured_again["changed"] is False
    assert set_result["quantity"] == 3
    assert removed["quantity"] == 2
    assert shopping_list["items"][0]["quantity"] == 2


def test_remove_all_deletes_item(isolated_database):
    router = ToolRouter(FakeOpenFoodFactsClient(), "test-user")
    router.execute(
        "add_to_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "quantity": 2},
    )
    removed = router.execute(
        "remove_from_shopping_list",
        {"barcode": SAMPLE_PRODUCT["barcode"], "remove_all": True},
    )
    shopping_list = router.execute("get_shopping_list", {})

    assert removed["removed_all"] is True
    assert removed["quantity"] == 0
    assert shopping_list["count"] == 0
