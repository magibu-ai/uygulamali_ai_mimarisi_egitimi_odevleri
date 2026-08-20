import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from database.database_layer import Database
from core.domain import (
    Availability,
    PlanAssignment,
    PlanProposal,
    Priority,
    TaskCreate,
)
from services.planning_service import PlanningError, PlanningService


TZ = ZoneInfo("Europe/Istanbul")


class FakePlanClient:
    def __init__(self, payload):
        """Planlama servisine dondurulecek sabit model yanitini saklar."""

        self.payload = payload

    def chat(self, messages, tools=None, format_schema=None):
        """Sabit payload'u Ollama istemcisiyle ayni yanit biciminde dondurur."""

        return {"role": "assistant", "content": json.dumps(self.payload), "tool_calls": []}


@pytest.fixture
def setup(tmp_path):
    """Plan testleri icin veritabani, gorev ve haftalik uygunluk olusturur."""

    database = Database(tmp_path / "planner.db")
    database.initialize()
    task = database.create_task(
        "session-a",
        TaskCreate(
            title="Sunum",
            deadline=datetime(2026, 8, 7, 17, 0, tzinfo=TZ),
            estimated_minutes=120,
            priority=Priority.HIGH,
        ),
    )
    availability = Availability(
        week_start=datetime(2026, 8, 3, tzinfo=TZ),
        weekdays={0, 1, 2, 3, 4},
        day_start=time(9, 0),
        day_end=time(18, 0),
    )
    return database, task, availability


def test_generate_valid_plan(setup):
    """Gecerli model onerisinin taslaga donustugunu ancak DB'ye yazilmadigini dogrular."""

    database, task, availability = setup
    client = FakePlanClient(
        {
            "assignments": [
                {"task_id": task.id, "start": "2026-08-03T09:00:00+03:00"}
            ],
            "unscheduled": [],
        }
    )
    service = PlanningService(database, client)

    draft = service.generate("session-a", availability)

    assert draft.blocks[0].task_id == task.id
    assert draft.blocks[0].end.hour == 11
    assert database.get_task("session-a", task.id).scheduled_start is None


def test_validation_rejects_deadline_violation(setup):
    """Deadline sonrasina tasan plan blogunun reddedildigini dogrular."""

    database, task, availability = setup
    service = PlanningService(database, FakePlanClient({}))
    proposal = PlanProposal(
        assignments=[
            PlanAssignment(
                task_id=task.id,
                start=datetime(2026, 8, 7, 16, 0, tzinfo=TZ),
            )
        ],
        unscheduled=[],
    )

    with pytest.raises(PlanningError, match="deadline"):
        service.validate(proposal, [task], availability)


def test_validation_requires_every_real_task(setup):
    """Model taslaginda her gercek gorevin tam olarak yer almasini zorunlu tutar."""

    database, task, availability = setup
    service = PlanningService(database, FakePlanClient({}))

    with pytest.raises(PlanningError, match="Eksik"):
        service.validate(
            PlanProposal(assignments=[], unscheduled=[]),
            [task],
            availability,
        )


def test_invalid_model_output_uses_safe_fallback(setup):
    """Gecersiz model yanitinda deterministik guvenli planin kullanildigini dogrular."""

    database, task, availability = setup
    client = FakePlanClient({"assignments": [], "unscheduled": []})
    service = PlanningService(database, client, max_attempts=1)

    draft = service.generate("session-a", availability)

    assert [block.task_id for block in draft.blocks] == [task.id]
    assert draft.blocks[0].start == datetime(2026, 8, 3, 9, 0, tzinfo=TZ)
    assert database.get_task("session-a", task.id).scheduled_start is None
