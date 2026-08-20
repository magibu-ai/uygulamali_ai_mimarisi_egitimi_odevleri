from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from assistant.action_schema import ActionPlan, ActionType
from assistant.tool_call_parser import ParsedToolCall


@dataclass
class ConversationState:
    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_search_barcodes: list[str] = field(default_factory=list)
    last_detail_barcodes: list[str] = field(default_factory=list)
    last_selected_barcodes: list[str] = field(default_factory=list)
    last_mutated_barcodes: list[str] = field(default_factory=list)
    shopping_quantities: dict[str, int] = field(default_factory=dict)

    def planner_context(self, max_products: int = 20) -> dict[str, Any]:
        ordered_barcodes = list(
            dict.fromkeys(
                self.last_selected_barcodes
                + self.last_detail_barcodes
                + self.last_mutated_barcodes
                + self.last_search_barcodes
                + list(self.products)
            )
        )[:max_products]
        return {
            "known_products": [
                {
                    "barcode": barcode,
                    "name": self.products.get(barcode, {}).get("name"),
                    "brand": self.products.get(barcode, {}).get("brand"),
                    "shopping_quantity": self.shopping_quantities.get(barcode, 0),
                }
                for barcode in ordered_barcodes
            ],
            "last_search_barcodes": self.last_search_barcodes[:10],
            "last_detail_barcodes": self.last_detail_barcodes[:10],
            "last_selected_barcodes": self.last_selected_barcodes[:10],
            "last_mutated_barcodes": self.last_mutated_barcodes[:10],
        }

    def update(
        self,
        plan: ActionPlan,
        calls_and_results: list[tuple[ParsedToolCall, dict[str, Any]]],
    ) -> None:
        successful_barcodes: list[str] = []

        for call, result in calls_and_results:
            if not result.get("success"):
                continue

            if call.name == "search_products":
                products = result.get("products") or []
                barcodes: list[str] = []
                for product in products:
                    barcode = str(product.get("barcode") or "").strip()
                    if not barcode:
                        continue
                    self.products[barcode] = product
                    barcodes.append(barcode)
                self.last_search_barcodes = list(dict.fromkeys(barcodes))
                # Search results are candidates, not an explicit selection. Keeping
                # last_selected intact prevents a later search from destroying context.
                continue

            if call.name in {
                "get_product_details",
                "add_to_shopping_list",
                "ensure_in_shopping_list",
                "set_shopping_list_quantity",
                "remove_from_shopping_list",
            }:
                product = result.get("product") or {}
                barcode = str(product.get("barcode") or call.arguments.get("barcode") or "").strip()
                if barcode:
                    if product:
                        self.products[barcode] = product
                    successful_barcodes.append(barcode)
                    if call.name != "get_product_details":
                        self.shopping_quantities[barcode] = int(result.get("quantity", 0))
                        if self.shopping_quantities[barcode] <= 0:
                            self.shopping_quantities.pop(barcode, None)
                continue

            if call.name == "get_shopping_list":
                self.shopping_quantities.clear()
                for item in result.get("items") or []:
                    barcode = str(item.get("barcode") or "").strip()
                    if barcode:
                        existing = self.products.get(barcode, {})
                        self.products[barcode] = {
                            **existing,
                            "barcode": barcode,
                            "name": item.get("product_name") or existing.get("name"),
                            "brand": item.get("brand") or existing.get("brand"),
                            "image_url": item.get("image_url") or existing.get("image_url"),
                            "nutrition_grade": item.get("nutrition_grade") or existing.get("nutrition_grade"),
                        }
                        self.shopping_quantities[barcode] = int(item.get("quantity", 0))

        successful_barcodes = list(dict.fromkeys(successful_barcodes))
        if not successful_barcodes:
            return
        if plan.action == ActionType.GET_PRODUCT_DETAILS:
            self.last_detail_barcodes = successful_barcodes
            self.last_selected_barcodes = successful_barcodes
        elif plan.action in {
            ActionType.ADD_TO_SHOPPING_LIST,
            ActionType.ENSURE_IN_SHOPPING_LIST,
            ActionType.SET_SHOPPING_LIST_QUANTITY,
            ActionType.REMOVE_FROM_SHOPPING_LIST,
        }:
            self.last_mutated_barcodes = successful_barcodes
            # Do not erase the last detailed set; it is often referenced later as
            # “daha önce detaylarını getirdiğim ürünler”.


class SessionStateStore:
    def __init__(self, max_sessions: int = 256):
        self.max_sessions = max_sessions
        self._states: dict[str, ConversationState] = {}
        self._touched_at: dict[str, float] = {}
        self._lock = threading.RLock()

    def get(self, session_id: str) -> ConversationState:
        key = session_id or "default"
        with self._lock:
            if key not in self._states:
                self._evict_if_needed()
                self._states[key] = ConversationState()
            self._touched_at[key] = time.monotonic()
            return self._states[key]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)
            self._touched_at.pop(session_id, None)

    def _evict_if_needed(self) -> None:
        if len(self._states) < self.max_sessions:
            return
        oldest = min(self._touched_at, key=self._touched_at.get)
        self._states.pop(oldest, None)
        self._touched_at.pop(oldest, None)
