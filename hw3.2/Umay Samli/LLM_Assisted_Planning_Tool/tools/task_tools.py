"""Gorev veritabanini guvenli fonksiyonlar olarak modele acar."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from database.database_layer import Database, DatabaseError
from core.domain import Priority, TaskCreate, TaskStatus


class CreateTaskArguments(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    deadline: str
    estimated_minutes: int = Field(ge=15, le=720, multiple_of=15)
    priority: Priority = Priority.MEDIUM


class ListTasksArguments(BaseModel):
    status: TaskStatus | None = None
    date_from: str | None = None
    date_to: str | None = None


class UpdateTaskStatusArguments(BaseModel):
    task_id: int = Field(gt=0)
    status: TaskStatus


class TaskTools:
    def __init__(self, database: Database, timezone: str = "Europe/Istanbul") -> None:
        """Tool islemleri icin veritabani ve saat dilimi bagimliliklarini saklar."""

        self.database = database
        self.timezone = ZoneInfo(timezone)

    @property
    def schemas(self) -> list[dict[str, Any]]:
        """Modelin cagirabilecegi izinli fonksiyon semalarini dondurur."""

        return [
            {
                "type": "function",
                "function": {
                    "name": "create_task",
                    "description": (
                        "Kullanicinin acikca verdigi gorevi veritabanina kaydeder. "
                        "Tahmini sure bilinmiyorsa bu araci cagirma; kullaniciya sor."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "deadline": {
                                "type": "string",
                                "description": "ISO 8601 tarih veya tarih-saat",
                            },
                            "estimated_minutes": {
                                "type": "integer",
                                "minimum": 15,
                                "maximum": 720,
                                "multipleOf": 15,
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                        },
                        "required": ["title", "deadline", "estimated_minutes", "priority"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": (
                        "Oturumdaki gercek gorevleri listeler. Gorevler hakkinda cevap "
                        "vermeden once kullanilmalidir."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": ["string", "null"],
                                "enum": ["active", "completed", None],
                            },
                            "date_from": {"type": ["string", "null"]},
                            "date_to": {"type": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_task_status",
                    "description": (
                        "Yalniz mevcut bir gorevi aktif veya tamamlandi durumuna getirir. "
                        "Kimlik bilinmiyorsa once list_tasks kullan."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "integer", "minimum": 1},
                            "status": {
                                "type": "string",
                                "enum": ["active", "completed"],
                            },
                        },
                        "required": ["task_id", "status"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def execute(
        self, name: str, arguments: dict[str, Any], session_id: str
    ) -> dict[str, Any]:
        """Tool adini dogrular, argumanlari parse eder ve ilgili DB islemini calistirir."""

        try:
            if name == "create_task":
                parsed = CreateTaskArguments.model_validate(arguments)
                deadline = self._parse_datetime(parsed.deadline, end_of_day=True)
                task = self.database.create_task(
                    session_id,
                    TaskCreate(
                        title=parsed.title,
                        deadline=deadline,
                        estimated_minutes=parsed.estimated_minutes,
                        priority=parsed.priority,
                    ),
                )
                return {"ok": True, "task": self._serialize_task(task)}
            if name == "list_tasks":
                parsed = ListTasksArguments.model_validate(arguments)
                tasks = self.database.list_tasks(
                    session_id,
                    parsed.status,
                    self._parse_datetime(parsed.date_from) if parsed.date_from else None,
                    self._parse_datetime(parsed.date_to, end_of_day=True)
                    if parsed.date_to
                    else None,
                )
                return {
                    "ok": True,
                    "count": len(tasks),
                    "tasks": [self._serialize_task(task) for task in tasks],
                }
            if name == "update_task_status":
                parsed = UpdateTaskStatusArguments.model_validate(arguments)
                task = self.database.update_task_status(
                    session_id, parsed.task_id, parsed.status
                )
                return {"ok": True, "task": self._serialize_task(task)}
            return {"ok": False, "error": f"Izin verilmeyen arac: {name}"}
        except (ValidationError, ValueError, DatabaseError) as error:
            return {"ok": False, "error": str(error)}

    def _parse_datetime(self, raw: str, end_of_day: bool = False) -> datetime:
        """ISO tarih girdisini uygulama saat diliminde timezone-aware degere cevirir."""

        value = raw.strip()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Tarih ISO 8601 biciminde olmalidir") from error
        if "T" not in value and " " not in value:
            parsed = datetime.combine(
                parsed.date(), time(23, 59, 59) if end_of_day else time.min
            )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self.timezone)
        return parsed.astimezone(self.timezone)

    @staticmethod
    def _serialize_task(task: Any) -> dict[str, Any]:
        """Task modelini modele verilecek JSON uyumlu ve oturumsuz veriye cevirir."""

        return task.model_dump(mode="json", exclude={"session_id"})
