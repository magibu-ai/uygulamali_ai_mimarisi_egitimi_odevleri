"""SQLite katmanı: kitap stoğu ve sipariş kayıtları."""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "kitapci.db")

SEED_BOOKS = [
    ("Suç ve Ceza", "Fyodor Dostoyevski", 180.0, 12),
    ("1984", "George Orwell", 120.0, 8),
    ("Küçük Prens", "Antoine de Saint-Exupéry", 90.0, 20),
    ("Simyacı", "Paulo Coelho", 110.0, 15),
    ("Sapiens", "Yuval Noah Harari", 220.0, 5),
    ("Fahrenheit 451", "Ray Bradbury", 130.0, 0),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset: bool = False) -> None:
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books(id)
        )
        """
    )
    cur.execute("SELECT COUNT(*) FROM books")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO books (title, author, price, stock) VALUES (?, ?, ?, ?)",
            SEED_BOOKS,
        )
    conn.commit()
    conn.close()


def list_books(query: str | None = None) -> list[dict]:
    conn = get_connection()
    if query:
        rows = conn.execute(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ?",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM books").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_book(book_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_order(book_id: int, quantity: int, customer_name: str) -> dict:
    conn = get_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        conn.close()
        return {"error": f"book_id {book_id} bulunamadı."}
    if quantity < 1:
        conn.close()
        return {"error": "quantity en az 1 olmalı."}
    if book["stock"] < quantity:
        conn.close()
        return {"error": f"Yetersiz stok. '{book['title']}' için mevcut stok: {book['stock']}."}

    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO orders (book_id, quantity, customer_name, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (book_id, quantity, customer_name, "confirmed", now),
    )
    conn.execute(
        "UPDATE books SET stock = stock - ? WHERE id = ?", (quantity, book_id)
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return {
        "order_id": order_id,
        "book_title": book["title"],
        "quantity": quantity,
        "customer_name": customer_name,
        "total_price": round(book["price"] * quantity, 2),
        "status": "confirmed",
    }


def check_order_status(order_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT orders.id AS order_id, orders.quantity, orders.customer_name,
               orders.status, orders.created_at, books.title AS book_title
        FROM orders JOIN books ON orders.book_id = books.id
        WHERE orders.id = ?
        """,
        (order_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"error": f"order_id {order_id} bulunamadı."}
    return dict(row)


init_db()
