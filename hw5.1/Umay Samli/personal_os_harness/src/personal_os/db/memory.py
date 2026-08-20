"""Bounded Psycopg read adapter for the private memory database."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from personal_os.db._query import bounded_limit, valid_offset, validate_aware_datetime
from personal_os.db.models import (
    ExperienceRecord,
    LessonEvidenceRecord,
    LessonRecord,
    LessonReviewRecord,
    LessonStatus,
    LessonWithEvidence,
    ProposalRecord,
)
from personal_os.db.postgres import DatabasePool, fetch_all, fetch_one

_EXPERIENCE_COLUMNS = """
    id,
    occurred_precision,
    occurred_date,
    occurred_at,
    occurred_start_at,
    occurred_end_at,
    title,
    narrative,
    context,
    outcome,
    reflection,
    statement_origin,
    sensitivity,
    tags,
    source_turn_id,
    version,
    created_at,
    updated_at
"""

_LESSON_COLUMNS = """
    id,
    statement,
    rationale,
    status,
    confidence,
    confidence_rationale,
    applicability,
    applicability_notes,
    review_policy,
    next_review_at,
    last_reviewed_at,
    superseded_by_id,
    sensitivity,
    tags,
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


class MemoryRepository:
    """Bounded read interface for the experience and lesson PostgreSQL database."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    def search_experiences(
        self,
        query_text: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ExperienceRecord, ...]:
        query_limit = bounded_limit(limit, maximum=100)
        query_offset = valid_offset(offset)
        query = f"""
            SELECT {_EXPERIENCE_COLUMNS}
            FROM experiences
            WHERE (
                %s = ''
                OR to_tsvector(
                    'simple',
                    title || ' ' || narrative || ' ' || coalesce(reflection, '')
                ) @@ plainto_tsquery('simple', %s)
            )
            ORDER BY
                CASE
                    WHEN %s = '' THEN 0
                    ELSE ts_rank(
                        to_tsvector(
                            'simple',
                            title || ' ' || narrative || ' ' || coalesce(reflection, '')
                        ),
                        plainto_tsquery('simple', %s)
                    )
                END DESC,
                created_at DESC,
                id
            LIMIT %s OFFSET %s
        """
        normalized_query = query_text.strip()
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (
                    normalized_query,
                    normalized_query,
                    normalized_query,
                    normalized_query,
                    query_limit,
                    query_offset,
                ),
                ExperienceRecord,
            )
        return tuple(records)

    def get_experience(self, experience_id: UUID) -> ExperienceRecord | None:
        query = f"""
            SELECT {_EXPERIENCE_COLUMNS}
            FROM experiences
            WHERE id = %s
        """
        with self._pool.connection() as connection:
            return fetch_one(
                connection,
                query,
                (experience_id,),
                ExperienceRecord,
            )

    def search_lessons(
        self,
        query_text: str,
        *,
        status: LessonStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[LessonRecord, ...]:
        query_limit = bounded_limit(limit, maximum=100)
        query_offset = valid_offset(offset)
        query = f"""
            SELECT {_LESSON_COLUMNS}
            FROM lessons
            WHERE (
                %s = ''
                OR to_tsvector('simple', statement || ' ' || rationale)
                    @@ plainto_tsquery('simple', %s)
            )
              AND (%s::text IS NULL OR status = %s)
            ORDER BY
                CASE
                    WHEN %s = '' THEN 0
                    ELSE ts_rank(
                        to_tsvector('simple', statement || ' ' || rationale),
                        plainto_tsquery('simple', %s)
                    )
                END DESC,
                updated_at DESC,
                id
            LIMIT %s OFFSET %s
        """
        normalized_query = query_text.strip()
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (
                    normalized_query,
                    normalized_query,
                    status,
                    status,
                    normalized_query,
                    normalized_query,
                    query_limit,
                    query_offset,
                ),
                LessonRecord,
            )
        return tuple(records)

    def get_lesson(self, lesson_id: UUID) -> LessonRecord | None:
        query = f"""
            SELECT {_LESSON_COLUMNS}
            FROM lessons
            WHERE id = %s
        """
        with self._pool.connection() as connection:
            return fetch_one(
                connection,
                query,
                (lesson_id,),
                LessonRecord,
            )

    def get_lesson_with_evidence(self, lesson_id: UUID) -> LessonWithEvidence | None:
        lesson = self.get_lesson(lesson_id)
        if lesson is None:
            return None

        query = """
            SELECT
                lesson_id,
                experience_id,
                relationship,
                relevance_explanation,
                provenance,
                created_at,
                updated_at
            FROM lesson_evidence
            WHERE lesson_id = %s
            ORDER BY
                CASE relationship
                    WHEN 'supports' THEN 0
                    WHEN 'contradicts' THEN 1
                    ELSE 2
                END,
                created_at,
                experience_id
        """
        with self._pool.connection() as connection:
            evidence = fetch_all(
                connection,
                query,
                (lesson_id,),
                LessonEvidenceRecord,
            )
        return LessonWithEvidence(lesson=lesson, evidence=tuple(evidence))

    def get_due_reviews(
        self,
        due_at: datetime,
        *,
        limit: int = 50,
    ) -> tuple[LessonRecord, ...]:
        validate_aware_datetime(due_at, "due_at")
        query_limit = bounded_limit(limit, maximum=100)
        query = f"""
            SELECT {_LESSON_COLUMNS}
            FROM lessons
            WHERE status = 'confirmed'
              AND next_review_at IS NOT NULL
              AND next_review_at <= %s
            ORDER BY next_review_at, updated_at, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (due_at, query_limit),
                LessonRecord,
            )
        return tuple(records)

    def list_reviews(
        self,
        lesson_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[LessonReviewRecord, ...]:
        query_limit = bounded_limit(limit, maximum=200)
        query = """
            SELECT
                id,
                lesson_id,
                outcome,
                reviewed_at,
                notes,
                next_review_at,
                proposal_id,
                proposal_revision,
                created_at
            FROM lesson_reviews
            WHERE lesson_id = %s
            ORDER BY reviewed_at DESC, id
            LIMIT %s
        """
        with self._pool.connection() as connection:
            records = fetch_all(
                connection,
                query,
                (lesson_id, query_limit),
                LessonReviewRecord,
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
