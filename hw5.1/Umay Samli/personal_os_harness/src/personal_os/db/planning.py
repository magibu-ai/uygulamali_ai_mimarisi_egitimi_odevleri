"""Bounded Psycopg read adapter for the planning database."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from personal_os.db._query import (
    bounded_limit,
    valid_offset,
    validate_aware_datetime,
    validate_date_range,
    validate_datetime_range,
)
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
from personal_os.db.postgres import DatabasePool, fetch_all, fetch_one

_TASK_COLUMNS = """
    id,
    parent_id,
    title,
    description,
    status,
    priority,
    estimate_minutes,
    category_id,
    earliest_start,
    deadline_at,
    deadline_precision,
    planning_timezone,
    splittable,
    min_session_minutes,
    max_session_minutes,
    constraints,
    notes,
    version,
    created_at,
    updated_at
"""

_PROPOSAL_COLUMNS = """
    id,
    revision,
    preview_hash,
    source_turn_id,
    redacted_source_summary,
    assumptions,
    status,
    validation_result,
    sensitivity,
    previewed_state_versions,
    correlation_metadata,
    applied_result,
    expires_at,
    applied_at,
    rejected_at,
    superseded_at,
    expired_at,
    created_at,
    updated_at
"""


class PlanningRepository:
    """Bounded read interface for the planning PostgreSQL database."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    def get_settings(self) -> PlanningSettingsRecord:
        query = """
            SELECT
                planning_timezone,
                scheduling_resolution_minutes,
                fallback_personal_reserve_minutes,
                daily_profile_complete_default,
                deadline_buffer_minutes,
                proposal_ttl_minutes,
                reminder_display_limit
            FROM settings
            WHERE singleton_id = 1
        """
        with self._pool.connection() as connection:
            record = fetch_one(
                connection,
                query,
                None,
                PlanningSettingsRecord,
            )
        if record is None:
            raise LookupError("planning settings row is missing")
        return record

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[TaskRecord, ...]:
        query_limit = bounded_limit(limit)
        query_offset = valid_offset(offset)
        query = f"""
            SELECT {_TASK_COLUMNS}
            FROM tasks
            WHERE (%s::text IS NULL OR status = %s)
            ORDER BY priority, deadline_at NULLS LAST, created_at, id
            LIMIT %s OFFSET %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (status, status, query_limit, query_offset),
                TaskRecord,
            )
        return tuple(records)

    def get_task(self, task_id: UUID) -> TaskRecord | None:
        query = f"""
            SELECT {_TASK_COLUMNS}
            FROM tasks
            WHERE id = %s
        """
        with self._pool.connection() as connection:
            return fetch_one(
                connection,
                query,
                (task_id,),
                TaskRecord,
            )

    def get_task_tree(self, root_task_id: UUID, *, limit: int = 500) -> tuple[TaskTreeNode, ...]:
        query_limit = bounded_limit(limit, maximum=500)
        query = f"""
            WITH RECURSIVE task_tree AS (
                SELECT
                    {_TASK_COLUMNS},
                    0 AS depth,
                    ARRAY[id] AS traversal_path
                FROM tasks
                WHERE id = %s

                UNION ALL

                SELECT
                    child.id,
                    child.parent_id,
                    child.title,
                    child.description,
                    child.status,
                    child.priority,
                    child.estimate_minutes,
                    child.category_id,
                    child.earliest_start,
                    child.deadline_at,
                    child.deadline_precision,
                    child.planning_timezone,
                    child.splittable,
                    child.min_session_minutes,
                    child.max_session_minutes,
                    child.constraints,
                    child.notes,
                    child.version,
                    child.created_at,
                    child.updated_at,
                    parent.depth + 1,
                    parent.traversal_path || child.id
                FROM tasks AS child
                JOIN task_tree AS parent ON child.parent_id = parent.id
                WHERE NOT child.id = ANY(parent.traversal_path)
            )
            SELECT
                {_TASK_COLUMNS},
                depth
            FROM task_tree
            ORDER BY traversal_path
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (root_task_id, query_limit),
                TaskTreeNode,
            )
        return tuple(records)

    def list_task_ancestors(
        self,
        task_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[TaskAncestorNode, ...]:
        query_limit = bounded_limit(limit, maximum=200)
        # Include a traversal path as defense in depth. Invalid historical rows
        # cannot make a recursive read loop forever while schema rules evolve.
        query = f"""
            WITH RECURSIVE ancestors AS (
                SELECT
                    {_TASK_COLUMNS},
                    0 AS distance,
                    ARRAY[id] AS traversal_path
                FROM tasks
                WHERE id = %s

                UNION ALL

                SELECT
                    parent.id,
                    parent.parent_id,
                    parent.title,
                    parent.description,
                    parent.status,
                    parent.priority,
                    parent.estimate_minutes,
                    parent.category_id,
                    parent.earliest_start,
                    parent.deadline_at,
                    parent.deadline_precision,
                    parent.planning_timezone,
                    parent.splittable,
                    parent.min_session_minutes,
                    parent.max_session_minutes,
                    parent.constraints,
                    parent.notes,
                    parent.version,
                    parent.created_at,
                    parent.updated_at,
                    child.distance + 1,
                    child.traversal_path || parent.id
                FROM tasks AS parent
                JOIN ancestors AS child ON parent.id = child.parent_id
                WHERE NOT parent.id = ANY(child.traversal_path)
            )
            SELECT
                {_TASK_COLUMNS},
                distance
            FROM ancestors
            WHERE distance > 0
            ORDER BY distance
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (task_id, query_limit),
                TaskAncestorNode,
            )
        return tuple(records)

    def list_dependencies(
        self,
        *,
        task_id: UUID | None = None,
        limit: int = 500,
    ) -> tuple[DependencyRecord, ...]:
        query_limit = bounded_limit(limit, maximum=500)
        query = """
            SELECT prerequisite_task_id, dependent_task_id, created_at
            FROM task_dependencies
            WHERE (
                %s::uuid IS NULL
                OR prerequisite_task_id = %s
                OR dependent_task_id = %s
            )
            ORDER BY created_at, prerequisite_task_id, dependent_task_id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (task_id, task_id, task_id, query_limit),
                DependencyRecord,
            )
        return tuple(records)

    def list_schedule(
        self,
        range_start: datetime,
        range_end: datetime,
        *,
        task_id: UUID | None = None,
        limit: int = 500,
    ) -> tuple[ScheduledSessionRecord, ...]:
        validate_datetime_range(range_start, range_end)
        query_limit = bounded_limit(limit, maximum=500)
        # Half-open overlap: a session ending exactly at range_start, or starting
        # exactly at range_end, does not intersect the requested interval.
        query = """
            SELECT
                id,
                task_id,
                start_at,
                end_at,
                status,
                notes,
                proposal_id,
                proposal_revision,
                version,
                created_at,
                updated_at
            FROM scheduled_sessions
            WHERE start_at < %s
              AND end_at > %s
              AND (%s::uuid IS NULL OR task_id = %s)
            ORDER BY start_at, end_at, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (range_end, range_start, task_id, task_id, query_limit),
                ScheduledSessionRecord,
            )
        return tuple(records)

    def list_availability(
        self,
        start_date: date,
        end_date: date,
        *,
        enabled_only: bool = True,
        limit: int = 500,
    ) -> tuple[AvailabilityWindowRecord, ...]:
        validate_date_range(start_date, end_date)
        query_limit = bounded_limit(limit, maximum=500)
        query = """
            SELECT
                id,
                weekday,
                start_local_time,
                end_local_time,
                effective_from,
                effective_until,
                label,
                enabled,
                version,
                created_at,
                updated_at
            FROM availability_windows
            WHERE (%s = false OR enabled)
              AND (effective_from IS NULL OR effective_from <= %s)
              AND (effective_until IS NULL OR effective_until >= %s)
            ORDER BY weekday, start_local_time, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (enabled_only, end_date, start_date, query_limit),
                AvailabilityWindowRecord,
            )
        return tuple(records)

    def list_calendar_blocks(
        self,
        range_start: datetime,
        range_end: datetime,
        *,
        local_start_date: date,
        local_end_date: date,
        limit: int = 500,
    ) -> tuple[CalendarBlockRecord, ...]:
        validate_datetime_range(range_start, range_end)
        validate_date_range(local_start_date, local_end_date)
        query_limit = bounded_limit(limit, maximum=500)
        query = """
            SELECT
                id,
                title,
                category,
                notes,
                load_class,
                start_at,
                end_at,
                all_day_date,
                version,
                created_at,
                updated_at
            FROM calendar_blocks
            WHERE (
                (start_at IS NOT NULL AND start_at < %s AND end_at > %s)
                OR all_day_date BETWEEN %s AND %s
            )
            ORDER BY all_day_date NULLS LAST, start_at NULLS LAST, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (
                    range_end,
                    range_start,
                    local_start_date,
                    local_end_date,
                    query_limit,
                ),
                CalendarBlockRecord,
            )
        return tuple(records)

    def list_recurring_blocks(
        self,
        start_date: date,
        end_date: date,
        *,
        enabled_only: bool = True,
        limit: int = 500,
    ) -> tuple[RecurringBlockRuleRecord, ...]:
        validate_date_range(start_date, end_date)
        query_limit = bounded_limit(limit, maximum=500)
        query = """
            SELECT
                id,
                title,
                category,
                notes,
                load_class,
                weekday,
                start_local_time,
                end_local_time,
                effective_from,
                effective_until,
                planning_timezone,
                enabled,
                version,
                created_at,
                updated_at
            FROM recurring_block_rules
            WHERE (%s = false OR enabled)
              AND (effective_from IS NULL OR effective_from <= %s)
              AND (effective_until IS NULL OR effective_until >= %s)
            ORDER BY weekday, start_local_time, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (enabled_only, end_date, start_date, query_limit),
                RecurringBlockRuleRecord,
            )
        return tuple(records)

    def list_contexts(
        self,
        applicable_at: datetime,
        *,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
        limit: int = 200,
    ) -> tuple[PlanningContextRecord, ...]:
        validate_aware_datetime(applicable_at, "applicable_at")
        query_limit = bounded_limit(limit, maximum=200)
        query = """
            SELECT
                id,
                scope_type,
                scope_id,
                kind,
                structured_value,
                notes,
                effective_from,
                effective_until,
                enabled,
                version,
                created_at,
                updated_at
            FROM planning_contexts
            WHERE enabled
              AND (%s::text IS NULL OR scope_type = %s)
              AND (%s::uuid IS NULL OR scope_id = %s)
              AND (effective_from IS NULL OR effective_from <= %s)
              AND (effective_until IS NULL OR effective_until > %s)
            ORDER BY
                CASE kind WHEN 'hard_constraint' THEN 0 ELSE 1 END,
                created_at,
                id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (
                    scope_type,
                    scope_type,
                    scope_id,
                    scope_id,
                    applicable_at,
                    applicable_at,
                    query_limit,
                ),
                PlanningContextRecord,
            )
        return tuple(records)

    def get_proposal(self, proposal_id: UUID, revision: int) -> ProposalRecord | None:
        if revision <= 0:
            raise ValueError("revision must be positive")
        query = f"""
            SELECT {_PROPOSAL_COLUMNS}
            FROM mutation_proposals
            WHERE id = %s AND revision = %s
        """
        with self._pool.connection() as connection:
            return fetch_one(
                connection,
                query,
                (proposal_id, revision),
                ProposalRecord,
            )
