from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from database.database_layer import Database, DatabaseError
from core.domain import PlanBlock, PlanDraft, Priority, TaskCreate, TaskStatus


TZ = ZoneInfo("Europe/Istanbul")


@pytest.fixture
def database(tmp_path):
    """Her test icin ayri ve baslatilmis gecici SQLite veritabani saglar."""

    db = Database(tmp_path / "planner.db")
    db.initialize()
    return db


def make_task(title: str = "Sunum") -> TaskCreate:
    """Veritabani testlerinde kullanilan gecerli bir gorev girdisi olusturur."""

    return TaskCreate(
        title=title,
        deadline=datetime(2026, 8, 7, 17, 0, tzinfo=TZ),
        estimated_minutes=120,
        priority=Priority.HIGH,
    )


def test_crud_and_session_isolation(database):
    """CRUD islemlerinin calistigini ve oturumlarin birbirini gormedigini dogrular."""

    task = database.create_task("session-a", make_task())

    assert [item.id for item in database.list_tasks("session-a")] == [task.id]
    assert database.list_tasks("session-b") == []
    assert database.get_task("session-b", task.id) is None

    completed = database.update_task_status(
        "session-a", task.id, TaskStatus.COMPLETED
    )
    assert completed.status is TaskStatus.COMPLETED

    with pytest.raises(DatabaseError):
        database.update_task_status("session-b", task.id, TaskStatus.ACTIVE)


def test_plan_is_saved_atomically(database):
    """Bir plan blogunun baslangic ve bitis degerleriyle birlikte kaydedildigini dogrular."""

    task = database.create_task("session-a", make_task())
    start = datetime(2026, 8, 3, 9, 0, tzinfo=TZ)
    draft = PlanDraft(
        week_start=datetime(2026, 8, 3, tzinfo=TZ),
        blocks=[
            PlanBlock(
                task_id=task.id,
                title=task.title,
                start=start,
                end=start + timedelta(minutes=120),
            )
        ],
        unscheduled=[],
    )

    saved = database.save_plan("session-a", draft)

    assert saved[0].scheduled_start == start
    assert saved[0].scheduled_end == start + timedelta(minutes=120)


def test_plan_rejects_task_from_another_session(database):
    """Baska oturuma ait gorevin plana yazilamadigini ve degismedigini dogrular."""

    task = database.create_task("session-a", make_task())
    start = datetime(2026, 8, 3, 9, 0, tzinfo=TZ)
    draft = PlanDraft(
        week_start=datetime(2026, 8, 3, tzinfo=TZ),
        blocks=[
            PlanBlock(
                task_id=task.id,
                title=task.title,
                start=start,
                end=start + timedelta(minutes=120),
            )
        ],
        unscheduled=[],
    )

    with pytest.raises(DatabaseError):
        database.save_plan("session-b", draft)

    assert database.get_task("session-a", task.id).scheduled_start is None
