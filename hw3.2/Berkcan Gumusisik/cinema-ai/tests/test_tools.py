"""Tool fonksiyonlarının okuma/yazma davranışı ve halüsinasyon engeli testleri.

Her test izole bir geçici veritabanı kullanır (config.DB_PATH monkeypatch'lenir).
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Her test için temiz, seed'lenmiş geçici bir SQLite veritabanı.

    get_connection() config.DB_PATH'i çağrı anında okuduğundan, tek satırlık
    monkeypatch yeterli; her tool çağrısında DB otomatik oluşturulur + seed'lenir.
    """
    from src import config, tools

    test_db = str(tmp_path / "test_cinema.db")
    monkeypatch.setattr(config, "DB_PATH", test_db)
    return tools


def test_search_returns_seeded_movies(db):
    """Katalog seed'lendi; tür filtresi gerçek kayıt döndürmeli."""
    result = db.search_movies(genre="Bilim Kurgu", min_rating=8.5)
    assert result["count"] > 0
    assert all(m["rating"] >= 8.5 for m in result["movies"])
    assert all("Bilim Kurgu" in m["genre"] for m in result["movies"])


def test_search_unknown_returns_empty(db):
    """Olmayan film boş liste döndürmeli (halüsinasyon engeli)."""
    result = db.search_movies(query="Uzaylı Kediler 7")
    assert result["count"] == 0
    assert result["movies"] == []


def test_add_to_watchlist_writes(db):
    """Geçerli movie_id izleme listesine yazılmalı ve okunabilmeli."""
    found = db.search_movies(genre="Dram")["movies"][0]
    added = db.add_to_watchlist(found["id"], user="tester")
    assert added["status"] == "added"

    wl = db.get_watchlist(user="tester")
    assert wl["count"] == 1
    assert wl["items"][0]["id"] == found["id"]


def test_add_duplicate_is_idempotent(db):
    """Aynı film iki kez eklenince tekrar yazılmamalı."""
    movie_id = db.search_movies(genre="Dram")["movies"][0]["id"]
    db.add_to_watchlist(movie_id, user="tester")
    second = db.add_to_watchlist(movie_id, user="tester")
    assert second["status"] == "already_exists"
    assert db.get_watchlist(user="tester")["count"] == 1


def test_add_nonexistent_movie_is_blocked(db):
    """Olmayan movie_id yazılmamalı; not_found dönmeli (halüsinasyon engeli)."""
    result = db.add_to_watchlist(999999, user="tester")
    assert result.get("error") == "not_found"
    assert db.get_watchlist(user="tester")["count"] == 0


def test_get_movie_details(db):
    """Detay sorgusu doğru filmi, olmayan id ise not_found döndürmeli."""
    movie = db.search_movies(genre="Dram")["movies"][0]
    detail = db.get_movie_details(movie["id"])
    assert detail["title"] == movie["title"]
    assert db.get_movie_details(999999).get("error") == "not_found"
