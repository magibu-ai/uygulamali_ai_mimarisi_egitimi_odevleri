"""
database.py
-----------
SQLite baglanti yonetimi, sema olusturma ve baslangic (seed) verisi.
Tum tablo erisimleri bu modul uzerinden yapilir; tool fonksiyonlari dogrudan
SQL yazmaz, boylece veri katmani tek yerde toplanir (temiz + modüler).
"""

import os
import sqlite3
from contextlib import contextmanager

# Veritabani dosyasinin yolu (proje kokune gore)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "restaurant.db")


@contextmanager
def get_connection():
    """Row'lari dict gibi okumak icin row_factory ayarli baglanti dondurur."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(force: bool = False) -> None:
    """Semayi olusturur ve tablolar bossa ornek menu ile doldurur."""
    with get_connection() as conn:
        cur = conn.cursor()
        if force:
            cur.executescript(
                "DROP TABLE IF EXISTS order_items;"
                "DROP TABLE IF EXISTS orders;"
                "DROP TABLE IF EXISTS menu;"
            )

        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS menu (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                category    TEXT NOT NULL,          -- ana | tatli | icecek
                price       REAL NOT NULL,
                stock       INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer    TEXT NOT NULL,
                table_no    INTEGER,
                status      TEXT NOT NULL DEFAULT 'hazirlaniyor',  -- hazirlaniyor | yolda | teslim
                total       REAL NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL,
                menu_id     INTEGER NOT NULL,
                quantity    INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (menu_id)  REFERENCES menu(id)
            );
            """
        )

        # Seed: menu bossa doldur
        count = cur.execute("SELECT COUNT(*) FROM menu").fetchone()[0]
        if count == 0:
            seed = [
                ("Mercimek Corbasi", "ana", 65.0, 40),
                ("Izgara Kofte",     "ana", 180.0, 25),
                ("Tavuk Sote",       "ana", 165.0, 30),
                ("Adana Kebap",      "ana", 220.0, 20),
                ("Kunefe",           "tatli", 120.0, 15),
                ("Sutlac",           "tatli", 90.0, 18),
                ("Baklava",          "tatli", 140.0, 12),
                ("Turk Kahvesi",     "icecek", 55.0, 100),
                ("Ayran",            "icecek", 30.0, 100),
                ("Limonata",         "icecek", 45.0, 60),
            ]
            cur.executemany(
                "INSERT INTO menu (name, category, price, stock) VALUES (?, ?, ?, ?)",
                seed,
            )


if __name__ == "__main__":
    init_db(force=True)
    print(f"Veritabani hazir: {os.path.abspath(DB_PATH)}")
