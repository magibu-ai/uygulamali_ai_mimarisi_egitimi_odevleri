from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import ValidationError

from database.initialize import initialize_database
from database.repositories import (
    ensure_shopping_list_item,
    list_shopping_items,
    log_tool_call,
    remove_shopping_list_item,
    set_shopping_list_item_quantity,
    upsert_shopping_list_item,
)
from services.open_food_facts import OpenFoodFactsClient, OpenFoodFactsError
from tools.schemas import (
    AddToShoppingListArguments,
    EnsureInShoppingListArguments,
    GetProductDetailsArguments,
    GetShoppingListArguments,
    RemoveFromShoppingListArguments,
    SearchProductsArguments,
    SetShoppingListQuantityArguments,
)


class ToolRouter:
    def __init__(self, off_client: OpenFoodFactsClient, user_id: str):
        initialize_database()
        self.off_client = off_client
        self.user_id = user_id
        self._verified_products: dict[str, dict[str, Any]] = {}
        self._tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "search_products": self._search_products,
            "get_product_details": self._get_product_details,
            "add_to_shopping_list": self._add_to_shopping_list,
            "ensure_in_shopping_list": self._ensure_in_shopping_list,
            "set_shopping_list_quantity": self._set_shopping_list_quantity,
            "remove_from_shopping_list": self._remove_from_shopping_list,
            "get_shopping_list": self._get_shopping_list,
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        print(
            f"TOOL_CALL name={name} arguments="
            f"{json.dumps(arguments, ensure_ascii=False, separators=(',', ':'))}",
            flush=True,
        )
        if name not in self._tools:
            result = {
                "success": False,
                "error": "UNKNOWN_TOOL",
                "message": f"Tool is not allowed: {name}",
            }
        else:
            try:
                result = self._tools[name](arguments)
            except ValidationError as exc:
                result = {
                    "success": False,
                    "error": "INVALID_ARGUMENTS",
                    "details": exc.errors(include_url=False),
                }
            except OpenFoodFactsError as exc:
                result = {
                    "success": False,
                    "error": "EXTERNAL_API_ERROR",
                    "message": str(exc),
                }
            except Exception as exc:
                result = {
                    "success": False,
                    "error": "INTERNAL_TOOL_ERROR",
                    "message": str(exc),
                }

        log_tool_call(
            user_id=self.user_id,
            tool_name=name,
            arguments=arguments,
            result=result,
        )
        print(
            f"TOOL_RESULT name={name} success={str(bool(result.get('success'))).lower()} "
            f"result={json.dumps(result, ensure_ascii=False, separators=(',', ':'))}",
            flush=True,
        )
        return result

    def _search_products(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = SearchProductsArguments.model_validate(raw)
        products = self.off_client.search_products(
            args.query,
            max_sugars_100g=args.max_sugars_100g,
            excluded_ingredients=args.excluded_ingredients,
            limit=args.limit,
        )
        for product in products:
            barcode = str(product.get("barcode") or "").strip()
            if barcode:
                self._verified_products[barcode] = product
        return {
            "success": True,
            "query": args.query,
            "count": len(products),
            "products": products,
            "source": "Open Food Facts",
        }

    def _verified_product(self, barcode: str) -> dict[str, Any] | None:
        product = self._verified_products.get(barcode)
        if product is None:
            product = self.off_client.get_product(barcode)
        if product is not None:
            self._verified_products[barcode] = product
        return product

    def _get_product_details(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = GetProductDetailsArguments.model_validate(raw)
        product = self._verified_product(args.barcode)
        if product is None:
            return {"success": False, "error": "PRODUCT_NOT_FOUND", "barcode": args.barcode}
        return {"success": True, "product": product, "source": "Open Food Facts"}

    def _add_to_shopping_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = AddToShoppingListArguments.model_validate(raw)
        product = self._verified_product(args.barcode)
        if product is None:
            return {"success": False, "error": "PRODUCT_NOT_FOUND", "barcode": args.barcode}
        total_quantity = upsert_shopping_list_item(
            user_id=self.user_id,
            barcode=product["barcode"],
            product_name=product["name"],
            brand=product.get("brand"),
            quantity=args.quantity,
            image_url=product.get("image_url"),
            nutrition_grade=product.get("nutrition_grade"),
        )
        return {
            "success": True,
            "action": "shopping_list_incremented",
            "product": product,
            "added_quantity": args.quantity,
            "quantity": total_quantity,
        }

    def _ensure_in_shopping_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = EnsureInShoppingListArguments.model_validate(raw)
        product = self._verified_product(args.barcode)
        if product is None:
            return {"success": False, "error": "PRODUCT_NOT_FOUND", "barcode": args.barcode}
        total, changed = ensure_shopping_list_item(
            user_id=self.user_id,
            barcode=product["barcode"],
            product_name=product["name"],
            brand=product.get("brand"),
            minimum_quantity=args.minimum_quantity,
            image_url=product.get("image_url"),
            nutrition_grade=product.get("nutrition_grade"),
        )
        return {
            "success": True,
            "action": "shopping_list_ensured",
            "product": product,
            "minimum_quantity": args.minimum_quantity,
            "quantity": total,
            "changed": changed,
        }

    def _set_shopping_list_quantity(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = SetShoppingListQuantityArguments.model_validate(raw)
        product = self._verified_product(args.barcode)
        if product is None:
            return {"success": False, "error": "PRODUCT_NOT_FOUND", "barcode": args.barcode}
        previous, total = set_shopping_list_item_quantity(
            user_id=self.user_id,
            barcode=product["barcode"],
            product_name=product["name"],
            brand=product.get("brand"),
            quantity=args.quantity,
            image_url=product.get("image_url"),
            nutrition_grade=product.get("nutrition_grade"),
        )
        return {
            "success": True,
            "action": "shopping_list_quantity_set",
            "product": product,
            "previous_quantity": previous,
            "quantity": total,
        }

    def _remove_from_shopping_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = RemoveFromShoppingListArguments.model_validate(raw)
        result = remove_shopping_list_item(
            user_id=self.user_id,
            barcode=args.barcode,
            quantity=args.quantity,
            remove_all=args.remove_all,
        )
        if result is None:
            return {
                "success": False,
                "error": "ITEM_NOT_IN_SHOPPING_LIST",
                "barcode": args.barcode,
            }
        product = self._verified_products.get(args.barcode) or {
            "barcode": result["barcode"],
            "name": result["product_name"],
            "brand": result.get("brand"),
            "image_url": result.get("image_url"),
            "nutrition_grade": result.get("nutrition_grade"),
        }
        return {
            "success": True,
            "action": "shopping_list_decremented",
            "product": product,
            "removed_quantity": result["removed_quantity"],
            "quantity": result["remaining_quantity"],
            "removed_all": result["removed_all"],
        }

    def _get_shopping_list(self, raw: dict[str, Any]) -> dict[str, Any]:
        GetShoppingListArguments.model_validate(raw)
        items = list_shopping_items(self.user_id)
        return {"success": True, "count": len(items), "items": items}
