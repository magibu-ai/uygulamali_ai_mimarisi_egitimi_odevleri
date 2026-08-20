from __future__ import annotations

from database.connection import get_connection, get_database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS shopping_list_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    barcode TEXT NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    image_url TEXT,
    nutrition_grade TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, barcode)
);

CREATE TABLE IF NOT EXISTS tool_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    success INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA)


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {get_database_path()}")
