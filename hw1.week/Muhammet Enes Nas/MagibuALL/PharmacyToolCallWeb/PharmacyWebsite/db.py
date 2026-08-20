"""
Eczane Sipariş Asistanı — Veritabanı Katmanı
SQLite bağlantı yönetimi, şema oluşturma ve CRUD fonksiyonları.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pharmacy.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS drugs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT    UNIQUE NOT NULL,
                display_name        TEXT,
                stock               INTEGER NOT NULL DEFAULT 0,
                price               REAL,
                prospektus_summary  TEXT,
                source              TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_id     INTEGER REFERENCES drugs(id),
                drug_name   TEXT,
                quantity    INTEGER NOT NULL,
                status      TEXT    DEFAULT 'Hazırlanıyor',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def find_drug(name: str) -> dict | None:
    normalized = " ".join(name.strip().lower().split())
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM drugs WHERE LOWER(REPLACE(name, ' ', '')) = LOWER(REPLACE(?, ' ', ''))",
            (normalized,),
        ).fetchone()
        if row:
            return dict(row)
    return None


def insert_drug(
    name: str,
    display_name: str,
    stock: int = 0,
    price: float | None = None,
    prospektus_summary: str | None = None,
    source: str = "seed",
) -> int:
    normalized = " ".join(name.strip().lower().split())
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO drugs (name, display_name, stock, price, prospektus_summary, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (normalized, display_name, stock, price, prospektus_summary, source),
        )
        return cur.lastrowid


def update_drug_prospektus(drug_id: int, summary: str, source: str = "fetched"):
    with get_db() as conn:
        conn.execute(
            "UPDATE drugs SET prospektus_summary = ?, source = ? WHERE id = ?",
            (summary, source, drug_id),
        )


def search_drugs_by_keyword(keyword: str) -> list[dict]:
    term = keyword.strip().lower()
    stop_words = {"ilaci", "ilaç", "ilacı", "onerisi", "önerisi", "icin", "için", "ne", "var", "mi", "mı", "tavsiye", "iyi", "gelen", "gelir"}
    words = [w for w in term.split() if w not in stop_words and len(w) > 2]

    with get_db() as conn:
        results = []
        seen_ids = set()

        full_pattern = f"%{term}%"
        rows = conn.execute(
            """SELECT id, name, display_name, stock, price, prospektus_summary, source
               FROM drugs
               WHERE LOWER(prospektus_summary) LIKE ? OR LOWER(display_name) LIKE ? OR LOWER(name) LIKE ?""",
            (full_pattern, full_pattern, full_pattern),
        ).fetchall()
        for r in rows:
            d = dict(r)
            if d["id"] not in seen_ids:
                seen_ids.add(d["id"])
                results.append(d)

        if results:
            return results

        for word in words:
            pattern = f"%{word}%"
            rows = conn.execute(
                """SELECT id, name, display_name, stock, price, prospektus_summary, source
                   FROM drugs
                   WHERE LOWER(prospektus_summary) LIKE ? OR LOWER(display_name) LIKE ? OR LOWER(name) LIKE ?""",
                (pattern, pattern, pattern),
            ).fetchall()
            for r in rows:
                d = dict(r)
                if d["id"] not in seen_ids:
                    seen_ids.add(d["id"])
                    results.append(d)
        return results


def list_drugs() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT display_name, stock, price FROM drugs ORDER BY display_name"
        ).fetchall()
        return [dict(r) for r in rows]


def create_order_record(drug_id: int, drug_name: str, quantity: int) -> dict | None:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE drugs SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (quantity, drug_id, quantity),
        )
        if cur.rowcount == 0:
            return None

        cur = conn.execute(
            """INSERT INTO orders (drug_id, drug_name, quantity, status)
               VALUES (?, ?, ?, 'Hazırlanıyor')""",
            (drug_id, drug_name, quantity),
        )
        order_id = cur.lastrowid
        return {
            "order_id": order_id,
            "drug_name": drug_name,
            "quantity": quantity,
            "status": "Hazırlanıyor",
        }


def find_order(order_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id AS order_id, drug_name, quantity, status, created_at FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if row:
            return dict(row)
    return None
