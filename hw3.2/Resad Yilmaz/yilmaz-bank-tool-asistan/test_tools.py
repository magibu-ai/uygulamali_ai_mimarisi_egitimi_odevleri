import json

import tools


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def show(result):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main():
    section("1. list_accounts")
    show(tools.execute_tool("list_accounts", {"user_id": 1}))

    section("2. get_balance")
    show(tools.execute_tool("get_balance", {"account_id": 1}))

    section("3. get_balance — olmayan hesap")
    show(tools.execute_tool("get_balance", {"account_id": 99999}))

    section("4. get_transaction_history")
    show(tools.execute_tool("get_transaction_history", {"account_id": 1, "limit": 3}))

    section("5. transfer_money — geçerli")
    show(tools.execute_tool(
        "transfer_money",
        {"from_account_id": 1, "to_account_id": 2, "amount": 50, "description": "tools.py testi"},
    ))

    section("6. transfer_money — negatif tutar (Pydantic reddetmeli)")
    show(tools.execute_tool(
        "transfer_money",
        {"from_account_id": 1, "to_account_id": 2, "amount": -10},
    ))

    section("7. create_card")
    show(tools.execute_tool("create_card", {"account_id": 3, "card_type": "virtual"}))

    section("8. block_card")
    show(tools.execute_tool("block_card", {"card_id": 1}))

    section("9. Bilinmeyen tool")
    show(tools.execute_tool("sil_hesabi", {}))

    print("\nTÜM TESTLER TAMAMLANDI")


if __name__ == "__main__":
    main()