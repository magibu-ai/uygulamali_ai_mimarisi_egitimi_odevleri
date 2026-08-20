from __future__ import annotations

import json
from typing import Any

from database.connection import get_connection


def upsert_shopping_list_item(
    *,
    user_id: str,
    barcode: str,
    product_name: str,
    brand: str | None,
    quantity: int,
    image_url: str | None,
    nutrition_grade: str | None,
) -> int:
    """Increment an item's quantity, inserting it when needed."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO shopping_list_items (
                user_id, barcode, product_name, brand, quantity, image_url, nutrition_grade
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, barcode) DO UPDATE SET
                product_name = excluded.product_name,
                brand = excluded.brand,
                quantity = shopping_list_items.quantity + excluded.quantity,
                image_url = excluded.image_url,
                nutrition_grade = excluded.nutrition_grade,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                barcode,
                product_name,
                brand,
                quantity,
                image_url,
                nutrition_grade,
            ),
        )
        row = connection.execute(
            "SELECT quantity FROM shopping_list_items WHERE user_id = ? AND barcode = ?",
            (user_id, barcode),
        ).fetchone()
        return int(row["quantity"])


def ensure_shopping_list_item(
    *,
    user_id: str,
    barcode: str,
    product_name: str,
    brand: str | None,
    minimum_quantity: int,
    image_url: str | None,
    nutrition_grade: str | None,
) -> tuple[int, bool]:
    """Ensure an item exists with at least the requested quantity, without incrementing it blindly."""
    with get_connection() as connection:
        before = connection.execute(
            "SELECT quantity FROM shopping_list_items WHERE user_id = ? AND barcode = ?",
            (user_id, barcode),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO shopping_list_items (
                user_id, barcode, product_name, brand, quantity, image_url, nutrition_grade
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, barcode) DO UPDATE SET
                product_name = excluded.product_name,
                brand = excluded.brand,
                quantity = MAX(shopping_list_items.quantity, excluded.quantity),
                image_url = excluded.image_url,
                nutrition_grade = excluded.nutrition_grade,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                barcode,
                product_name,
                brand,
                minimum_quantity,
                image_url,
                nutrition_grade,
            ),
        )
        row = connection.execute(
            "SELECT quantity FROM shopping_list_items WHERE user_id = ? AND barcode = ?",
            (user_id, barcode),
        ).fetchone()
        total = int(row["quantity"])
        changed = before is None or total != int(before["quantity"])
        return total, changed


def set_shopping_list_item_quantity(
    *,
    user_id: str,
    barcode: str,
    product_name: str,
    brand: str | None,
    quantity: int,
    image_url: str | None,
    nutrition_grade: str | None,
) -> tuple[int | None, int]:
    """Set the exact final quantity and return (previous, current)."""
    with get_connection() as connection:
        before = connection.execute(
            "SELECT quantity FROM shopping_list_items WHERE user_id = ? AND barcode = ?",
            (user_id, barcode),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO shopping_list_items (
                user_id, barcode, product_name, brand, quantity, image_url, nutrition_grade
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, barcode) DO UPDATE SET
                product_name = excluded.product_name,
                brand = excluded.brand,
                quantity = excluded.quantity,
                image_url = excluded.image_url,
                nutrition_grade = excluded.nutrition_grade,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                barcode,
                product_name,
                brand,
                quantity,
                image_url,
                nutrition_grade,
            ),
        )
        previous = int(before["quantity"]) if before else None
        return previous, quantity


def remove_shopping_list_item(
    *,
    user_id: str,
    barcode: str,
    quantity: int = 1,
    remove_all: bool = False,
) -> dict[str, Any] | None:
    """Decrease quantity or remove the row. Returns None when the item is absent."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT barcode, product_name, brand, quantity, image_url, nutrition_grade
            FROM shopping_list_items
            WHERE user_id = ? AND barcode = ?
            """,
            (user_id, barcode),
        ).fetchone()
        if row is None:
            return None

        current = int(row["quantity"])
        removed_quantity = current if remove_all else min(quantity, current)
        remaining = current - removed_quantity
        if remaining <= 0:
            connection.execute(
                "DELETE FROM shopping_list_items WHERE user_id = ? AND barcode = ?",
                (user_id, barcode),
            )
            remaining = 0
        else:
            connection.execute(
                """
                UPDATE shopping_list_items
                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND barcode = ?
                """,
                (remaining, user_id, barcode),
            )

        item = dict(row)
        item.update(
            {
                "removed_quantity": removed_quantity,
                "remaining_quantity": remaining,
                "removed_all": remaining == 0,
            }
        )
        return item


def list_shopping_items(user_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT barcode, product_name, brand, quantity, image_url,
                   nutrition_grade, created_at, updated_at
            FROM shopping_list_items
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def log_tool_call(
    *,
    user_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tool_call_logs (
                user_id, tool_name, arguments_json, result_json, success
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                tool_name,
                json.dumps(arguments, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                int(bool(result.get("success"))),
            ),
        )
