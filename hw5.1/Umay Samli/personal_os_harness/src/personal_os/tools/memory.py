"""Bounded read tools over the private experience and lesson module interface."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID

from personal_os.db.models import (
    ExperienceRecord,
    LessonRecord,
    LessonReviewRecord,
    LessonStatus,
    LessonWithEvidence,
    ProposalRecord,
)
from personal_os.tools._arguments import Arguments
from personal_os.tools.core import (
    JsonObject,
    JsonValue,
    RegisteredTool,
    ToolDefinition,
    collection_result,
    item_result,
    object_parameters,
)

_SOURCE = "memory_database"
_LESSON_STATUSES = frozenset({"candidate", "confirmed", "superseded", "retired"})

_UUID: JsonObject = {"type": "string", "format": "uuid"}
_DATETIME: JsonObject = {"type": "string", "format": "date-time"}
_LESSON_STATUS_SCHEMA: JsonObject = {
    "type": "string",
    "enum": cast(list[JsonValue], sorted(_LESSON_STATUSES)),
}


def _integer_schema(*, default: int, maximum: int, minimum: int = 1) -> JsonObject:
    return {
        "type": "integer",
        "minimum": minimum,
        "maximum": maximum,
        "default": default,
    }


class MemoryReader(Protocol):
    """Read seam that keeps memory storage isolated from planning tools."""

    def search_experiences(
        self, query_text: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[ExperienceRecord, ...]: ...

    def get_experience(self, experience_id: UUID) -> ExperienceRecord | None: ...

    def search_lessons(
        self,
        query_text: str,
        *,
        status: LessonStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[LessonRecord, ...]: ...

    def get_lesson_with_evidence(self, lesson_id: UUID) -> LessonWithEvidence | None: ...

    def get_due_reviews(self, due_at: datetime, *, limit: int = 50) -> tuple[LessonRecord, ...]: ...

    def list_reviews(
        self, lesson_id: UUID, *, limit: int = 100
    ) -> tuple[LessonReviewRecord, ...]: ...

    def get_proposal(self, proposal_id: UUID, revision: int) -> ProposalRecord | None: ...


def memory_read_tools(reader: MemoryReader) -> tuple[RegisteredTool, ...]:
    """Build the bounded read-only memory tool set for one memory reader."""

    def search_experiences(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        query_text = parsed.required_string("query_text")
        limit = parsed.integer("limit", default=25, minimum=1, maximum=50)
        offset = parsed.integer("offset", default=0, minimum=0, maximum=10_000)
        parsed.finish()
        records = reader.search_experiences(query_text, limit=limit, offset=offset)
        return collection_result(
            _SOURCE,
            cast(tuple[object, ...], records),
            limit=limit,
            offset=offset,
        )

    def get_experience(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        experience_id = cast(UUID, parsed.uuid("experience_id"))
        parsed.finish()
        return item_result(_SOURCE, reader.get_experience(experience_id))

    def search_lessons(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        query_text = parsed.required_string("query_text")
        status = parsed.choice("status", _LESSON_STATUSES)
        limit = parsed.integer("limit", default=25, minimum=1, maximum=50)
        offset = parsed.integer("offset", default=0, minimum=0, maximum=10_000)
        parsed.finish()
        records = reader.search_lessons(
            query_text,
            status=cast(LessonStatus | None, status),
            limit=limit,
            offset=offset,
        )
        return collection_result(
            _SOURCE,
            cast(tuple[object, ...], records),
            limit=limit,
            offset=offset,
        )

    def get_lesson_with_evidence(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        lesson_id = cast(UUID, parsed.uuid("lesson_id"))
        parsed.finish()
        return item_result(_SOURCE, reader.get_lesson_with_evidence(lesson_id))

    def get_relevant_lessons(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        query_text = parsed.required_string("query_text")
        limit = parsed.integer("limit", default=10, minimum=1, maximum=25)
        parsed.finish()
        # Candidate and rejected interpretations are never surfaced as established
        # personal facts; only explicitly confirmed lessons are planning input.
        records = reader.search_lessons(
            query_text,
            status="confirmed",
            limit=limit,
            offset=0,
        )
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def get_due_reviews(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        due_at = parsed.datetime("due_at")
        limit = parsed.integer("limit", default=10, minimum=1, maximum=25)
        parsed.finish()
        records = reader.get_due_reviews(due_at, limit=limit)
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def list_reviews(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        lesson_id = cast(UUID, parsed.uuid("lesson_id"))
        limit = parsed.integer("limit", default=50, minimum=1, maximum=100)
        parsed.finish()
        records = reader.list_reviews(lesson_id, limit=limit)
        return collection_result(_SOURCE, cast(tuple[object, ...], records), limit=limit)

    def get_proposal(arguments: Mapping[str, object]) -> JsonValue:
        parsed = Arguments(arguments)
        proposal_id = cast(UUID, parsed.uuid("proposal_id"))
        revision = parsed.integer("revision", minimum=1)
        parsed.finish()
        return item_result(_SOURCE, reader.get_proposal(proposal_id, revision))

    search_properties: JsonObject = {
        "query_text": {
            "type": "string",
            "minLength": 1,
            "description": "Plain text to match using PostgreSQL full-text search.",
        },
        "limit": _integer_schema(default=25, maximum=50),
        "offset": _integer_schema(default=0, minimum=0, maximum=10_000),
    }

    return (
        RegisteredTool(
            ToolDefinition(
                "memory.search_experiences",
                "Search a bounded page of personal experiences by plain text.",
                object_parameters(search_properties, required=("query_text",)),
            ),
            search_experiences,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.get_experience",
                "Read one personal experience by UUID.",
                object_parameters({"experience_id": _UUID}, required=("experience_id",)),
            ),
            get_experience,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.search_lessons",
                "Search a bounded page of lessons by plain text and optional lifecycle status.",
                object_parameters(
                    {
                        **search_properties,
                        "status": _LESSON_STATUS_SCHEMA,
                    },
                    required=("query_text",),
                ),
            ),
            search_lessons,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.get_lesson_with_evidence",
                "Read one lesson and every supporting, contradicting, or contextual evidence link.",
                object_parameters({"lesson_id": _UUID}, required=("lesson_id",)),
            ),
            get_lesson_with_evidence,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.get_relevant_lessons",
                "Search a small bounded set of confirmed lessons relevant to plain text.",
                object_parameters(
                    {
                        "query_text": search_properties["query_text"],
                        "limit": _integer_schema(default=10, maximum=25),
                    },
                    required=("query_text",),
                ),
            ),
            get_relevant_lessons,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.get_due_reviews",
                "List confirmed lessons whose next review is due by an offset-aware timestamp.",
                object_parameters(
                    {
                        "due_at": _DATETIME,
                        "limit": _integer_schema(default=10, maximum=25),
                    },
                    required=("due_at",),
                ),
            ),
            get_due_reviews,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.list_reviews",
                "List a bounded review history for one lesson.",
                object_parameters(
                    {
                        "lesson_id": _UUID,
                        "limit": _integer_schema(default=50, maximum=100),
                    },
                    required=("lesson_id",),
                ),
            ),
            list_reviews,
        ),
        RegisteredTool(
            ToolDefinition(
                "memory.get_proposal",
                "Read one immutable memory proposal revision and its validation state.",
                object_parameters(
                    {
                        "proposal_id": _UUID,
                        "revision": {"type": "integer", "minimum": 1},
                    },
                    required=("proposal_id", "revision"),
                ),
            ),
            get_proposal,
        ),
    )
