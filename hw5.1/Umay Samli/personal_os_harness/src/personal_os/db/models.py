"""Provider-independent records returned by the PostgreSQL adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal, TypeAlias
from uuid import UUID

# Recursive aliases describe JSON values at the persistence seam without importing
# provider-specific dictionaries into the domain records.
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

TaskStatus: TypeAlias = Literal[
    "draft",
    "ready",
    "in_progress",
    "blocked",
    "completed",
    "cancelled",
]
LessonStatus: TypeAlias = Literal["candidate", "confirmed", "superseded", "retired"]
ProposalStatus: TypeAlias = Literal["pending", "applied", "rejected", "superseded", "expired"]


@dataclass(frozen=True, slots=True)
class PlanningSettingsRecord:
    planning_timezone: str
    scheduling_resolution_minutes: int
    fallback_personal_reserve_minutes: int
    daily_profile_complete_default: bool
    deadline_buffer_minutes: int
    proposal_ttl_minutes: int
    reminder_display_limit: int


@dataclass(frozen=True, slots=True)
class TaskRecord:
    id: UUID
    parent_id: UUID | None
    title: str
    description: str | None
    status: str
    priority: int
    estimate_minutes: int | None
    category_id: UUID | None
    earliest_start: datetime | None
    deadline_at: datetime | None
    deadline_precision: str | None
    planning_timezone: str
    splittable: bool
    min_session_minutes: int | None
    max_session_minutes: int | None
    constraints: JsonObject
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TaskTreeNode(TaskRecord):
    depth: int


@dataclass(frozen=True, slots=True)
class TaskAncestorNode(TaskRecord):
    distance: int


@dataclass(frozen=True, slots=True)
class DependencyRecord:
    prerequisite_task_id: UUID
    dependent_task_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ScheduledSessionRecord:
    id: UUID
    task_id: UUID
    start_at: datetime
    end_at: datetime
    status: str
    notes: str | None
    proposal_id: UUID
    proposal_revision: int
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AvailabilityWindowRecord:
    id: UUID
    weekday: int
    start_local_time: time
    end_local_time: time
    effective_from: date | None
    effective_until: date | None
    label: str
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CalendarBlockRecord:
    id: UUID
    title: str
    category: str | None
    notes: str | None
    load_class: str
    start_at: datetime | None
    end_at: datetime | None
    all_day_date: date | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RecurringBlockRuleRecord:
    id: UUID
    title: str
    category: str | None
    notes: str | None
    load_class: str
    weekday: int
    start_local_time: time
    end_local_time: time
    effective_from: date | None
    effective_until: date | None
    planning_timezone: str
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlanningContextRecord:
    id: UUID
    scope_type: str
    scope_id: UUID | None
    kind: str
    structured_value: JsonObject
    notes: str | None
    effective_from: datetime | None
    effective_until: datetime | None
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TimeInterval:
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True, slots=True)
class FreeBusyResult:
    range_start: datetime
    range_end: datetime
    planning_timezone: str
    interval_semantics: str
    availability: tuple[TimeInterval, ...]
    busy: tuple[TimeInterval, ...]
    free: tuple[TimeInterval, ...]


@dataclass(frozen=True, slots=True)
class ProposalRecord:
    id: UUID
    revision: int
    preview_hash: str
    source_turn_id: str | None
    redacted_source_summary: str | None
    assumptions: JsonValue
    status: str
    validation_result: JsonObject
    sensitivity: str
    previewed_state_versions: JsonObject
    correlation_metadata: JsonObject
    applied_result: JsonObject | None
    expires_at: datetime
    applied_at: datetime | None
    rejected_at: datetime | None
    superseded_at: datetime | None
    expired_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    id: UUID
    occurred_precision: str
    occurred_date: date | None
    occurred_at: datetime | None
    occurred_start_at: datetime | None
    occurred_end_at: datetime | None
    title: str
    narrative: str
    context: JsonObject
    outcome: JsonObject
    reflection: str | None
    statement_origin: str
    sensitivity: str
    tags: list[str]
    source_turn_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LessonRecord:
    id: UUID
    statement: str
    rationale: str
    status: str
    confidence: str
    confidence_rationale: str
    applicability: JsonObject
    applicability_notes: str | None
    review_policy: JsonObject
    next_review_at: datetime | None
    last_reviewed_at: datetime | None
    superseded_by_id: UUID | None
    sensitivity: str
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LessonEvidenceRecord:
    lesson_id: UUID
    experience_id: UUID
    relationship: str
    relevance_explanation: str
    provenance: JsonObject
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LessonWithEvidence:
    lesson: LessonRecord
    evidence: tuple[LessonEvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class LessonReviewRecord:
    id: UUID
    lesson_id: UUID
    outcome: str
    reviewed_at: datetime
    notes: str | None
    next_review_at: datetime | None
    proposal_id: UUID | None
    proposal_revision: int | None
    created_at: datetime
