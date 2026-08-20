from __future__ import annotations

import pytest


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    return database_path
