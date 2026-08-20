from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchProductsArguments(StrictToolArguments):
    query: str = Field(min_length=2, max_length=120)
    max_sugars_100g: float | None = Field(default=None, ge=0, le=100)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("excluded_ingredients")
    @classmethod
    def validate_exclusions(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 60 for value in cleaned):
            raise ValueError("Excluded ingredient names must be at most 60 characters.")
        return cleaned


def _coerce_barcode_to_string(value: object) -> object:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value


class BarcodeArguments(StrictToolArguments):
    barcode: str = Field(pattern=r"^\d{8,14}$")

    @field_validator("barcode", mode="before")
    @classmethod
    def normalize_barcode(cls, value: object) -> object:
        return _coerce_barcode_to_string(value)


class GetProductDetailsArguments(BarcodeArguments):
    pass


class AddToShoppingListArguments(BarcodeArguments):
    quantity: int = Field(default=1, ge=1, le=50)


class EnsureInShoppingListArguments(BarcodeArguments):
    minimum_quantity: int = Field(default=1, ge=1, le=50)


class SetShoppingListQuantityArguments(BarcodeArguments):
    quantity: int = Field(ge=1, le=50)


class RemoveFromShoppingListArguments(BarcodeArguments):
    quantity: int = Field(default=1, ge=1, le=50)
    remove_all: bool = False


class GetShoppingListArguments(StrictToolArguments):
    pass
