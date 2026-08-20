from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from assistant.action_schema import ActionPlan, ActionType, SelectionScope
from assistant.conversation_state import ConversationState
from assistant.tool_call_parser import ParsedToolCall


@dataclass(frozen=True)
class Resolution:
    calls: list[ParsedToolCall]
    clarification: str | None = None
    candidates: list[str] | None = None


class EntityResolver:
    STOPWORDS = {
        "urun", "urunu", "urunler", "urunleri", "tane", "adet", "ekle", "ekler",
        "ekler misin", "koy", "sepete", "sepet", "listeye", "alisveris", "liste",
        "detay", "detayini", "getir", "goster", "lutfen", "bana", "bu", "o", "bir",
        "iki", "uc", "dort", "olsun", "yap", "sil", "cikar", "azalt", "fazladan",
        "alisveris", "listeme", "listemde", "bunlar", "bunlari", "birini", "eklenmis",
    }

    MUTATION_TOOL_NAMES = {
        ActionType.ADD_TO_SHOPPING_LIST: "add_to_shopping_list",
        ActionType.ENSURE_IN_SHOPPING_LIST: "ensure_in_shopping_list",
        ActionType.SET_SHOPPING_LIST_QUANTITY: "set_shopping_list_quantity",
        ActionType.REMOVE_FROM_SHOPPING_LIST: "remove_from_shopping_list",
    }

    def resolve(self, plan: ActionPlan, state: ConversationState) -> Resolution:
        if plan.action == ActionType.SEARCH_PRODUCTS:
            if not plan.query:
                return Resolution([], "Ne tür bir ürün aramamı istediğini biraz daha açık yazar mısın?")
            arguments: dict[str, Any] = {"query": plan.query, "limit": plan.limit}
            if plan.max_sugars_100g is not None:
                arguments["max_sugars_100g"] = plan.max_sugars_100g
            if plan.excluded_ingredients:
                arguments["excluded_ingredients"] = plan.excluded_ingredients
            return Resolution([ParsedToolCall("search_products", arguments, "resolved_0")])

        if plan.action in {ActionType.GET_SHOPPING_LIST, ActionType.COUNT_SHOPPING_LIST}:
            return Resolution([ParsedToolCall("get_shopping_list", {}, "resolved_0")])

        if plan.action == ActionType.UNKNOWN:
            return Resolution([], "Bu isteği ürün arama, ürün detayı veya alışveriş listesi işlemi olarak anlayamadım.")

        barcodes, clarification, candidates = self._resolve_product_barcodes(plan, state)
        if clarification:
            return Resolution([], clarification, candidates)
        if not barcodes:
            return Resolution([], "Hangi ürünü kastettiğini belirleyemedim. Ürün adını veya barkodunu yazar mısın?")

        if plan.action == ActionType.GET_PRODUCT_DETAILS:
            tool_name = "get_product_details"
        else:
            tool_name = self.MUTATION_TOOL_NAMES.get(plan.action)
            if tool_name is None:
                return Resolution([], "Bu alışveriş listesi işlemi henüz desteklenmiyor.")

        calls: list[ParsedToolCall] = []
        for index, barcode in enumerate(barcodes):
            arguments: dict[str, Any] = {"barcode": barcode}
            if tool_name == "add_to_shopping_list":
                arguments["quantity"] = plan.quantity
            elif tool_name == "ensure_in_shopping_list":
                arguments["minimum_quantity"] = plan.quantity
            elif tool_name == "set_shopping_list_quantity":
                arguments["quantity"] = plan.quantity
            elif tool_name == "remove_from_shopping_list":
                arguments["quantity"] = plan.quantity
                arguments["remove_all"] = plan.remove_all
            calls.append(ParsedToolCall(tool_name, arguments, f"resolved_{index}"))
        return Resolution(calls)

    def _resolve_product_barcodes(
        self, plan: ActionPlan, state: ConversationState
    ) -> tuple[list[str], str | None, list[str] | None]:
        if plan.barcodes:
            return plan.barcodes, None, None

        # A named product is more specific than a positional/context selection.
        # For example, product_reference="corn flakes" plus
        # selection=last_selected must resolve Corn Flakes, not the first item in
        # the selected list. Restrict matching to the referenced pool when possible.
        if plan.product_reference:
            scoped_pool = self._pool_for_selection(plan.selection, state)
            matches = self.match_named_products(
                plan.product_reference,
                state,
                pool=scoped_pool or None,
            )
            if len(matches) == 1:
                return matches, None, None
            if len(matches) > 1:
                lines = ["Birden fazla ürün bu ifadeyle eşleşiyor:"]
                for index, barcode in enumerate(matches, start=1):
                    product = state.products.get(barcode, {})
                    lines.append(f"{index}. {product.get('name') or 'İsimsiz ürün'} — Barkod: {barcode}")
                lines.append("Hangisini seçtiğini ürün adı veya barkoduyla belirtir misin?")
                return [], "\n".join(lines), matches

        if plan.selection in {SelectionScope.LAST_SELECTED, SelectionScope.ALL}:
            pool = self._default_pool(state)
            return self._apply_count(pool, plan), None, None

        if plan.selection == SelectionScope.LAST_DETAILS:
            return self._apply_count(state.last_detail_barcodes, plan), None, None

        if plan.selection == SelectionScope.LAST_SEARCH:
            return self._apply_count(state.last_search_barcodes, plan), None, None

        if plan.selection in {SelectionScope.FIRST, SelectionScope.LAST}:
            pool = state.last_search_barcodes or self._default_pool(state)
            count = plan.selection_count or 1
            if count > len(pool):
                return [], f"Yalnızca {len(pool)} doğrulanmış ürün var; {count} ürün seçemiyorum.", None
            selected = pool[-count:] if plan.selection == SelectionScope.LAST else pool[:count]
            return selected, None, None

        pool = self._default_pool(state)
        if len(pool) == 1:
            return pool, None, None
        return [], None, None

    @staticmethod
    def _pool_for_selection(
        selection: SelectionScope,
        state: ConversationState,
    ) -> list[str]:
        if selection == SelectionScope.LAST_DETAILS:
            return state.last_detail_barcodes.copy()
        if selection in {SelectionScope.LAST_SELECTED, SelectionScope.ALL}:
            return EntityResolver._default_pool(state).copy()
        if selection in {SelectionScope.LAST_SEARCH, SelectionScope.FIRST, SelectionScope.LAST}:
            return state.last_search_barcodes.copy()
        return []

    @staticmethod
    def _default_pool(state: ConversationState) -> list[str]:
        return state.last_selected_barcodes or state.last_detail_barcodes or state.last_search_barcodes

    @staticmethod
    def _apply_count(pool: list[str], plan: ActionPlan) -> list[str]:
        if not plan.selection_count:
            return pool.copy()
        return pool[: plan.selection_count]

    def match_named_products(self, reference: str, state: ConversationState, pool: list[str] | None = None) -> list[str]:
        if pool is not None:
            return self._score_candidates(reference, pool, state)
        return self._match_named_products(reference, state)

    def _match_named_products(self, reference: str, state: ConversationState) -> list[str]:
        preferred_pool = self._default_pool(state)
        pools = [preferred_pool, list(state.products)] if preferred_pool else [list(state.products)]
        for pool in pools:
            scored = self._score_candidates(reference, pool, state)
            if scored:
                return scored
        return []

    def _score_candidates(self, reference: str, pool: list[str], state: ConversationState) -> list[str]:
        query_text = self._normalize(reference)
        query_tokens = self._content_tokens(query_text)
        if not query_tokens:
            return []

        scores: list[tuple[float, int, str]] = []
        for position, barcode in enumerate(pool):
            product = state.products.get(barcode, {})
            name_text = self._normalize(str(product.get("name") or ""))
            brand_text = self._normalize(str(product.get("brand") or ""))
            combined_text = " ".join(part for part in (name_text, brand_text) if part).strip()
            candidate_tokens = self._content_tokens(combined_text)
            if not candidate_tokens:
                continue

            if query_text == name_text or query_text == combined_text:
                score = 1.00
            elif query_text and query_text in name_text:
                score = 0.97
            elif name_text and name_text in query_text:
                score = 0.95
            else:
                matched_query_tokens = 0
                matched_candidate_tokens: set[str] = set()
                for query_token in query_tokens:
                    best_token = None
                    best_ratio = 0.0
                    for candidate_token in candidate_tokens:
                        ratio = (
                            1.0
                            if query_token == candidate_token
                            else SequenceMatcher(None, query_token, candidate_token).ratio()
                        )
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_token = candidate_token
                    if best_ratio >= 0.82:
                        matched_query_tokens += 1
                        if best_token:
                            matched_candidate_tokens.add(best_token)

                query_coverage = matched_query_tokens / max(len(query_tokens), 1)
                candidate_coverage = len(matched_candidate_tokens) / max(len(candidate_tokens), 1)
                similarity = max(
                    SequenceMatcher(None, query_text, name_text).ratio(),
                    SequenceMatcher(None, query_text, combined_text).ratio(),
                )
                if query_coverage < 0.75:
                    continue
                score = query_coverage * 0.62 + candidate_coverage * 0.18 + similarity * 0.20

            if score >= 0.72:
                scores.append((score, position, barcode))

        if not scores:
            return []
        scores.sort(key=lambda item: (-item[0], item[1]))
        best_score = scores[0][0]
        return [barcode for score, _, barcode in scores if best_score - score <= 0.025]

    @classmethod
    def _content_tokens(cls, normalized: str) -> set[str]:
        tokens: set[str] = set()
        for raw_token in normalized.split():
            token = cls._stem(raw_token)
            if len(token) >= 3 and token not in cls.STOPWORDS:
                tokens.add(token)
        return tokens

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.casefold().replace("ı", "i")
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())

    @staticmethod
    def _stem(token: str) -> str:
        suffixes = (
            "lerden", "lardan", "lerin", "larin", "den", "dan", "ten", "tan", "leri",
            "lari", "ler", "lar", "nin", "in", "un", "li", "lu", "lik", "yi", "yu", "i", "u",
        )
        for suffix in suffixes:
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                return token[: -len(suffix)]
        return token
