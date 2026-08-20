from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from personal_os.db.models import PlanningSettingsRecord, TaskStatus
from personal_os.tools import (
    MemoryReader,
    PlanningReader,
    RegisteredTool,
    ToolArgumentError,
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
    memory_read_tools,
    planning_read_tools,
)
from personal_os.tools.core import JsonValue, object_parameters, to_json_value


class PlanningStub:
    def __init__(self) -> None:
        self.list_call: tuple[TaskStatus | None, int, int] | None = None

    def get_settings(self) -> PlanningSettingsRecord:
        return PlanningSettingsRecord("Europe/Istanbul", 15, 720, False, 0, 30, 5)

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[object, ...]:
        self.list_call = (status, limit, offset)
        return ()


class MemoryStub:
    def __init__(self) -> None:
        self.lesson_call: tuple[str, str | None, int, int] | None = None
        self.due_call: tuple[datetime, int] | None = None

    def search_lessons(
        self,
        query_text: str,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[object, ...]:
        self.lesson_call = (query_text, status, limit, offset)
        return ()

    def get_due_reviews(self, due_at: datetime, *, limit: int = 50) -> tuple[object, ...]:
        self.due_call = (due_at, limit)
        return ()


def test_planning_tools_expose_namespaced_ollama_declarations() -> None:
    registry = ToolRegistry(planning_read_tools(cast(PlanningReader, PlanningStub())))
    names = {definition.name for definition in registry.definitions}

    assert "planning.get_settings" in names
    assert "planning.list_tasks" in names
    assert "planning.list_task_ancestors" in names
    assert "planning.get_free_busy" in names
    assert all(name.startswith("planning.") for name in names)
    assert all(".propose_" not in name for name in names)
    assert registry.as_ollama_tools()[0] == {
        "type": "function",
        "function": {
            "name": "planning.get_settings",
            "description": "Read the active planning configuration and scheduling defaults.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }


def test_planning_tool_parses_arguments_and_returns_bounded_envelope() -> None:
    reader = PlanningStub()
    registry = ToolRegistry(planning_read_tools(cast(PlanningReader, reader)))

    result = registry.execute(
        "planning.list_tasks",
        {"status": "ready", "limit": 12, "offset": 4},
    )

    assert reader.list_call == ("ready", 12, 4)
    assert result == {
        "source": "planning_database",
        "data": {"items": [], "count": 0, "limit": 12, "offset": 4},
    }


def test_planning_settings_are_json_safe() -> None:
    registry = ToolRegistry(planning_read_tools(cast(PlanningReader, PlanningStub())))

    result = registry.execute("planning.get_settings", {})

    assert isinstance(result, dict)
    assert cast(dict[str, object], result["data"])["planning_timezone"] == ("Europe/Istanbul")


@pytest.mark.parametrize(
    ("tool_name", "arguments", "message"),
    [
        ("planning.list_tasks", {"surprise": True}, "unexpected arguments"),
        ("planning.list_tasks", {"limit": 101}, "limit must be at most 100"),
        ("planning.get_task", {"task_id": "not-a-uuid"}, "valid UUID"),
        (
            "planning.list_schedule",
            {
                "range_start": "2026-08-13T09:00:00",
                "range_end": "2026-08-13T10:00:00+03:00",
            },
            "must include a UTC offset",
        ),
    ],
)
def test_planning_tools_reject_invalid_model_arguments(
    tool_name: str,
    arguments: Mapping[str, object],
    message: str,
) -> None:
    registry = ToolRegistry(planning_read_tools(cast(PlanningReader, PlanningStub())))

    with pytest.raises(ToolArgumentError, match=message):
        registry.execute(tool_name, arguments)


def test_relevant_lessons_force_confirmed_status_and_small_limit() -> None:
    reader = MemoryStub()
    registry = ToolRegistry(memory_read_tools(cast(MemoryReader, reader)))

    result = registry.execute(
        "memory.get_relevant_lessons",
        {"query_text": "starting difficult tasks", "limit": 7},
    )

    assert reader.lesson_call == ("starting difficult tasks", "confirmed", 7, 0)
    assert result == {
        "source": "memory_database",
        "data": {"items": [], "count": 0, "limit": 7},
    }


def test_due_reviews_require_an_offset_aware_timestamp() -> None:
    reader = MemoryStub()
    registry = ToolRegistry(memory_read_tools(cast(MemoryReader, reader)))

    registry.execute(
        "memory.get_due_reviews",
        {"due_at": "2026-08-13T12:30:00+03:00", "limit": 4},
    )

    assert reader.due_call is not None
    assert reader.due_call[0].isoformat() == "2026-08-13T12:30:00+03:00"
    assert reader.due_call[1] == 4


def test_memory_tools_reject_empty_search_text() -> None:
    registry = ToolRegistry(memory_read_tools(cast(MemoryReader, MemoryStub())))

    with pytest.raises(ToolArgumentError, match="non-empty string"):
        registry.execute("memory.search_lessons", {"query_text": "   "})


def test_registry_rejects_unknown_and_duplicate_tools() -> None:
    def handler(arguments: Mapping[str, object]) -> JsonValue:
        assert arguments == {}
        return None

    tool = RegisteredTool(
        ToolDefinition("test.read", "Read test data.", object_parameters({})),
        handler,
    )

    with pytest.raises(ValueError, match="duplicate tool name"):
        ToolRegistry((tool, tool))
    with pytest.raises(ToolNotFoundError, match="unknown tool"):
        ToolRegistry((tool,)).execute("test.missing", {})


@dataclass(frozen=True)
class SerializableRecord:
    id: UUID
    occurred_at: datetime
    tags: tuple[str, ...]


def test_json_conversion_handles_records_and_standard_types() -> None:
    record_id = uuid4()

    result = to_json_value(
        SerializableRecord(
            record_id,
            datetime.fromisoformat("2026-08-13T09:00:00+03:00"),
            ("planning", "focus"),
        )
    )

    assert result == {
        "id": str(record_id),
        "occurred_at": "2026-08-13T09:00:00+03:00",
        "tags": ["planning", "focus"],
    }
