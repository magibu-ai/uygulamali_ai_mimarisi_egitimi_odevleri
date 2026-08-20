from __future__ import annotations

import json

from assistant.action_schema import ActionPlan, ActionType, ResponseMode, SelectionScope
from assistant.agent import NutriChoiceAgent
from assistant.intent_planner import IntentPlanner
from assistant.model_client import ModelClient


class PlannedModel(ModelClient):
    """Returns a plan_user_action call selected from the current user message."""

    def generate(self, messages, tools):
        payload = json.loads(messages[-1]["content"])
        message = payload["user_message"].casefold()

        if "100 gram" in message:
            args = {
                "action": "search_products",
                "query": "kahvaltılık gevrek",
                "max_sugars_100g": 10,
                "limit": 5,
            }
        elif "detay" in message:
            args = {
                "action": "get_product_details",
                "barcodes": ["8681655007075", "8681185086991"],
            }
        elif "granola" in message and "ekle" in message:
            args = {
                "action": "add_to_shopping_list",
                "product_reference": "granola",
                "selection": "named",
                "quantity": 2,
            }
        elif "kaç" in message:
            args = {"action": "count_shopping_list", "response_mode": "count"}
        elif "görüntüle" in message or "göster" in message:
            args = {"action": "get_shopping_list"}
        else:
            args = {"action": "unknown"}

        blocks = []
        for key, value in args.items():
            rendered = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            blocks.append(f"<parameter={key}>\n{rendered}\n</parameter>")
        return (
            "<tool_call>\n<function=plan_user_action>\n"
            + "\n".join(blocks)
            + "\n</function>\n</tool_call>"
        )


class StatefulFakeRouter:
    def __init__(self):
        self.calls = []
        self.items: dict[str, dict] = {}
        self.products = {
            "8681655007075": {
                "barcode": "8681655007075",
                "name": "Corn flakes",
                "brand": None,
                "nutrition_grade": "c",
                "nutriments": {"sugars_100g": 0.0, "energy_kcal_100g": 376.0},
                "allergens": [],
            },
            "8681185086991": {
                "barcode": "8681185086991",
                "name": "Fındıklı ve Kakaolu Granola",
                "brand": "Fellas",
                "nutrition_grade": "c",
                "nutriments": {"sugars_100g": 10.0, "energy_kcal_100g": 467.0},
                "allergens": ["en:gluten", "en:nuts"],
            },
        }

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_products":
            return {
                "success": True,
                "products": list(self.products.values()),
                "count": 2,
            }
        if name == "get_product_details":
            return {"success": True, "product": self.products[arguments["barcode"]]}
        if name == "add_to_shopping_list":
            barcode = arguments["barcode"]
            quantity = arguments["quantity"]
            current = self.items.get(barcode, {}).get("quantity", 0) + quantity
            product = self.products[barcode]
            self.items[barcode] = {
                "barcode": barcode,
                "product_name": product["name"],
                "brand": product.get("brand"),
                "quantity": current,
            }
            return {
                "success": True,
                "product": product,
                "added_quantity": quantity,
                "quantity": current,
            }
        if name == "get_shopping_list":
            return {
                "success": True,
                "count": len(self.items),
                "items": list(self.items.values()),
            }
        raise AssertionError(name)


def test_stateful_flow_resolves_named_product_and_formats_list_count():
    router = StatefulFakeRouter()
    agent = NutriChoiceAgent(model=PlannedModel(), router=router)

    search_answer = agent.chat(
        "100 gramında en fazla 10 gram şeker olan kahvaltılık ürünleri bul.",
        session_id="session-a",
    )
    assert "Corn flakes" in search_answer
    assert "Fındıklı ve Kakaolu Granola" in search_answer

    details_answer = agent.chat(
        "8681655007075 ve 8681185086991 barkodlu ürünlerin detayını getir",
        session_id="session-a",
    )
    assert "Corn flakes" in details_answer
    assert "Fındıklı ve Kakaolu Granola" in details_answer

    add_answer = agent.chat("Granoladan 2 tane ekle", session_id="session-a")
    assert "Eklenen miktar: 2" in add_answer
    assert router.calls[-1] == (
        "add_to_shopping_list",
        {"barcode": "8681185086991", "quantity": 2},
    )

    list_answer = agent.chat("Alışveriş listemi görüntüle", session_id="session-a")
    assert "2 adet" in list_answer
    assert "Toplam: 1 farklı ürün, 2 adet ürün" in list_answer

    count_answer = agent.chat("Alışveriş listemde kaç ürün var", session_id="session-a")
    assert "1 farklı ürün" in count_answer
    assert "2 adet ürün" in count_answer


def test_state_is_structured_and_does_not_depend_on_rendered_history():
    router = StatefulFakeRouter()
    agent = NutriChoiceAgent(model=PlannedModel(), router=router)
    agent.chat("100 gramında en fazla 10 gram şeker olan kahvaltılık ürünleri bul.", session_id="s")
    agent.chat(
        "8681655007075 ve 8681185086991 barkodlu ürünlerin detayını getir",
        history=[{"role": "assistant", "content": "Bu metinde hiç barkod yok."}],
        session_id="s",
    )
    answer = agent.chat(
        "Granoladan 2 tane ekle",
        history=[{"role": "assistant", "content": "Yanıt biçimi tamamen değişti."}],
        session_id="s",
    )
    assert "Fındıklı ve Kakaolu Granola" in answer


def test_sessions_do_not_share_conversation_state():
    router = StatefulFakeRouter()
    agent = NutriChoiceAgent(model=PlannedModel(), router=router)
    agent.chat("100 gramında en fazla 10 gram şeker olan kahvaltılık ürünleri bul.", session_id="a")
    answer = agent.chat("Granoladan 2 tane ekle", session_id="b")
    assert "Hangi ürünü kastettiğini" in answer
