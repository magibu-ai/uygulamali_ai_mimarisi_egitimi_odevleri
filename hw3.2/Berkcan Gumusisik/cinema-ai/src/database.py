"""SQLite veritabanı katmanı: bağlantı, şema oluşturma ve seed.

İki tablo tutulur:
  - movies    : film kataloğu (salt okunur referans veri)
  - watchlist : kullanıcıların izleme listesi (okuma + yazma)

Veritabanı ilk erişimde otomatik oluşturulur ve data/seed_movies.json'dan
doldurulur. Böylece repo klonlandığında ekstra bir kurulum adımı gerekmez.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from . import config


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Row factory'si dict-benzeri olan bir SQLite bağlantısı döndürür.

    Bağlantı her çağrıda veritabanının kurulu (şema + seed) olmasını garanti eder.
    """
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # satırlara sütun adıyla erişim
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_initialized(conn)
    return conn


def _ensure_initialized(conn: sqlite3.Connection) -> None:
    """Şema yoksa oluşturur ve movies tablosu boşsa seed eder (idempotent)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS movies (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT    NOT NULL,
            year     INTEGER,
            genre    TEXT,
            rating   REAL,
            director TEXT,
            overview TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL REFERENCES movies(id),
            user     TEXT    NOT NULL DEFAULT 'guest',
            status   TEXT    NOT NULL DEFAULT 'izlenecek',
            added_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(movie_id, user)
        );
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    if count == 0:
        _seed_movies(conn)
    conn.commit()


def _seed_movies(conn: sqlite3.Connection) -> None:
    """Seed JSON dosyasından film kataloğunu yükler."""
    seed_file = Path(config.SEED_PATH)
    if not seed_file.exists():
        return
    movies = json.loads(seed_file.read_text(encoding="utf-8"))
    conn.executemany(
        """
        INSERT INTO movies (title, year, genre, rating, director, overview)
        VALUES (:title, :year, :genre, :rating, :director, :overview)
        """,
        movies,
    )


def reset_database(db_path: Optional[str] = None) -> None:
    """Veritabanını sıfırlar (testler ve temiz demo için)."""
    path = Path(db_path or config.DB_PATH)
    if path.exists():
        path.unlink()
    # Yeniden oluştur + seed et.
    get_connection(str(path)).close()
