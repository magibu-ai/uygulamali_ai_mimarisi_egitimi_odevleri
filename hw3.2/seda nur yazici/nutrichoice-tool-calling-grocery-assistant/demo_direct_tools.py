"""Run a minimal direct tool trace without loading the language model."""

from services.open_food_facts import OpenFoodFactsClient
from tools.tool_router import ToolRouter


def main() -> None:
    router = ToolRouter(OpenFoodFactsClient.from_environment(), "demo-user")
    router.execute(
        "get_product_details",
        {"barcode": "3159470000120"},
    )
    router.execute(
        "ensure_in_shopping_list",
        {"barcode": "3159470000120", "minimum_quantity": 1},
    )
    router.execute(
        "set_shopping_list_quantity",
        {"barcode": "3159470000120", "quantity": 2},
    )
    router.execute("get_shopping_list", {})


if __name__ == "__main__":
    main()
