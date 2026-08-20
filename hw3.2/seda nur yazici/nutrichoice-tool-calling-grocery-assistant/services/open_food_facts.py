from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


class OpenFoodFactsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Product:
    barcode: str
    name: str
    brand: str | None
    ingredients_text: str | None
    allergens: list[str]
    nutrition_grade: str | None
    sugars_100g: float | None
    fat_100g: float | None
    salt_100g: float | None
    proteins_100g: float | None
    energy_kcal_100g: float | None
    image_url: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brand": self.brand,
            "ingredients_text": self.ingredients_text,
            "allergens": self.allergens,
            "nutrition_grade": self.nutrition_grade,
            "nutriments": {
                "sugars_100g": self.sugars_100g,
                "fat_100g": self.fat_100g,
                "salt_100g": self.salt_100g,
                "proteins_100g": self.proteins_100g,
                "energy_kcal_100g": self.energy_kcal_100g,
            },
            "image_url": self.image_url,
        }


class OpenFoodFactsClient:
    SEARCH_FIELDS = ",".join(
        [
            "code",
            "product_name",
            "product_name_tr",
            "product_name_en",
            "brands",
            "ingredients_text",
            "ingredients_text_tr",
            "ingredients_text_en",
            "allergens_tags",
            "nutrition_grades",
            "nutriments",
            "image_front_small_url",
        ]
    )

    # Use the structured search API for concepts that map cleanly to an OFF category.
    # This is more reliable than asking the legacy full-text endpoint to interpret a
    # Turkish natural-language phrase.
    CATEGORY_ALIASES = {
        "breakfast-cereals": (
            "kahvaltılık gevrek",
            "kahvaltilik gevrek",
            "kahvaltılık ürün",
            "kahvaltilik urun",
            "breakfast cereal",
            "breakfast cereals",
            "cereal",
            "corn flakes",
            "muesli",
            "müsli",
            "granola",
            "yulaf ezmesi",
        )
    }

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff: float = 0.6,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, max_retries)
        self.retry_backoff = max(0.0, retry_backoff)
        self.debug = os.getenv("DEBUG_OFF_API", "0") == "1"
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )
        self._search_cache: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

    @classmethod
    def from_environment(cls) -> "OpenFoodFactsClient":
        return cls(
            base_url=os.getenv("OFF_BASE_URL", "https://world.openfoodfacts.org"),
            user_agent=os.getenv(
                "OFF_USER_AGENT",
                "NutriChoice/0.1 (contact: your-email@example.com)",
            ),
            timeout=float(os.getenv("OFF_TIMEOUT_SECONDS", "15")),
            max_retries=int(os.getenv("OFF_MAX_RETRIES", "2")),
            retry_backoff=float(os.getenv("OFF_RETRY_BACKOFF_SECONDS", "0.6")),
        )

    def search_products(
        self,
        query: str,
        *,
        max_sugars_100g: float | None = None,
        excluded_ingredients: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        cache_key = (
            query.casefold().strip(),
            max_sugars_100g,
            tuple(value.casefold().strip() for value in (excluded_ingredients or [])),
            limit,
        )
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return [dict(product) for product in cached]

        category = self._detect_category(query)
        errors: list[str] = []
        raw_products: list[Any] | None = None

        # Prefer the structured v2 endpoint whenever the intent can be represented by
        # category/nutrient filters. Fall back to the legacy full-text endpoint if the
        # structured endpoint is temporarily unavailable or returns no usable products.
        if category:
            try:
                raw_products = self._structured_search(
                    category=category,
                    max_sugars_100g=max_sugars_100g,
                    limit=limit,
                )
            except OpenFoodFactsError as exc:
                errors.append(str(exc))

        if not raw_products:
            try:
                raw_products = self._legacy_search(query=query, limit=limit)
            except OpenFoodFactsError as exc:
                errors.append(str(exc))
                if raw_products is None:
                    raw_products = []

        if not raw_products and errors:
            # Both routes failed. Return the most recent, concrete error.
            raise OpenFoodFactsError(errors[-1])

        products = self._filter_and_normalize_products(
            raw_products or [],
            max_sugars_100g=max_sugars_100g,
            excluded_ingredients=excluded_ingredients,
            limit=limit,
        )
        self._search_cache[cache_key] = [dict(product) for product in products]
        return products

    def _structured_search(
        self,
        *,
        category: str,
        max_sugars_100g: float | None,
        limit: int,
    ) -> list[Any]:
        params: dict[str, Any] = {
            "categories_tags_en": category,
            "page": 1,
            "page_size": min(max(limit * 5, 20), 50),
            "fields": self.SEARCH_FIELDS,
        }
        if max_sugars_100g is not None:
            # OFF v2 nutrient filters are represented as dynamic query keys, e.g.
            # `sugars_100g<10`.
            params[f"sugars_100g<{max_sugars_100g:g}"] = ""

        response = self._get("/api/v2/search", params=params)
        products = response.get("products", [])
        if not isinstance(products, list):
            raise OpenFoodFactsError("Unexpected structured search response.")
        return products

    def _legacy_search(self, *, query: str, limit: int) -> list[Any]:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": min(max(limit * 5, 20), 50),
            "fields": self.SEARCH_FIELDS,
        }
        response = self._get("/cgi/search.pl", params=params)
        products = response.get("products", [])
        if not isinstance(products, list):
            raise OpenFoodFactsError("Unexpected full-text search response.")
        return products

    def _filter_and_normalize_products(
        self,
        raw_products: list[Any],
        *,
        max_sugars_100g: float | None,
        excluded_ingredients: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        excluded = [value.casefold() for value in (excluded_ingredients or [])]
        output: list[dict[str, Any]] = []
        seen_barcodes: set[str] = set()

        for raw in raw_products:
            if not isinstance(raw, dict):
                continue
            product = self._normalize_product(raw)
            if product is None or product.barcode in seen_barcodes:
                continue
            if max_sugars_100g is not None:
                if product.sugars_100g is None or product.sugars_100g > max_sugars_100g:
                    continue
            ingredient_text = (product.ingredients_text or "").casefold()
            if excluded and any(term in ingredient_text for term in excluded):
                continue

            seen_barcodes.add(product.barcode)
            output.append(product.as_dict())
            if len(output) >= limit:
                break
        return output

    @classmethod
    def _detect_category(cls, query: str) -> str | None:
        normalized = query.casefold().strip()
        for category, aliases in cls.CATEGORY_ALIASES.items():
            if any(alias in normalized for alias in aliases):
                return category
        return None

    def get_product(self, barcode: str) -> dict[str, Any] | None:
        fields = self.SEARCH_FIELDS
        try:
            response = self._get(
                f"/api/v3/product/{barcode}",
                params={"fields": fields, "lc": "tr"},
                allow_not_found=True,
            )
        except OpenFoodFactsError:
            response = self._get(
                f"/api/v2/product/{barcode}",
                params={"fields": fields},
                allow_not_found=True,
            )

        if not response:
            return None
        raw = response.get("product")
        if not isinstance(raw, dict):
            return None
        product = self._normalize_product(raw, fallback_barcode=barcode)
        return product.as_dict() if product else None

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any],
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: OpenFoodFactsError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = OpenFoodFactsError(
                    f"Open Food Facts request failed: {type(exc).__name__}."
                )
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise last_error from exc

            if self.debug:
                print(
                    f"OFF_API path={path} status={response.status_code} "
                    f"attempt={attempt + 1}/{self.max_retries + 1}",
                    flush=True,
                )

            if response.status_code == 404 and allow_not_found:
                return {}
            if response.status_code == 429:
                raise OpenFoodFactsError(
                    "Open Food Facts rate limit reached. Wait about one minute and try again."
                )
            if response.status_code in {500, 502, 503, 504}:
                last_error = OpenFoodFactsError(
                    f"Open Food Facts temporarily returned HTTP {response.status_code}."
                )
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise last_error

            try:
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OpenFoodFactsError(
                    f"Invalid response from Open Food Facts (HTTP {response.status_code})."
                ) from exc
            if not isinstance(payload, dict):
                raise OpenFoodFactsError("Unexpected response type from Open Food Facts.")
            return payload

        raise last_error or OpenFoodFactsError("Open Food Facts request failed.")

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.retry_backoff * (2**attempt)
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _normalize_product(
        raw: dict[str, Any], fallback_barcode: str | None = None
    ) -> Product | None:
        barcode = str(raw.get("code") or fallback_barcode or "").strip()
        name = str(
            raw.get("product_name_tr")
            or raw.get("product_name")
            or raw.get("product_name_en")
            or ""
        ).strip()
        if not barcode or not name:
            return None

        ingredients = (
            raw.get("ingredients_text_tr")
            or raw.get("ingredients_text")
            or raw.get("ingredients_text_en")
        )
        allergens = raw.get("allergens_tags") or []
        if not isinstance(allergens, list):
            allergens = []
        nutriments = raw.get("nutriments") or {}
        if not isinstance(nutriments, dict):
            nutriments = {}

        return Product(
            barcode=barcode,
            name=name,
            brand=OpenFoodFactsClient._optional_text(raw.get("brands")),
            ingredients_text=OpenFoodFactsClient._optional_text(ingredients),
            allergens=[str(item) for item in allergens],
            nutrition_grade=OpenFoodFactsClient._optional_text(
                raw.get("nutrition_grades")
            ),
            sugars_100g=OpenFoodFactsClient._optional_float(
                nutriments.get("sugars_100g")
            ),
            fat_100g=OpenFoodFactsClient._optional_float(nutriments.get("fat_100g")),
            salt_100g=OpenFoodFactsClient._optional_float(
                nutriments.get("salt_100g")
            ),
            proteins_100g=OpenFoodFactsClient._optional_float(
                nutriments.get("proteins_100g")
            ),
            energy_kcal_100g=OpenFoodFactsClient._optional_float(
                nutriments.get("energy-kcal_100g")
                or nutriments.get("energy_kcal_100g")
            ),
            image_url=OpenFoodFactsClient._optional_text(
                raw.get("image_front_small_url")
            ),
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
