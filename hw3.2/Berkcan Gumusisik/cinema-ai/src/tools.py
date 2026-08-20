"""Tool fonksiyonları: modelin dış dünyaya (SQLite veritabanı) eriştiği katman.

Her fonksiyon JSON'a çevrilebilir bir dict/list döndürür. Modelin ürettiği
argümanlar buraya gelir; tüm SQL sorguları parametrelidir (SQL injection'a kapalı).

ÖNEMLİ — Halüsinasyon engeli: Bu fonksiyonlar yalnızca veritabanında gerçekten
var olan veriyi döndürür. Bulunamayan bir kayıt için boş liste ya da
{"error": "not_found"} döner; asla uydurma veri üretilmez.
"""

from __future__ import annotations

from typing import Any, Optional

from .database import get_connection


def search_movies(
    query: Optional[str] = None,
    genre: Optional[str] = None,
    min_rating: Optional[float] = None,
    year: Optional[int] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Film kataloğunda arama yapar (SALT OKUMA).

    Args:
        query: Başlık/yönetmen/özet içinde geçen serbest metin.
        genre: Tür filtresi (ör. "Bilim Kurgu", "Dram").
        min_rating: Minimum IMDb-benzeri puan (0-10).
        year: Yapım yılı filtresi.
        limit: Döndürülecek en fazla kayıt sayısı.

    Returns:
        {"count": int, "movies": [ {id, title, year, genre, rating, director, overview}, ... ]}
        Eşleşme yoksa boş liste döner.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if query:
        clauses.append("(title LIKE ? OR director LIKE ? OR overview LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like])
    if genre:
        clauses.append("genre LIKE ?")
        params.append(f"%{genre}%")
    if min_rating is not None:
        clauses.append("rating >= ?")
        params.append(min_rating)
    if year is not None:
        clauses.append("year = ?")
        params.append(year)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, title, year, genre, rating, director, overview
        FROM movies
        {where}
        ORDER BY rating DESC
        LIMIT ?
    """
    params.append(max(1, min(limit, 50)))

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    movies = [dict(row) for row in rows]
    return {"count": len(movies), "movies": movies}


def get_movie_details(movie_id: int) -> dict[str, Any]:
    """Tek bir filmin tüm detaylarını döndürür (SALT OKUMA).

    Returns:
        Film dict'i ya da bulunamazsa {"error": "not_found", "movie_id": ...}.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, title, year, genre, rating, director, overview FROM movies WHERE id = ?",
            (movie_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {"error": "not_found", "movie_id": movie_id}
    return dict(row)


def add_to_watchlist(movie_id: int, user: str = "guest") -> dict[str, Any]:
    """Bir filmi kullanıcının izleme listesine ekler (YAZMA).

    Önce filmin veritabanında var olduğunu doğrular; yoksa hata döner
    (halüsinasyon engeli). Zaten ekliyse tekrar eklemez.

    Returns:
        Başarılı: {"status": "added"|"already_exists", "movie": {...}, "user": ...}
        Film yok: {"error": "not_found", "movie_id": ...}
    """
    conn = get_connection()
    try:
        movie = conn.execute(
            "SELECT id, title, year FROM movies WHERE id = ?", (movie_id,)
        ).fetchone()
        if movie is None:
            return {"error": "not_found", "movie_id": movie_id}

        existing = conn.execute(
            "SELECT id FROM watchlist WHERE movie_id = ? AND user = ?",
            (movie_id, user),
        ).fetchone()
        if existing is not None:
            return {
                "status": "already_exists",
                "movie": dict(movie),
                "user": user,
            }

        conn.execute(
            "INSERT INTO watchlist (movie_id, user) VALUES (?, ?)",
            (movie_id, user),
        )
        conn.commit()
        return {"status": "added", "movie": dict(movie), "user": user}
    finally:
        conn.close()


def get_watchlist(user: str = "guest") -> dict[str, Any]:
    """Kullanıcının izleme listesini döndürür (SALT OKUMA).

    Returns:
        {"user": ..., "count": int, "items": [ {watchlist_id, status, added_at,
         id, title, year, genre, rating}, ... ]}
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT w.id AS watchlist_id, w.status, w.added_at,
                   m.id, m.title, m.year, m.genre, m.rating
            FROM watchlist w
            JOIN movies m ON m.id = w.movie_id
            WHERE w.user = ?
            ORDER BY w.added_at DESC
            """,
            (user,),
        ).fetchall()
    finally:
        conn.close()

    items = [dict(row) for row in rows]
    return {"user": user, "count": len(items), "items": items}
