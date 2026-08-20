"""Agent + tool-calling döngüsünün MOCK backend ile uçtan uca testi (API'siz).

Bu testler gerçek modeli çağırmaz; yerel kural tabanlı MockClient üzerinden
tüm akışı (search -> add -> get_watchlist -> not_found) doğrular.
"""

from __future__ import annotations

import pytest

from src.config import LLMConfig


@pytest.fixture()
def mock_cfg(tmp_path, monkeypatch):
    """Mock backend + izole geçici veritabanı."""
    from src import config

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "agent_test.db"))
    return LLMConfig(api_key="", base_url="", model="mock", backend="mock")


def test_config_falls_back_to_mock_without_key():
    """Anahtar yokken 'auto' backend mock'a düşmeli ve hazır olmalı."""
    cfg = LLMConfig(api_key="", base_url="x", model="y", backend="auto")
    assert cfg.use_mock is True
    assert cfg.is_ready is True


def test_recommend_flow(mock_cfg):
    from src.agent import respond

    reply, trace = respond([], "Bana 8.7 üstü bir bilim kurgu filmi öner", cfg=mock_cfg)
    assert trace[0]["name"] == "search_movies"
    assert trace[0]["result"]["count"] > 0
    assert "öneririm" in reply.lower() or "başlangıç" in reply.lower()


def test_add_flow_writes_to_db(mock_cfg):
    from src.agent import respond
    from src import tools

    reply, trace = respond([], "Başlangıç filmini izleme listeme ekle", cfg=mock_cfg)
    called = [step["name"] for step in trace]
    assert "search_movies" in called and "add_to_watchlist" in called
    # Gerçekten yazıldı mı?
    assert tools.get_watchlist(user="guest")["count"] == 1
    assert "eklendi" in reply.lower()


def test_not_found_is_honest(mock_cfg):
    """Olmayan film için uydurma yapmadan 'bulunamadı' demeli."""
    from src.agent import respond

    reply, trace = respond([], "Uzaylı Kediler 7 filmini bul", cfg=mock_cfg)
    # Anti-halüsinasyonun özü: arama gerçekten boş döndü...
    assert trace[-1]["result"]["count"] == 0
    # ...ve yanıt bir film uydurmadı; "bulunamadı" anlamı taşıyan bir ifade verdi.
    assert any(k in reply.lower() for k in ["çıkmadı", "bulamad", "bulun", "dener misin"])
