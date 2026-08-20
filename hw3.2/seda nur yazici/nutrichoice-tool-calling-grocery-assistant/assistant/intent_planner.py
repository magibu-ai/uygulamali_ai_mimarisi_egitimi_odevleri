from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from pydantic import ValidationError

from assistant.action_schema import (
    PLANNER_TOOL_DEFINITION,
    ActionPlan,
    ActionType,
    ResponseMode,
    SelectionScope,
)
from assistant.conversation_state import ConversationState
from assistant.model_client import ModelClient
from assistant.system_prompt import PLANNER_SYSTEM_PROMPT
from assistant.tool_call_parser import parse_tool_calls, remove_tool_call_markup


class IntentPlanner:
    def __init__(self, model: ModelClient, max_attempts: int = 2):
        self.model = model
        self.max_attempts = max_attempts

    def create_plan(self, user_message: str, state: ConversationState) -> ActionPlan:
        """Backward-compatible single-plan API used by older tests."""
        return self.create_plans(user_message, state)[0]

    def create_plans(self, user_message: str, state: ConversationState) -> list[ActionPlan]:
        payload = {
            "user_message": user_message,
            "conversation_context": state.planner_context(),
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        for attempt in range(self.max_attempts):
            raw_output = self.model.generate(messages, [PLANNER_TOOL_DEFINITION])
            try:
                calls = parse_tool_calls(raw_output)
                planner_calls = [call for call in calls if call.name == "plan_user_action"]
                plans = [ActionPlan.model_validate(call.arguments) for call in planner_calls]
                plans = self._canonicalize_plans(user_message, state, plans)
                plans = self._merge_compatible_plans(self._deduplicate_plans(plans))
                plans = self._enforce_final_invariants(user_message, state, plans)
                if plans and not self._plans_need_repair(user_message, state, plans):
                    self._log_plans("model", plans)
                    return plans
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                print(f"ACTION_PLAN_PARSE_ERROR attempt={attempt + 1} error={exc}", flush=True)

            if attempt + 1 < self.max_attempts:
                messages.append({"role": "assistant", "content": remove_tool_call_markup(raw_output)})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Önceki çıktıyı yok say. Normal metin yazma. Son kullanıcı mesajı "
                            "birden fazla ürün veya işlem içeriyorsa her işlem için ayrı "
                            "plan_user_action çağrısı üret. 'olsun' exact set, 'birini sil' "
                            "remove, 'bunlar' ise conversation_context içindeki seçili ürünlerdir."
                        ),
                    }
                )

        plans = self._canonicalize_plans(
            user_message,
            state,
            self._safe_fallback_plans(user_message, state),
        )
        plans = self._merge_compatible_plans(self._deduplicate_plans(plans))
        plans = self._enforce_final_invariants(user_message, state, plans)
        self._log_plans("safe_fallback", plans)
        return plans

    @staticmethod
    def _log_plans(source: str, plans: list[ActionPlan]) -> None:
        payload = "[" + ",".join(plan.model_dump_json(exclude_none=True) for plan in plans) + "]"
        print(f"ACTION_PLAN source={source} plans={payload}", flush=True)

    @classmethod
    def _canonicalize_plans(
        cls,
        user_message: str,
        state: ConversationState,
        plans: list[ActionPlan],
    ) -> list[ActionPlan]:
        """Compile imperfect model plans into unambiguous, state-aware actions.

        The model decides the semantic intent. This compiler only repairs structural
        contradictions such as a named product combined with a positional selection,
        a missing search query, or a plural context request with one named quantity
        override. It never invents product identifiers; all identifiers come from the
        current structured conversation state or the user's explicit barcodes.
        """
        normalized = cls._normalize(user_message)
        context_pool = cls._context_pool(normalized, state)
        canonical: list[ActionPlan] = []

        for original in plans:
            plan = original

            # A search filter without a query is still a valid natural-language search.
            # Derive the query from the user's message instead of asking a redundant
            # clarification question.
            if plan.action == ActionType.SEARCH_PRODUCTS and not plan.query:
                plan = plan.model_copy(update={"query": cls._search_query(user_message)})

            mutation_actions = {
                ActionType.ADD_TO_SHOPPING_LIST,
                ActionType.ENSURE_IN_SHOPPING_LIST,
                ActionType.SET_SHOPPING_LIST_QUANTITY,
                ActionType.REMOVE_FROM_SHOPPING_LIST,
            }

            if plan.action in mutation_actions:
                exact_quantity = cls._is_exact_quantity_request(normalized)

                # "İki ürün de listemde olsun" contains a product count, not a target
                # quantity for each product. If the model mistakes it for SET, compile
                # it back to ENSURE without lowering an existing quantity.
                if (
                    plan.action == ActionType.SET_SHOPPING_LIST_QUANTITY
                    and cls._is_ensure_request(normalized)
                    and not exact_quantity
                ):
                    plan = plan.model_copy(
                        update={
                            "action": ActionType.ENSURE_IN_SHOPPING_LIST,
                            "quantity": 1,
                        }
                    )

                # "2 tane olacak şekilde / toplam 2 / 2 olsun" expresses a target
                # quantity, not an increment. Apply this only to the named/explicit
                # target; other products in a plural reference are merely ensured.
                if (
                    exact_quantity
                    and plan.action in {
                        ActionType.ADD_TO_SHOPPING_LIST,
                        ActionType.ENSURE_IN_SHOPPING_LIST,
                    }
                    and not cls._is_remove_request(normalized)
                ):
                    plan = plan.model_copy(
                        update={"action": ActionType.SET_SHOPPING_LIST_QUANTITY}
                    )

                # A product name always narrows a positional/context selection. Small
                # models may emit product_reference="corn flakes" together with
                # selection=last_selected; keeping both used to select the first item.
                named_targets: list[str] = []
                if plan.barcodes:
                    # Explicit barcodes are the strongest possible grounding signal.
                    # Never replace them with fuzzy name matches from the wider search
                    # state. This previously caused a single selected product to expand
                    # into every product sharing words such as "avoine" or "flocons".
                    named_targets = plan.barcodes.copy()
                    plan = plan.model_copy(
                        update={
                            "product_reference": None,
                            "selection": SelectionScope.EXPLICIT,
                            "selection_count": None,
                        }
                    )
                elif plan.product_reference:
                    pool = (
                        cls._pool_for_selection(plan.selection, state)
                        or context_pool
                        or cls._preferred_product_pool(state)
                    )
                    named_targets = cls._mentioned_products(plan.product_reference, state, pool)
                    if len(named_targets) == 1:
                        plan = plan.model_copy(
                            update={
                                "barcodes": named_targets,
                                "product_reference": None,
                                "selection": SelectionScope.EXPLICIT,
                                "selection_count": None,
                            }
                        )
                    elif named_targets:
                        # Keep the human-readable reference so EntityResolver can ask
                        # for clarification. Never execute a quantity mutation against
                        # multiple fuzzy matches merely because they share one token.
                        plan = plan.model_copy(
                            update={
                                "selection": SelectionScope.NAMED,
                                "selection_count": 1,
                            }
                        )
                    elif plan.selection not in {
                        SelectionScope.NONE,
                        SelectionScope.EXPLICIT,
                        SelectionScope.NAMED,
                    }:
                        # Preserve the name for the entity resolver, but remove the
                        # contradictory positional selection.
                        plan = plan.model_copy(
                            update={"selection": SelectionScope.NAMED, "selection_count": 1}
                        )

                # Compound request: "bunları ekle, Corn Flakes 2 tane olsun".
                # The named product gets its own quantity action while the remaining
                # products from the referenced set are only ensured in the list.
                if (
                    context_pool
                    and cls._has_plural_context_reference(normalized)
                    and (named_targets or plan.barcodes)
                    and plan.action in {
                        ActionType.ADD_TO_SHOPPING_LIST,
                        ActionType.ENSURE_IN_SHOPPING_LIST,
                        ActionType.SET_SHOPPING_LIST_QUANTITY,
                    }
                ):
                    target_set = set(plan.barcodes)
                    remaining = [barcode for barcode in context_pool if barcode not in target_set]
                    if remaining:
                        canonical.append(
                            ActionPlan(
                                action=ActionType.ENSURE_IN_SHOPPING_LIST,
                                barcodes=remaining,
                                quantity=1,
                            )
                        )

            canonical.append(plan)

        return cls._deduplicate_plans(canonical)

    @staticmethod
    def _pool_for_selection(
        selection: SelectionScope,
        state: ConversationState,
    ) -> list[str]:
        if selection == SelectionScope.LAST_DETAILS:
            return state.last_detail_barcodes.copy()
        if selection in {SelectionScope.LAST_SELECTED, SelectionScope.ALL}:
            return (
                state.last_selected_barcodes
                or state.last_detail_barcodes
                or state.last_search_barcodes
            ).copy()
        if selection in {SelectionScope.FIRST, SelectionScope.LAST, SelectionScope.LAST_SEARCH}:
            return state.last_search_barcodes.copy()
        return []

    @classmethod
    def _enforce_final_invariants(
        cls,
        user_message: str,
        state: ConversationState,
        plans: list[ActionPlan],
    ) -> list[ActionPlan]:
        """Apply non-negotiable grounding rules after model-plan compilation."""
        normalized = cls._normalize(user_message)
        explicit_user_barcodes = list(dict.fromkeys(re.findall(r"\b\d{8,14}\b", user_message)))
        mutation_actions = {
            ActionType.ADD_TO_SHOPPING_LIST,
            ActionType.ENSURE_IN_SHOPPING_LIST,
            ActionType.SET_SHOPPING_LIST_QUANTITY,
            ActionType.REMOVE_FROM_SHOPPING_LIST,
        }
        result: list[ActionPlan] = []

        for plan in plans:
            if plan.action == ActionType.SEARCH_PRODUCTS and not plan.query:
                plan = plan.model_copy(update={"query": cls._search_query(user_message)})

            if plan.barcodes:
                plan = plan.model_copy(
                    update={
                        "product_reference": None,
                        "selection": SelectionScope.EXPLICIT,
                        "selection_count": None,
                    }
                )

            # For a singular named quantity mutation, mutating several products is a
            # safety violation. Re-resolve against the recent conversational pool. If
            # the name is still ambiguous, preserve it as a named reference so the
            # resolver asks the user instead of updating every fuzzy match.
            if (
                plan.action in mutation_actions
                and cls._is_exact_quantity_request(normalized)
                and not cls._has_plural_context_reference(normalized)
                and len(plan.barcodes) > 1
                and not explicit_user_barcodes
            ):
                pool = cls._preferred_product_pool(state)
                matches = cls._mentioned_products(user_message, state, pool)
                if len(matches) == 1:
                    plan = plan.model_copy(update={"barcodes": matches})
                else:
                    plan = plan.model_copy(
                        update={
                            "barcodes": [],
                            "product_reference": user_message,
                            "selection": SelectionScope.NAMED,
                            "selection_count": 1,
                        }
                    )

            result.append(plan)

        return cls._deduplicate_plans(result)

    @staticmethod
    def _preferred_product_pool(state: ConversationState) -> list[str]:
        """Return products in conversational relevance order without duplicates."""
        ordered = (
            state.last_selected_barcodes
            + state.last_detail_barcodes
            + state.last_search_barcodes
            + list(state.products)
        )
        return list(dict.fromkeys(ordered))

    @classmethod
    def _plans_need_repair(
        cls,
        user_message: str,
        state: ConversationState,
        plans: list[ActionPlan],
    ) -> bool:
        normalized = cls._normalize(user_message)
        actions = {plan.action for plan in plans}
        explicit_barcodes = set(re.findall(r"\b\d{8,14}\b", user_message))
        planned_barcodes = {barcode for plan in plans for barcode in plan.barcodes}

        if cls._is_remove_request(normalized) and ActionType.REMOVE_FROM_SHOPPING_LIST not in actions:
            return True
        if cls._is_exact_quantity_request(normalized) and not actions.intersection(
            {ActionType.SET_SHOPPING_LIST_QUANTITY, ActionType.REMOVE_FROM_SHOPPING_LIST}
        ):
            return True
        if explicit_barcodes and not explicit_barcodes.issubset(planned_barcodes):
            # Searches may legitimately contain numeric text, but 8-14 digit values in
            # product/detail/cart requests are barcodes and must not disappear.
            if any(token in normalized for token in ("barkod", "detay", "liste", "sepet", "ekle", "olsun")):
                return True
        if cls._is_count_request(normalized) and ActionType.COUNT_SHOPPING_LIST not in actions:
            return True
        if cls._is_list_request(normalized) and not cls._is_mutation_request(normalized):
            if ActionType.GET_SHOPPING_LIST not in actions and ActionType.COUNT_SHOPPING_LIST not in actions:
                return True

        context_pool = state.last_detail_barcodes or state.last_selected_barcodes
        if cls._has_plural_context_reference(normalized) and len(context_pool) > 1:
            targeted = planned_barcodes.copy()
            for plan in plans:
                if plan.selection in {
                    SelectionScope.LAST_SELECTED,
                    SelectionScope.LAST_DETAILS,
                    SelectionScope.ALL,
                }:
                    targeted.update(context_pool)
            if len(targeted) < 2:
                return True

        # A mutation plan without any resolvable product reference is incomplete.
        mutation_actions = {
            ActionType.ADD_TO_SHOPPING_LIST,
            ActionType.ENSURE_IN_SHOPPING_LIST,
            ActionType.SET_SHOPPING_LIST_QUANTITY,
            ActionType.REMOVE_FROM_SHOPPING_LIST,
        }
        for plan in plans:
            if plan.action in mutation_actions and not (
                plan.barcodes
                or plan.product_reference
                or plan.selection not in {SelectionScope.NONE, SelectionScope.EXPLICIT}
            ):
                return True
        return False

    @classmethod
    def _safe_fallback_plans(
        cls,
        user_message: str,
        state: ConversationState,
    ) -> list[ActionPlan]:
        normalized = cls._normalize(user_message)
        barcodes = re.findall(r"\b\d{8,14}\b", user_message)
        quantity = cls._quantity(user_message)

        if cls._is_count_request(normalized):
            return [ActionPlan(action=ActionType.COUNT_SHOPPING_LIST, response_mode=ResponseMode.COUNT)]
        if cls._is_list_request(normalized) and not cls._is_mutation_request(normalized):
            return [ActionPlan(action=ActionType.GET_SHOPPING_LIST)]

        if cls._is_mutation_request(normalized):
            return cls._fallback_mutation_plans(user_message, state, barcodes, quantity)

        detail_context = any(token in normalized for token in ("detay", "ayrinti", "icerik", "besin"))
        if barcodes or detail_context:
            return [
                ActionPlan(
                    action=ActionType.GET_PRODUCT_DETAILS,
                    barcodes=barcodes,
                    product_reference=None if barcodes else user_message,
                    selection=SelectionScope.EXPLICIT if barcodes else SelectionScope.NAMED,
                )
            ]

        return [
            ActionPlan(
                action=ActionType.SEARCH_PRODUCTS,
                query=cls._search_query(user_message),
                max_sugars_100g=cls._max_sugars(user_message),
                limit=10 if "10" in normalized else 5,
            )
        ]

    @classmethod
    def _fallback_mutation_plans(
        cls,
        user_message: str,
        state: ConversationState,
        barcodes: list[str],
        quantity: int,
    ) -> list[ActionPlan]:
        normalized = cls._normalize(user_message)
        remove_request = cls._is_remove_request(normalized)
        exact_request = cls._is_exact_quantity_request(normalized)
        context_pool = cls._context_pool(normalized, state)
        mentioned = cls._mentioned_products(user_message, state, context_pool or list(state.products))

        if remove_request:
            remove_all = any(token in normalized for token in ("tamamen", "hepsini sil", "listeden kaldir", "tumunu sil"))
            return [
                ActionPlan(
                    action=ActionType.REMOVE_FROM_SHOPPING_LIST,
                    barcodes=barcodes or mentioned,
                    product_reference=None if (barcodes or mentioned) else user_message,
                    selection=(
                        SelectionScope.EXPLICIT
                        if (barcodes or mentioned)
                        else SelectionScope.LAST_SELECTED
                        if cls._has_plural_context_reference(normalized)
                        else SelectionScope.NAMED
                    ),
                    quantity=quantity,
                    remove_all=remove_all,
                )
            ]

        plans: list[ActionPlan] = []
        targets = list(dict.fromkeys(barcodes or mentioned))

        # A plural/backward reference means the previously detailed/selected set should
        # be present, without blindly incrementing existing quantities.
        if context_pool and (
            cls._has_plural_context_reference(normalized)
            or "diger" in normalized
            or cls._is_ensure_request(normalized)
        ):
            base_targets = [barcode for barcode in context_pool if barcode not in targets]
            if base_targets:
                plans.append(
                    ActionPlan(
                        action=ActionType.ENSURE_IN_SHOPPING_LIST,
                        barcodes=base_targets,
                        quantity=1,
                    )
                )

        if plans and not targets:
            return cls._deduplicate_plans(plans)

        if targets:
            action = (
                ActionType.SET_SHOPPING_LIST_QUANTITY
                if exact_request
                else ActionType.ENSURE_IN_SHOPPING_LIST
                if cls._is_ensure_request(normalized)
                else ActionType.ADD_TO_SHOPPING_LIST
            )
            plans.append(ActionPlan(action=action, barcodes=targets, quantity=quantity))
        elif context_pool:
            action = (
                ActionType.SET_SHOPPING_LIST_QUANTITY
                if exact_request and len(context_pool) == 1
                else ActionType.ENSURE_IN_SHOPPING_LIST
                if cls._is_ensure_request(normalized) or cls._has_plural_context_reference(normalized)
                else ActionType.ADD_TO_SHOPPING_LIST
            )
            plans.append(
                ActionPlan(
                    action=action,
                    selection=(
                        SelectionScope.LAST_DETAILS
                        if context_pool == state.last_detail_barcodes
                        else SelectionScope.LAST_SELECTED
                    ),
                    quantity=quantity,
                )
            )
        else:
            action = (
                ActionType.SET_SHOPPING_LIST_QUANTITY
                if exact_request
                else ActionType.ENSURE_IN_SHOPPING_LIST
                if cls._is_ensure_request(normalized)
                else ActionType.ADD_TO_SHOPPING_LIST
            )
            plans.append(
                ActionPlan(
                    action=action,
                    product_reference=user_message,
                    selection=SelectionScope.NAMED,
                    quantity=quantity,
                )
            )

        return cls._deduplicate_plans(plans)

    @classmethod
    def _context_pool(cls, normalized: str, state: ConversationState) -> list[str]:
        backward_tokens = (
            "daha once", "az once", "detaylarini getirdigim", "barkodunu", "barkodlarini",
            "demistim", "sectigim", "secmistim", "diger",
        )
        if any(token in normalized for token in backward_tokens) and state.last_detail_barcodes:
            return state.last_detail_barcodes.copy()
        if cls._has_plural_context_reference(normalized):
            return (state.last_selected_barcodes or state.last_detail_barcodes).copy()
        return []

    @classmethod
    def _mentioned_products(
        cls,
        message: str,
        state: ConversationState,
        pool: list[str],
    ) -> list[str]:
        """Match a named reference conservatively within the supplied product pool.

        Exact/phrase matches outrank token overlap. A one-word overlap such as
        ``avoine`` must not select every oat product in the catalogue. When two
        products are genuinely tied (for example, identical display names), both are
        returned so the entity resolver can ask for clarification instead of mutating
        all of them.
        """
        normalized_message = cls._normalize(message)
        reference_tokens = {
            token
            for token in normalized_message.split()
            if len(token) >= 3 and token not in {
                "urun", "urunu", "urunler", "urunleri", "tane", "adet",
                "ekle", "eklenmis", "koy", "liste", "listeme", "listemde",
                "alisveris", "sepet", "sepete", "olsun", "olarak", "ayarla",
                "yap", "lutfen", "bunu", "bunlar", "bunlari", "birini",
                "iki", "uc", "dort", "fazladan", "sil", "cikar", "azalt",
            }
        }
        if not reference_tokens:
            return []

        scored: list[tuple[float, int, str]] = []
        for position, barcode in enumerate(pool):
            product = state.products.get(barcode, {})
            name = cls._normalize(str(product.get("name") or ""))
            brand = cls._normalize(str(product.get("brand") or ""))
            combined = " ".join(part for part in (name, brand) if part).strip()
            if not combined:
                continue

            candidate_tokens = {token for token in combined.split() if len(token) >= 3}
            if not candidate_tokens:
                continue

            if normalized_message == name or normalized_message == combined:
                score = 1.00
            elif normalized_message and normalized_message in name:
                score = 0.97
            elif name and name in normalized_message:
                score = 0.95
            else:
                matched_query_tokens = 0
                matched_candidate_tokens: set[str] = set()
                for query_token in reference_tokens:
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

                query_coverage = matched_query_tokens / len(reference_tokens)
                candidate_coverage = len(matched_candidate_tokens) / len(candidate_tokens)
                phrase_similarity = max(
                    SequenceMatcher(None, normalized_message, name).ratio(),
                    SequenceMatcher(None, normalized_message, combined).ratio(),
                )
                # Require the whole named reference to be represented. This prevents
                # "Flocons d'avoine" from matching Muesli merely through "avoine",
                # while still accepting small spelling errors such as "Quarker".
                if query_coverage < 0.75:
                    continue
                score = query_coverage * 0.62 + candidate_coverage * 0.18 + phrase_similarity * 0.20

            if score >= 0.72:
                # Earlier entries are more conversationally relevant. Position is a
                # tie-breaker only; it never hides a genuine exact-name ambiguity.
                scored.append((score, position, barcode))

        if not scored:
            return []
        scored.sort(key=lambda item: (-item[0], item[1]))
        best_score = scored[0][0]
        return [barcode for score, _, barcode in scored if best_score - score <= 0.025]


    @classmethod
    def _merge_compatible_plans(cls, plans: list[ActionPlan]) -> list[ActionPlan]:
        """Merge model-emitted per-barcode calls when their operation is identical.

        Qwen frequently emits one planner call per barcode. Treating those as separate
        turns would overwrite `last_detail_barcodes`; merging preserves the full selected set.
        """
        merged: list[ActionPlan] = []
        for plan in plans:
            if not plan.barcodes:
                merged.append(plan)
                continue
            compatible_index = None
            for index, existing in enumerate(merged):
                if (
                    existing.action == plan.action
                    and existing.barcodes
                    and existing.quantity == plan.quantity
                    and existing.remove_all == plan.remove_all
                    and existing.response_mode == plan.response_mode
                    and existing.max_sugars_100g == plan.max_sugars_100g
                    and existing.query == plan.query
                ):
                    compatible_index = index
                    break
            if compatible_index is None:
                merged.append(plan.model_copy(update={"product_reference": None}))
            else:
                existing = merged[compatible_index]
                combined = list(dict.fromkeys(existing.barcodes + plan.barcodes))
                merged[compatible_index] = existing.model_copy(
                    update={"barcodes": combined, "product_reference": None}
                )
        return merged

    @staticmethod
    def _deduplicate_plans(plans: list[ActionPlan]) -> list[ActionPlan]:
        seen: set[str] = set()
        result: list[ActionPlan] = []
        for plan in plans:
            key = plan.model_dump_json(exclude_none=True)
            if key not in seen:
                seen.add(key)
                result.append(plan)
        return result or [ActionPlan(action=ActionType.UNKNOWN)]

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.casefold().replace("ı", "i")
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())

    @classmethod
    def _quantity(cls, text: str) -> int:
        normalized = cls._normalize(text)
        match = re.search(r"\b(\d{1,2})\s*(?:adet|tane)\b", normalized)
        if match:
            return max(1, min(int(match.group(1)), 50))
        words = {
            "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5,
            "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
        }
        for word, number in words.items():
            if re.search(rf"\b{word}(?:ini|unu|sini)?\b", normalized) and any(
                token in normalized for token in ("sil", "cikar", "azalt", "ekle", "olsun", "tane", "adet")
            ):
                return number
        return 1

    @classmethod
    def _max_sugars(cls, text: str) -> float | None:
        normalized = cls._normalize(text)
        match = re.search(
            r"(?:en fazla|maksimum|altinda)\s+(\d+(?:[.,]\d+)?)\s*(?:gram|g)?\s*seker",
            normalized,
        )
        if match:
            return float(match.group(1).replace(",", "."))
        if any(token in normalized for token in ("az seker", "dusuk seker", "fit", "saglikli")):
            return 10.0
        return None

    @classmethod
    def _search_query(cls, message: str) -> str:
        normalized = cls._normalize(message)
        if "kahvalti" in normalized:
            return "kahvaltılık gevrek"
        cleaned = re.sub(
            r"\b(bul|ara|oner|goster|istiyorum|lutfen|urunu|urunleri|urun)\b",
            " ",
            normalized,
        )
        return re.sub(r"\s+", " ", cleaned).strip() or message.strip()

    @staticmethod
    def _has_plural_context_reference(normalized: str) -> bool:
        return any(
            token in normalized
            for token in (
                "bunlar", "bunlari", "bu urunler", "bu iki", "onlar", "onlari",
                "hepsi", "ikisi", "ucu", "daha once", "az once", "diger sectigim",
            )
        )

    @staticmethod
    def _is_remove_request(normalized: str) -> bool:
        return any(token in normalized for token in ("sil", "cikar", "azalt", "kaldir", "eksilt"))

    @classmethod
    def _is_exact_quantity_request(cls, normalized: str) -> bool:
        # A number followed by "ürün" is a selection count ("iki ürün de olsun"),
        # not an item quantity. Require an explicit quantity construction.
        number_word = r"(?:bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on|\d{1,2})"
        unit_quantity = re.search(rf"\b{number_word}\s*(?:tane|adet)\b", normalized)
        exact_marker = any(
            token in normalized
            for token in (
                "olsun", "kalsin", "olacak sekilde", "olacak bicimde",
                "olarak ayarla", "olarak yap", "miktari", "adetini", "toplam",
            )
        )
        if unit_quantity and exact_marker:
            return True
        if re.search(r"\b(?:miktari|adetini|toplam)\s*" + number_word + r"\b", normalized):
            return True
        if re.search(r"\b" + number_word + r"\s*(?:olsun|kalsin)\b", normalized):
            return True
        return False

    @staticmethod
    def _is_ensure_request(normalized: str) -> bool:
        return any(
            token in normalized
            for token in (
                "listemde olsun", "listemde istiyorum", "listeye eklemeni istedim",
                "bunlari liste", "bunlari sepet", "bu urunleri liste", "bu urunleri sepet",
            )
        )

    @classmethod
    def _is_mutation_request(cls, normalized: str) -> bool:
        return cls._is_remove_request(normalized) or any(
            token in normalized
            for token in ("ekle", "koy", "sepete at", "ilave", "artir", "olsun", "listemde istiyorum")
        )

    @staticmethod
    def _is_count_request(normalized: str) -> bool:
        return any(token in normalized for token in ("kac", "sayisi", "toplam adet")) and any(
            token in normalized for token in ("sepet", "alisveris list", "listem")
        )

    @staticmethod
    def _is_list_request(normalized: str) -> bool:
        return any(token in normalized for token in ("sepet", "alisveris list", "listem")) and any(
            token in normalized for token in ("goster", "goruntule", "listele", "ne var", "görmek", "istiyorum")
        )
