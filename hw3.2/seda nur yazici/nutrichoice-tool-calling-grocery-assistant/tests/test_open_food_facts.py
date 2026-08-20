from services.open_food_facts import OpenFoodFactsClient


def test_normalizes_product_fields():
    raw = {
        "code": "12345678",
        "product_name_tr": "Yulaf Ezmesi",
        "brands": "Örnek Marka",
        "ingredients_text_tr": "Yulaf",
        "allergens_tags": ["en:gluten"],
        "nutrition_grades": "a",
        "nutriments": {"sugars_100g": "1.2", "energy-kcal_100g": 360},
    }
    product = OpenFoodFactsClient._normalize_product(raw)
    assert product is not None
    assert product.name == "Yulaf Ezmesi"
    assert product.sugars_100g == 1.2
    assert product.energy_kcal_100g == 360.0


def test_breakfast_query_uses_structured_search_and_nutrient_filter(monkeypatch):
    client = OpenFoodFactsClient(
        "https://world.openfoodfacts.org",
        "NutriChoice/0.1 (contact: test@example.com)",
        max_retries=0,
    )
    captured = {}

    def fake_get(path, *, params, allow_not_found=False):
        captured["path"] = path
        captured["params"] = params
        return {
            "products": [
                {
                    "code": "12345678",
                    "product_name_tr": "Yulaf Ezmesi",
                    "nutriments": {"sugars_100g": 1.2},
                }
            ]
        }

    monkeypatch.setattr(client, "_get", fake_get)
    products = client.search_products(
        "kahvaltılık gevrek", max_sugars_100g=10, limit=5
    )

    assert captured["path"] == "/api/v2/search"
    assert captured["params"]["categories_tags_en"] == "breakfast-cereals"
    assert "sugars_100g<10" in captured["params"]
    assert products[0]["barcode"] == "12345678"


def test_transient_server_error_is_retried(monkeypatch):
    import httpx

    client = OpenFoodFactsClient(
        "https://world.openfoodfacts.org",
        "NutriChoice/0.1 (contact: test@example.com)",
        max_retries=2,
        retry_backoff=0,
    )
    responses = iter(
        [
            httpx.Response(
                503,
                request=httpx.Request("GET", "https://world.openfoodfacts.org/test"),
            ),
            httpx.Response(
                200,
                json={"products": []},
                request=httpx.Request("GET", "https://world.openfoodfacts.org/test"),
            ),
        ]
    )
    monkeypatch.setattr(client.client, "get", lambda *args, **kwargs: next(responses))

    payload = client._get("/test", params={})
    assert payload == {"products": []}
