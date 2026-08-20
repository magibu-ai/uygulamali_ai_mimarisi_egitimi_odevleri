from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActionType(str, Enum):
    SEARCH_PRODUCTS = "search_products"
    GET_PRODUCT_DETAILS = "get_product_details"
    ADD_TO_SHOPPING_LIST = "add_to_shopping_list"
    ENSURE_IN_SHOPPING_LIST = "ensure_in_shopping_list"
    SET_SHOPPING_LIST_QUANTITY = "set_shopping_list_quantity"
    REMOVE_FROM_SHOPPING_LIST = "remove_from_shopping_list"
    GET_SHOPPING_LIST = "get_shopping_list"
    COUNT_SHOPPING_LIST = "count_shopping_list"
    UNKNOWN = "unknown"


class SelectionScope(str, Enum):
    NONE = "none"
    EXPLICIT = "explicit"
    LAST_SELECTED = "last_selected"
    LAST_DETAILS = "last_details"
    LAST_SEARCH = "last_search"
    ALL = "all"
    FIRST = "first"
    LAST = "last"
    NAMED = "named"


class ResponseMode(str, Enum):
    FULL = "full"
    COUNT = "count"


class ActionPlan(BaseModel):
    """Validated intermediate representation between the LLM and real tools."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: ActionType
    query: str | None = Field(default=None, max_length=160)
    max_sugars_100g: float | None = Field(default=None, ge=0, le=100)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=5, ge=1, le=10)

    barcodes: list[str] = Field(default_factory=list, max_length=10)
    product_reference: str | None = Field(default=None, max_length=160)
    selection: SelectionScope = SelectionScope.NONE
    selection_count: int | None = Field(default=None, ge=1, le=10)
    quantity: int = Field(default=1, ge=1, le=50)
    remove_all: bool = False
    response_mode: ResponseMode = ResponseMode.FULL

    @field_validator("query", "product_reference", mode="before")
    @classmethod
    def coerce_text_fields(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return str(value)
        return value

    @field_validator("barcodes", mode="before")
    @classmethod
    def normalize_barcodes(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        return [str(item).strip() for item in value]

    @field_validator("barcodes")
    @classmethod
    def validate_barcodes(cls, values: list[str]) -> list[str]:
        deduplicated: list[str] = []
        for value in values:
            if not value.isdigit() or not 8 <= len(value) <= 14:
                raise ValueError("Each barcode must contain 8 to 14 digits.")
            if value not in deduplicated:
                deduplicated.append(value)
        return deduplicated

    @field_validator("excluded_ingredients")
    @classmethod
    def normalize_exclusions(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def normalize_action_fields(self) -> "ActionPlan":
        if self.action == ActionType.COUNT_SHOPPING_LIST:
            self.response_mode = ResponseMode.COUNT

        if self.action != ActionType.SEARCH_PRODUCTS and not self.product_reference and self.query:
            # Small local models occasionally place a product name in `query` even for
            # cart/detail actions. Preserve the meaning instead of rejecting it.
            self.product_reference = self.query
            self.query = None

        if self.barcodes:
            self.selection = SelectionScope.EXPLICIT
        elif self.product_reference and self.selection in {
            SelectionScope.NONE,
            SelectionScope.EXPLICIT,
        }:
            self.selection = SelectionScope.NAMED

        if self.action == ActionType.REMOVE_FROM_SHOPPING_LIST and self.remove_all:
            self.quantity = 1
        return self


PLANNER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "plan_user_action",
        "description": (
            "Kullanıcının son mesajını doğrulanabilir bir eylem planına dönüştürür. "
            "Bileşik isteklerde her farklı ürün veya işlem için ayrı plan_user_action "
            "çağrısı üretilebilir. Bu araç ürün verisi üretmez ve veritabanını değiştirmez."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [item.value for item in ActionType],
                },
                "query": {"type": ["string", "null"]},
                "max_sugars_100g": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                "excluded_ingredients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                    "default": [],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                "barcodes": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^\\d{8,14}$"},
                    "maxItems": 10,
                    "default": [],
                },
                "product_reference": {"type": ["string", "null"]},
                "selection": {
                    "type": "string",
                    "enum": [item.value for item in SelectionScope],
                    "default": SelectionScope.NONE.value,
                },
                "selection_count": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 10,
                },
                "quantity": {"type": "integer", "minimum": 1, "maximum": 50, "default": 1},
                "remove_all": {"type": "boolean", "default": False},
                "response_mode": {
                    "type": "string",
                    "enum": [item.value for item in ResponseMode],
                    "default": ResponseMode.FULL.value,
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}
