import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(__file__).with_name("bookstore.db")
SEED_BOOKS = [
    ("Kürk Mantolu Madonna", "Sabahattin Ali", 120.0, 8),
    ("Tutunamayanlar", "Oğuz Atay", 245.0, 5),
    ("Saatleri Ayarlama Enstitüsü", "Ahmet Hamdi Tanpınar", 180.0, 4),
    ("İnce Memed", "Yaşar Kemal", 210.0, 6),
]


def connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                author TEXT NOT NULL,
                price REAL NOT NULL CHECK (price >= 0),
                stock INTEGER NOT NULL CHECK (stock >= 0)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                book_id INTEGER NOT NULL REFERENCES books(id),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                total REAL NOT NULL CHECK (total >= 0),
                status TEXT NOT NULL DEFAULT 'hazırlanıyor',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        db.executemany(
            "INSERT OR IGNORE INTO books(title, author, price, stock) VALUES (?, ?, ?, ?)",
            SEED_BOOKS,
        )


def search_books(query=""):
    with connect() as db:
        rows = db.execute(
            """SELECT id, title, author, price, stock FROM books
               WHERE title LIKE ? OR author LIKE ? ORDER BY title""",
            (f"%{query.strip()}%", f"%{query.strip()}%"),
        ).fetchall()
    return {"books": [dict(row) for row in rows]}


def create_order(book_id, quantity):
    if not isinstance(book_id, int) or not isinstance(quantity, int) or quantity < 1:
        return {"error": "book_id ve quantity pozitif tam sayı olmalıdır."}

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        book = db.execute(
            "SELECT id, title, price, stock FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        if not book:
            return {"error": "Kitap bulunamadı."}
        if book["stock"] < quantity:
            return {"error": "Yetersiz stok.", "available_stock": book["stock"]}

        order_id = uuid.uuid4().hex[:8].upper()
        total = round(book["price"] * quantity, 2)
        db.execute("UPDATE books SET stock = stock - ? WHERE id = ?", (quantity, book_id))
        db.execute(
            "INSERT INTO orders(id, book_id, quantity, total) VALUES (?, ?, ?, ?)",
            (order_id, book_id, quantity, total),
        )
    return {
        "order_id": order_id,
        "title": book["title"],
        "quantity": quantity,
        "total": total,
        "status": "hazırlanıyor",
    }


def get_order_status(order_id):
    with connect() as db:
        row = db.execute(
            """SELECT orders.id AS order_id, books.title, orders.quantity,
                      orders.total, orders.status, orders.created_at
               FROM orders JOIN books ON books.id = orders.book_id
               WHERE orders.id = ?""",
            (str(order_id).strip().upper(),),
        ).fetchone()
    return dict(row) if row else {"error": "Sipariş bulunamadı."}


init_db()

