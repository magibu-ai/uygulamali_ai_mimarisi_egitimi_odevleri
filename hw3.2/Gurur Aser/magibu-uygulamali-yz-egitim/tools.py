"""Public tool-calling contract backed by one isolated SQLite database."""

from __future__ import annotations

import json
import sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

try:
    from .database import HiveDatabase, create_session_database
    from .data_loader import METRIC_COLUMNS
except ImportError:  # pragma: no cover - direct execution from les6/.
    from database import HiveDatabase, create_session_database
    from data_loader import METRIC_COLUMNS

STATES = ("normal", "izle", "dikkat")
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_hives",
            "description": "Kovanları son sensör ölçümleri ve istatistiksel durumlarıyla listeler; biyolojik tanı üretmez.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": [*STATES], "description": "İsteğe bağlı istatistiksel durum filtresi."}
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hive_details",
            "description": "Doğrulanmış bir kovanın sensör geçmişini ve saha kontrollerini getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hive_id": {"type": "string", "description": "hive-1 ile hive-6 arasında kovan kimliği."},
                    "reading_limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 24},
                },
                "required": ["hive_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_inspection",
            "description": "Mevcut kovana kraliçe, varroa ve not bilgisiyle saha kontrolü ekler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hive_id": {"type": "string", "description": "Mevcut kovan kimliği."},
                    "queen_seen": {"type": "boolean"},
                    "varroa_count": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "notes": {"type": "string", "maxLength": 500},
                },
                "required": ["hive_id", "queen_seen", "varroa_count", "notes"],
                "additionalProperties": False,
            },
        },
    },
]


