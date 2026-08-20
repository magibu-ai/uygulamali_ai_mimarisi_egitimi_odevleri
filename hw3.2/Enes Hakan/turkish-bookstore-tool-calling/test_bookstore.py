import tempfile
from pathlib import Path

import bookstore


def test_order_flow():
    original = bookstore.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as directory:
            bookstore.DB_PATH = Path(directory) / "test.db"
            bookstore.init_db()
            book = bookstore.search_books("Tutunamayanlar")["books"][0]
            order = bookstore.create_order(book["id"], 2)
            assert order["order_id"]
            assert bookstore.get_order_status(order["order_id"])["quantity"] == 2
            assert bookstore.search_books("Tutunamayanlar")["books"][0]["stock"] == book["stock"] - 2
            assert "error" in bookstore.create_order(book["id"], 999)

            from app import call_tool

            verified = set()
            assert "error" in call_tool("create_order", {"book_id": book["id"], "quantity": 1}, verified)
            call_tool("search_books", {"query": "Tutunamayanlar"}, verified)
            assert "order_id" in call_tool("create_order", {"book_id": book["id"], "quantity": 1}, verified)
    finally:
        bookstore.DB_PATH = original


if __name__ == "__main__":
    test_order_flow()
    print("OK: arama, sipariş, stok düşümü ve durum sorgusu")
