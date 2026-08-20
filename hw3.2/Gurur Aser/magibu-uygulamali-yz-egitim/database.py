"""SQLite schema, deterministic seeding, and ephemeral session copies."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .data_loader import DATASET_PATH, HIVE_METADATA, iter_enriched_rows
except ImportError:  # pragma: no cover - direct execution from les6/.
    from data_loader import DATASET_PATH, HIVE_METADATA, iter_enriched_rows

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS hives (
    hive_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hive_id TEXT NOT NULL REFERENCES hives(hive_id) ON DELETE CASCADE,
    source_row INTEGER NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    temperature_c REAL NOT NULL,
    humidity_percent REAL NOT NULL,
    ph REAL NOT NULL,
    weight_kg REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_hive_time
    ON sensor_readings(hive_id, recorded_at);
CREATE TABLE IF NOT EXISTS inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hive_id TEXT NOT NULL REFERENCES hives(hive_id) ON DELETE CASCADE,
    queen_seen INTEGER NOT NULL CHECK (queen_seen IN (0, 1)),
    varroa_count INTEGER NOT NULL CHECK (varroa_count BETWEEN 0 AND 1000),
    notes TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= 500),
    inspected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inspections_hive_time
    ON inspections(hive_id, inspected_at);
"""


class HiveDatabase:
    """Small row-dict SQLite wrapper used by tools and tests."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._closed = False

    def initialize(self, *, data_path: str | Path = DATASET_PATH) -> "HiveDatabase":
        self.connection.executescript(SCHEMA)
        existing = self.connection.execute("SELECT COUNT(*) FROM sensor_readings").fetchone()[0]
        if existing == 0:
            self.connection.executemany(
                "INSERT OR IGNORE INTO hives (hive_id, name, location, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        item["hive_id"],
                        item["name"],
                        item["location"],
                        item["latitude"],
                        item["longitude"],
                    )
                    for item in HIVE_METADATA
                ],
            )
            self.connection.executemany(
                """INSERT INTO sensor_readings
                   (hive_id, source_row, recorded_at, temperature_c, humidity_percent, ph, weight_kg)
                   VALUES (:hive_id, :source_row, :recorded_at, :temperature_c, :humidity_percent, :ph, :weight_kg)""",
                list(iter_enriched_rows(data_path)),
            )
            self.connection.commit()
        elif self.connection.execute("SELECT COUNT(*) FROM hives").fetchone()[0] != len(HIVE_METADATA):
            raise RuntimeError("Database contains readings but not the six expected hives")
        return self

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Cursor:
        cursor = self.connection.execute(sql, parameters)
        self.connection.commit()
        return cursor

    def executemany(self, sql: str, parameters: Iterable[Sequence[Any]]) -> sqlite3.Cursor:
        cursor = self.connection.executemany(sql, parameters)
        self.connection.commit()
        return cursor

    def fetchone(self, sql: str, parameters: Sequence[Any] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(sql, parameters).fetchone()
        return dict(row) if row is not None else None

    def fetchall(self, sql: str, parameters: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, parameters).fetchall()]

    def count(self, table: str) -> int:
        if table not in {"hives", "sensor_readings", "inspections"}:
            raise ValueError("Unknown table")
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def close(self) -> None:
        if not self._closed:
            self.connection.close()
            self._closed = True

    def __enter__(self) -> "HiveDatabase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def create_session_database(path: str | Path | None = None) -> HiveDatabase:
    """Create and seed an isolated SQLite file for one Gradio session.

    A directory path stores ``session.sqlite3`` inside it; a file path is used
    directly. Callers that need automatic cleanup can pass the path through
    :func:`cleanup_session` when Gradio's ``gr.State`` expires.
    """

    if path is None:
        directory = Path(tempfile.mkdtemp(prefix="les6-session-"))
        db_path = directory / "session.sqlite3"
    else:
        candidate = Path(path)
        if candidate.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            db_path = candidate
        else:
            candidate.mkdir(parents=True, exist_ok=True)
            db_path = candidate / "session.sqlite3"
    return HiveDatabase(db_path).initialize()


def copy_seed_database(destination: str | Path, *, data_path: str | Path = DATASET_PATH) -> HiveDatabase:
    """Build a deterministic seed database at ``destination``."""

    return HiveDatabase(destination).initialize(data_path=data_path)


initialize_database = copy_seed_database
create_session_db = create_session_database


def cleanup_session(value: object) -> None:
    """Gradio ``delete_callback``: close and remove an expired session DB."""

    if isinstance(value, HiveDatabase):
        path = value.path
        value.close()
    elif value:
        path = Path(str(value))
    else:
        return
    if path.is_file() and path.name == "session.sqlite3":
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


__all__ = [
    "HiveDatabase",
    "SCHEMA",
    "cleanup_session",
    "copy_seed_database",
    "create_session_database",
    "create_session_db",
    "initialize_database",
]