def _error(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a quantile for an empty metric")
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


class HiveTools:
    """Three public tools with validation at the model/user boundary."""

    def __init__(self, database: HiveDatabase):
        self.database = database

    def _known_hive(self, hive_id: object) -> bool:
        return isinstance(hive_id, str) and self.database.fetchone("SELECT hive_id FROM hives WHERE hive_id = ?", (hive_id,)) is not None

    def _quantiles(self) -> dict[str, dict[str, float]]:
        rows = self.database.fetchall(
            "SELECT temperature_c, humidity_percent, ph, weight_kg FROM sensor_readings"
        )
        return {
            metric: {
                "p10": round(_quantile([float(row[metric]) for row in rows], 0.10), 6),
                "p90": round(_quantile([float(row[metric]) for row in rows], 0.90), 6),
            }
            for metric in METRIC_COLUMNS
        }

    @staticmethod
    def _status_for(reading: Mapping[str, Any], quantiles: Mapping[str, Mapping[str, float]]) -> tuple[str, list[str]]:
        outliers = [
            metric
            for metric in METRIC_COLUMNS
            if float(reading[metric]) < quantiles[metric]["p10"] or float(reading[metric]) > quantiles[metric]["p90"]
        ]
        return ("normal" if not outliers else "izle" if len(outliers) == 1 else "dikkat", outliers)

    def list_hives(self, status: str | None = None) -> dict[str, Any]:
        if status is not None and status not in STATES:
            return _error("VALIDATION_ERROR", f"status must be one of: {', '.join(STATES)}")
        try:
            quantiles = self._quantiles()
            hives = []
            for hive in self.database.fetchall("SELECT * FROM hives ORDER BY hive_id"):
                latest = self.database.fetchone(
                    "SELECT recorded_at, temperature_c, humidity_percent, ph, weight_kg FROM sensor_readings WHERE hive_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
                    (hive["hive_id"],),
                )
                if latest is None:
                    continue
                state, outliers = self._status_for(latest, quantiles)
                item = {
                    **hive,
                    "latest_reading": latest,
                    "status": state,
                    "outlier_metrics": outliers,
                }
                if status is None or state == status:
                    hives.append(item)
            return {"hives": hives, "quantiles": quantiles, "status_definition": "normal=0, izle=1, dikkat=2+ aykırı metrik"}
        except sqlite3.Error:
            return _error("DATABASE_ERROR", "Kovan veritabanı okunamadı.")

    def get_hive_details(self, hive_id: str, reading_limit: int = 24) -> dict[str, Any]:
        if not isinstance(hive_id, str) or not self._known_hive(hive_id):
            return _error("UNKNOWN_HIVE", f"Unknown hive: {hive_id}")
        if isinstance(reading_limit, bool) or not isinstance(reading_limit, int) or not 1 <= reading_limit <= 1000:
            return _error("VALIDATION_ERROR", "reading_limit must be an integer between 1 and 1000")
        try:
            hive = self.database.fetchone("SELECT * FROM hives WHERE hive_id = ?", (hive_id,))
            readings = self.database.fetchall(
                """SELECT recorded_at, temperature_c, humidity_percent, ph, weight_kg
                   FROM sensor_readings WHERE hive_id = ? ORDER BY recorded_at DESC, id DESC LIMIT ?""",
                (hive_id, reading_limit),
            )
            inspections = self.database.fetchall(
                """SELECT id, hive_id, queen_seen, varroa_count, notes, inspected_at
                   FROM inspections WHERE hive_id = ? ORDER BY inspected_at DESC, id DESC""",
                (hive_id,),
            )
            for inspection in inspections:
                inspection["queen_seen"] = bool(inspection["queen_seen"])
            return {"hive": hive, "readings": readings, "inspections": inspections, "reading_limit": reading_limit}
        except sqlite3.Error:
            return _error("DATABASE_ERROR", "Kovan ayrıntıları okunamadı.")

    def record_inspection(self, hive_id: str, queen_seen: bool, varroa_count: int, notes: str) -> dict[str, Any]:
        if not isinstance(hive_id, str) or not self._known_hive(hive_id):
            return _error("UNKNOWN_HIVE", f"Unknown hive: {hive_id}")
        if not isinstance(queen_seen, bool):
            return _error("VALIDATION_ERROR", "queen_seen must be a boolean")
        if isinstance(varroa_count, bool) or not isinstance(varroa_count, int) or not 0 <= varroa_count <= 1000:
            return _error("VALIDATION_ERROR", "varroa_count must be an integer between 0 and 1000")
        if not isinstance(notes, str) or len(notes) > 500:
            return _error("VALIDATION_ERROR", "notes must be a string of at most 500 characters")
        inspected_at = datetime.now(timezone.utc).isoformat()
        try:
            cursor = self.database.execute(
                """INSERT INTO inspections (hive_id, queen_seen, varroa_count, notes, inspected_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (hive_id, int(queen_seen), varroa_count, notes, inspected_at),
            )
            inspection = {
                "id": cursor.lastrowid,
                "hive_id": hive_id,
                "queen_seen": queen_seen,
                "varroa_count": varroa_count,
                "notes": notes,
                "inspected_at": inspected_at,
            }
            return {"inspection": inspection, "record": inspection}
        except sqlite3.Error:
            return _error("DATABASE_ERROR", "Kontrol kaydı yazılamadı.")

    def registry(self) -> dict[str, Callable[..., dict[str, Any]]]:
        return {
            "list_hives": self.list_hives,
            "get_hive_details": self.get_hive_details,
            "record_inspection": self.record_inspection,
        }


_active_tools: ContextVar[HiveTools | None] = ContextVar("les6_active_tools", default=None)
_default_tools: HiveTools | None = None


def configure_tools(database: HiveDatabase) -> HiveTools:
    tools = HiveTools(database)
    _active_tools.set(tools)
    return tools


def _get_active() -> HiveTools:
    global _default_tools
    tools = _active_tools.get()
    if tools is None:
        if _default_tools is None:
            _default_tools = HiveTools(create_session_database())
        tools = _default_tools
    return tools


def list_hives(status: str | None = None) -> dict[str, Any]:
    return _get_active().list_hives(status)


def get_hive_details(hive_id: str, reading_limit: int = 24) -> dict[str, Any]:
    return _get_active().get_hive_details(hive_id, reading_limit)


def record_inspection(hive_id: str, queen_seen: bool, varroa_count: int, notes: str) -> dict[str, Any]:
    return _get_active().record_inspection(hive_id, queen_seen, varroa_count, notes)


def tool_schemas() -> list[dict[str, Any]]:
    return TOOL_SCHEMAS


__all__ = [
    "HiveTools",
    "STATES",
    "TOOL_SCHEMAS",
    "configure_tools",
    "get_hive_details",
    "list_hives",
    "record_inspection",
    "tool_schemas",
]
