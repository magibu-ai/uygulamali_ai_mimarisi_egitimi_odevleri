"""Bounded read tools over the planning module interface."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Protocol, cast
from uuid import UUID

from personal_os.db.models import (
    AvailabilityWindowRecord,
    CalendarBlockRecord,
    DependencyRecord,
    PlanningContextRecord,
    PlanningSettingsRecord,
    ProposalRecord,
    RecurringBlockRuleRecord,
    ScheduledSessionRecord,
    TaskAncestorNode,
    TaskRecord,
    TaskStatus,
    TaskTreeNode,
)
from personal_os.planning import compute_free_busy, local_date_bounds
from personal_os.tools._arguments import Arguments
from personal_os.tools.core import (
    JsonObject,
    JsonValue,
    RegisteredTool,
    ToolDefinition,
    collection_result,
    database_result,
    item_result,
    object_parameters,
    to_json_value,
)

_SOURCE = "planning_database"
_TASK_STATUSES = frozenset({"draft", "ready", "in_progress", "blocked", "completed", "cancelled"})

_STRING: JsonObject = {"type": "string"}
_UUID: JsonObject = {"type": "string", "format": "uuid"}
_DATE: JsonObject = {"type": "string", "format": "date"}
_DATETIME: JsonObject = {"type": "string", "format": "date-time"}
_BOOLEAN: JsonObject = {"type": "boolean"}
_TASK_STATUS_SCHEMA: JsonObject = {
    "type": "string",
    "enum": cast(list[JsonValue], sorted(_TASK_STATUSES)),
}


def _integer_schema(*, default: int, maximum: int) -> JsonObject:
    return {
        "type": "integer",
        "minimum": 1,
        "maximum": maximum,
        "default": default,
    }


class PlanningReader(Protocol):
    """Read seam used by planning tools without exposing Psycopg to the model."""

    def get_settings(self) -> PlanningSettingsRecord: ...

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[TaskRecord, ...]: ...

    def get_task(self, task_id: UUID) -> TaskRecord | None: ...

    def get_task_tree(
        self, root_task_id: UUID, *, limit: int = 500
    ) -> tuple[TaskTreeNode, ...]: ...

    def list_task_ancestors(
        self, task_id: UUID, *, limit: int = 100
    ) -> tuple[TaskAncestorNode, ...]: ...

    def list_dependencies(
        self, *, task_id: UUID | None = None, limit: int = 500
    ) -> tuple[DependencyRecord, ...]: ...

    def list_schedule(
        self,
        range_start: datetime,
        range_end: datetime,
        *,
        task_id: UUID | None = None,
        limit: int = 500,
    ) -> tuple[ScheduledSessionRecord, ...]: ...

    def list_availability(
        self,
        start_date: date,
        end_date: date,
        *,
        enabled_only: bool = True,
        limit: int = 500,
    ) -> tuple[AvailabilityWindowRecord, ...]: ...

    def list_calendar_blocks(
        self,
        range_start: datetime,
        range_end: datetime,
        *,
        local_start_date: date,
        local_end_date: date,
        limit: int = 500,
    ) -> tuple[CalendarBlockRecord, ...]: ...

    def list_recurring_blocks(
        self,
        start_date: date,
        end_date: date,
        *,
        enabled_only: bool = True,
        limit: int = 500,
    ) -> tuple[RecurringBlockRuleRecord, ...]: ...

    def list_contexts(
        self,
        applicable_at: datetime,
        *,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
        limit: int = 200,
    ) -> tuple[PlanningContextRecord, ...]: ...

    def get_proposal(self, proposal_id: UUID, revision: int) -> ProposalRecord | None: ...


def planning_read_tools(reader: PlanningReader) -> tuple[RegisteredTool, ...]:
    """Build the bounded read-only planning tool set for one planning reader."""

    def get_settings(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        parsed.finish()
        return database_result(_SOURCE, to_json_value(reader.get_settings()))

    def list_tasks(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        status = parsed.choice("status", _TASK_STATUSES)
        limit = parsed.integer("limit", default=50, minimum=1, maximum=100)
        offset = parsed.integer("offset", default=0, minimum=0, maximum=10_000)
        parsed.finish()
        records = reader.list_tasks(
            status=cast(TaskStatus | None, status),
            limit=limit,
            offset=offset,
        )
        return collection_result(
            _SOURCE, cast(tuple[object, ...], records), limit=limit, offset=offset
        )

    def get_task(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        task_id = cast(UUID, parsed.uuid("task_id"))
        parsed.finish()
        return item_result(_SOURCE, reader.get_task(task_id))

    def get_task_tree(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        task_id = cast(UUID, parsed.uuid("root_task_id"))
        limit = parsed.integer("limit", default=100, minimum=1, maximum=200)
        parsed.finish()
        records = reader.get_task_tree(task_id, limit=limit)
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_task_ancestors(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        task_id = cast(UUID, parsed.uuid("task_id"))
        limit = parsed.integer("limit", default=25, minimum=1, maximum=100)
        parsed.finish()
        records = reader.list_task_ancestors(task_id, limit=limit)
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_dependencies(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        task_id = parsed.uuid("task_id", required=False)
        limit = parsed.integer("limit", default=100, minimum=1, maximum=200)
        parsed.finish()
        records = reader.list_dependencies(task_id=task_id, limit=limit)
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_schedule(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        range_start = parsed.datetime("range_start")
        range_end = parsed.datetime("range_end")
        task_id = parsed.uuid("task_id", required=False)
        limit = parsed.integer("limit", default=100, minimum=1, maximum=200)
        parsed.finish()
        records = reader.list_schedule(
            range_start,
            range_end,
            task_id=task_id,
            limit=limit,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_availability(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        start_date = parsed.date("start_date")
        end_date = parsed.date("end_date")
        enabled_only = parsed.boolean("enabled_only", default=True)
        limit = parsed.integer("limit", default=100, minimum=1, maximum=100)
        parsed.finish()
        records = reader.list_availability(
            start_date,
            end_date,
            enabled_only=enabled_only,
            limit=limit,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_calendar_blocks(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        range_start = parsed.datetime("range_start")
        range_end = parsed.datetime("range_end")
        local_start_date = parsed.date("local_start_date")
        local_end_date = parsed.date("local_end_date")
        limit = parsed.integer("limit", default=100, minimum=1, maximum=200)
        parsed.finish()
        records = reader.list_calendar_blocks(
            range_start,
            range_end,
            local_start_date=local_start_date,
            local_end_date=local_end_date,
            limit=limit,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_recurring_blocks(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        start_date = parsed.date("start_date")
        end_date = parsed.date("end_date")
        enabled_only = parsed.boolean("enabled_only", default=True)
        limit = parsed.integer("limit", default=100, minimum=1, maximum=100)
        parsed.finish()
        records = reader.list_recurring_blocks(
            start_date,
            end_date,
            enabled_only=enabled_only,
            limit=limit,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def get_free_busy(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        range_start = parsed.datetime("range_start")
        range_end = parsed.datetime("range_end")
        parsed.finish()
        settings = reader.get_settings()
        start_date, end_date = local_date_bounds(range_start, range_end, settings.planning_timezone)
        # Gather authoritative facts first, then perform interval arithmetic in the
        # deterministic planning module rather than asking the model to calculate it.
        availability = reader.list_availability(start_date, end_date, enabled_only=True, limit=500)
        calendar_blocks = reader.list_calendar_blocks(
            range_start,
            range_end,
            local_start_date=start_date,
            local_end_date=end_date,
            limit=500,
        )
        recurring_blocks = reader.list_recurring_blocks(
            start_date, end_date, enabled_only=True, limit=500
        )
        scheduled_sessions = reader.list_schedule(range_start, range_end, limit=500)
        result = compute_free_busy(
            range_start,
            range_end,
            planning_timezone=settings.planning_timezone,
            availability_windows=availability,
            calendar_blocks=calendar_blocks,
            recurring_blocks=recurring_blocks,
            scheduled_sessions=scheduled_sessions,
        )
        return database_result(_SOURCE, to_json_value(result))

    def list_contexts(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        applicable_at = parsed.datetime("applicable_at")
        scope_type = parsed.optional_string("scope_type")
        scope_id = parsed.uuid("scope_id", required=False)
        limit = parsed.integer("limit", default=50, minimum=1, maximum=100)
        parsed.finish()
        records = reader.list_contexts(
            applicable_at,
            scope_type=scope_type,
            scope_id=scope_id,
            limit=limit,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def get_proposal(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        proposal_id = cast(UUID, parsed.uuid("proposal_id"))
        revision = parsed.integer("revision", minimum=1)
        parsed.finish()
        return item_result(_SOURCE, reader.get_proposal(proposal_id, revision))

    return (
        RegisteredTool(
            ToolDefinition(
                "planning.get_settings",
                "Read the active planning configuration and scheduling defaults.",
                object_parameters({}),
            ),
            get_settings,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_tasks",
                "List a bounded page of tasks, optionally filtered by status.",
                object_parameters(
                    {
                        "status": _TASK_STATUS_SCHEMA,
                        "limit": _integer_schema(default=50, maximum=100),
                        "offset": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 10_000,
                            "default": 0,
                        },
                    }
                ),
            ),
            list_tasks,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.get_task",
                "Read one task by UUID.",
                object_parameters({"task_id": _UUID}, required=("task_id",)),
            ),
            get_task,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.get_task_tree",
                "Read a task and its descendants in hierarchy order.",
                object_parameters(
                    {
                        "root_task_id": _UUID,
                        "limit": _integer_schema(default=100, maximum=200),
                    },
                    required=("root_task_id",),
                ),
            ),
            get_task_tree,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_task_ancestors",
                "Read the ancestors of one task, nearest parent first.",
                object_parameters(
                    {
                        "task_id": _UUID,
                        "limit": _integer_schema(default=25, maximum=100),
                    },
                    required=("task_id",),
                ),
            ),
            list_task_ancestors,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_dependencies",
                "Inspect a bounded dependency neighborhood or the bounded dependency graph.",
                object_parameters(
                    {
                        "task_id": _UUID,
                        "limit": _integer_schema(default=100, maximum=200),
                    }
                ),
            ),
            list_dependencies,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_schedule",
                "List scheduled task sessions overlapping a half-open timestamp range.",
                object_parameters(
                    {
                        "range_start": _DATETIME,
                        "range_end": _DATETIME,
                        "task_id": _UUID,
                        "limit": _integer_schema(default=100, maximum=200),
                    },
                    required=("range_start", "range_end"),
                ),
            ),
            list_schedule,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_availability",
                "List recurring availability rules applicable to an inclusive local-date range.",
                object_parameters(
                    {
                        "start_date": _DATE,
                        "end_date": _DATE,
                        "enabled_only": {**_BOOLEAN, "default": True},
                        "limit": _integer_schema(default=100, maximum=100),
                    },
                    required=("start_date", "end_date"),
                ),
            ),
            list_availability,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_calendar_blocks",
                "List timed and all-day calendar blocks overlapping the requested range.",
                object_parameters(
                    {
                        "range_start": _DATETIME,
                        "range_end": _DATETIME,
                        "local_start_date": _DATE,
                        "local_end_date": _DATE,
                        "limit": _integer_schema(default=100, maximum=200),
                    },
                    required=(
                        "range_start",
                        "range_end",
                        "local_start_date",
                        "local_end_date",
                    ),
                ),
            ),
            list_calendar_blocks,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_recurring_blocks",
                "List recurring blocked-time rules applicable to an inclusive local-date range.",
                object_parameters(
                    {
                        "start_date": _DATE,
                        "end_date": _DATE,
                        "enabled_only": {**_BOOLEAN, "default": True},
                        "limit": _integer_schema(default=100, maximum=100),
                    },
                    required=("start_date", "end_date"),
                ),
            ),
            list_recurring_blocks,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.get_free_busy",
                (
                    "Compute merged availability, busy, and free half-open intervals "
                    "for at most 31 days."
                ),
                object_parameters(
                    {
                        "range_start": _DATETIME,
                        "range_end": _DATETIME,
                    },
                    required=("range_start", "range_end"),
                ),
            ),
            get_free_busy,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.list_contexts",
                "Read enabled planning constraints and preferences applicable at a timestamp.",
                object_parameters(
                    {
                        "applicable_at": _DATETIME,
                        "scope_type": _STRING,
                        "scope_id": _UUID,
                        "limit": _integer_schema(default=50, maximum=100),
                    },
                    required=("applicable_at",),
                ),
            ),
            list_contexts,
        ),
        RegisteredTool(
            ToolDefinition(
                "planning.get_proposal",
                "Read one immutable planning proposal revision and its validation state.",
                object_parameters(
                    {
                        "proposal_id": _UUID,
                        "revision": {
                            "type": "integer",
                            "minimum": 1,
                        },
                    },
                    required=("proposal_id", "revision"),
                ),
            ),
            get_proposal,
        ),
    )
