from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb

from personal_os.db.memory import MemoryRepository
from personal_os.db.planning import PlanningRepository
from personal_os.db.postgres import DatabasePool

PLANNING_DSN = os.getenv(
    "PLANNING_DATABASE_URL",
    "postgresql://planning_runtime:change-me@127.0.0.1:5432/personal_os_planning",
)
MEMORY_DSN = os.getenv(
    "MEMORY_DATABASE_URL",
    "postgresql://memory_runtime:change-me@127.0.0.1:5432/personal_os_memory",
)
RUN_DATABASE_INTEGRATION = os.getenv("RUN_DATABASE_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not RUN_DATABASE_INTEGRATION,
        reason="set RUN_DATABASE_INTEGRATION=1 to use the local PostgreSQL stack",
    ),
]


@pytest.fixture
def planning_pool() -> Iterator[DatabasePool]:
    pool = DatabasePool(PLANNING_DSN, name="planning-integration")
    pool.open()
    try:
        yield pool
    finally:
        pool.close()


@pytest.fixture
def memory_pool() -> Iterator[DatabasePool]:
    pool = DatabasePool(MEMORY_DSN, name="memory-integration")
    pool.open()
    try:
        yield pool
    finally:
        pool.close()


def test_planning_repository_reads_settings_tasks_and_tree(
    planning_pool: DatabasePool,
) -> None:
    root_id = uuid4()
    child_id = uuid4()
    repository = PlanningRepository(planning_pool)

    with planning_pool.connection() as connection:
        connection.execute(
            """
            INSERT INTO tasks (id, title, status, priority, estimate_minutes)
            VALUES (%s, %s, 'ready', 2, 30)
            """,
            (
                root_id,
                f"Integration root {root_id.hex}",
            ),
        )
        connection.execute(
            """
            INSERT INTO tasks (
                id, parent_id, title, status, priority, estimate_minutes
            )
            VALUES (%s, %s, %s, 'ready', 3, 45)
            """,
            (
                child_id,
                root_id,
                f"Integration child {child_id.hex}",
            ),
        )
        connection.execute(
            """
            INSERT INTO task_dependencies (
                prerequisite_task_id, dependent_task_id
            )
            VALUES (%s, %s)
            """,
            (root_id, child_id),
        )

    try:
        settings = repository.get_settings()
        root = repository.get_task(root_id)
        tree = repository.get_task_tree(root_id)
        ancestors = repository.list_task_ancestors(child_id)
        dependencies = repository.list_dependencies(task_id=root_id)

        assert settings.planning_timezone == "Europe/Istanbul"
        assert root is not None
        assert root.id == root_id
        assert [(node.id, node.depth) for node in tree] == [
            (root_id, 0),
            (child_id, 1),
        ]
        assert [(node.id, node.distance) for node in ancestors] == [(root_id, 1)]
        assert len(dependencies) == 1
        assert dependencies[0].prerequisite_task_id == root_id
        assert dependencies[0].dependent_task_id == child_id
        assert repository.get_task(UUID(int=0)) is None
    finally:
        with planning_pool.connection() as connection:
            connection.execute(
                "DELETE FROM tasks WHERE id = ANY(%s)",
                ([child_id, root_id],),
            )


def test_memory_repository_searches_lessons_with_evidence_and_due_reviews(
    memory_pool: DatabasePool,
) -> None:
    experience_id = uuid4()
    lesson_id = uuid4()
    token = f"harnessdb{uuid4().hex}"
    due_at = datetime.now(UTC) - timedelta(hours=1)
    repository = MemoryRepository(memory_pool)

    with memory_pool.connection() as connection:
        connection.execute(
            """
            INSERT INTO experiences (
                id,
                occurred_precision,
                occurred_date,
                title,
                narrative,
                statement_origin,
                tags
            )
            VALUES (%s, 'date', %s, %s, %s, 'user_observation', %s)
            """,
            (
                experience_id,
                date.today(),
                f"{token} experience",
                "A database repository integration check succeeded.",
                [token],
            ),
        )
        connection.execute(
            """
            INSERT INTO lessons (
                id,
                statement,
                rationale,
                status,
                confidence,
                confidence_rationale,
                next_review_at,
                tags
            )
            VALUES (%s, %s, %s, 'confirmed', 'high', %s, %s, %s)
            """,
            (
                lesson_id,
                f"{token} validates repository reads",
                "The persisted experience supports the lesson.",
                "Observed through the real PostgreSQL adapter.",
                due_at,
                [token],
            ),
        )
        connection.execute(
            """
            INSERT INTO lesson_evidence (
                lesson_id,
                experience_id,
                relationship,
                relevance_explanation,
                provenance
            )
            VALUES (%s, %s, 'supports', %s, %s)
            """,
            (
                lesson_id,
                experience_id,
                "The integration fixture connects both records.",
                Jsonb({"source": "pytest"}),
            ),
        )

    try:
        experiences = repository.search_experiences(token)
        lessons = repository.search_lessons(token, status="confirmed")
        lesson_with_evidence = repository.get_lesson_with_evidence(lesson_id)
        due_reviews = repository.get_due_reviews(datetime.now(UTC))

        assert [experience.id for experience in experiences] == [experience_id]
        assert [lesson.id for lesson in lessons] == [lesson_id]
        assert lesson_with_evidence is not None
        assert lesson_with_evidence.lesson.id == lesson_id
        assert [item.experience_id for item in lesson_with_evidence.evidence] == [experience_id]
        assert lesson_id in {lesson.id for lesson in due_reviews}
        assert repository.get_experience(UUID(int=0)) is None
        assert repository.get_lesson(UUID(int=0)) is None
    finally:
        with memory_pool.connection() as connection:
            connection.execute("DELETE FROM lessons WHERE id = %s", (lesson_id,))
            connection.execute(
                "DELETE FROM experiences WHERE id = %s",
                (experience_id,),
            )
