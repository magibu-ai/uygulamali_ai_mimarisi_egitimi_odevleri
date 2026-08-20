from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

from personal_os.db.models import (
    AvailabilityWindowRecord,
    CalendarBlockRecord,
    RecurringBlockRuleRecord,
    ScheduledSessionRecord,
    TimeInterval,
)
from personal_os.planning import FreeBusyError, compute_free_busy, local_date_bounds

CREATED_AT = datetime(2026, 8, 1, tzinfo=UTC)


def _availability(
    *,
    weekday: int,
    start: time = time(9),
    end: time = time(17),
) -> AvailabilityWindowRecord:
    return AvailabilityWindowRecord(
        id=uuid4(),
        weekday=weekday,
        start_local_time=start,
        end_local_time=end,
        effective_from=None,
        effective_until=None,
        label="Work",
        enabled=True,
        version=1,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _calendar_block(start_at: datetime, end_at: datetime) -> CalendarBlockRecord:
    return CalendarBlockRecord(
        id=uuid4(),
        title="Appointment",
        category=None,
        notes=None,
        load_class="non_personal",
        start_at=start_at,
        end_at=end_at,
        all_day_date=None,
        version=1,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _recurring_block(*, weekday: int) -> RecurringBlockRuleRecord:
    return RecurringBlockRuleRecord(
        id=uuid4(),
        title="Lunch",
        category=None,
        notes=None,
        load_class="personal",
        weekday=weekday,
        start_local_time=time(12),
        end_local_time=time(13),
        effective_from=None,
        effective_until=None,
        planning_timezone="Europe/Istanbul",
        enabled=True,
        version=1,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _session(
    start_at: datetime,
    end_at: datetime,
    *,
    status: str = "planned",
) -> ScheduledSessionRecord:
    return ScheduledSessionRecord(
        id=uuid4(),
        task_id=uuid4(),
        start_at=start_at,
        end_at=end_at,
        status=status,
        notes=None,
        proposal_id=uuid4(),
        proposal_revision=1,
        version=1,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _times(intervals: tuple[TimeInterval, ...]) -> list[tuple[str, str]]:
    return [
        (
            interval.start_at.isoformat(),
            interval.end_at.isoformat(),
        )
        for interval in intervals
    ]


def test_compute_free_busy_merges_blocks_and_subtracts_from_availability() -> None:
    range_start = datetime.fromisoformat("2026-08-13T00:00:00+03:00")
    range_end = range_start + timedelta(days=1)
    weekday = range_start.date().weekday()

    result = compute_free_busy(
        range_start,
        range_end,
        planning_timezone="Europe/Istanbul",
        availability_windows=(_availability(weekday=weekday),),
        calendar_blocks=(
            _calendar_block(
                datetime.fromisoformat("2026-08-13T10:00:00+03:00"),
                datetime.fromisoformat("2026-08-13T11:00:00+03:00"),
            ),
        ),
        recurring_blocks=(_recurring_block(weekday=weekday),),
        scheduled_sessions=(
            _session(
                datetime.fromisoformat("2026-08-13T15:00:00+03:00"),
                datetime.fromisoformat("2026-08-13T16:00:00+03:00"),
            ),
            _session(
                datetime.fromisoformat("2026-08-13T13:00:00+03:00"),
                datetime.fromisoformat("2026-08-13T14:00:00+03:00"),
                status="cancelled",
            ),
        ),
    )

    assert result.interval_semantics == "[start_at, end_at)"
    assert _times(result.busy) == [
        ("2026-08-13T10:00:00+03:00", "2026-08-13T11:00:00+03:00"),
        ("2026-08-13T12:00:00+03:00", "2026-08-13T13:00:00+03:00"),
        ("2026-08-13T15:00:00+03:00", "2026-08-13T16:00:00+03:00"),
    ]
    assert _times(result.free) == [
        ("2026-08-13T09:00:00+03:00", "2026-08-13T10:00:00+03:00"),
        ("2026-08-13T11:00:00+03:00", "2026-08-13T12:00:00+03:00"),
        ("2026-08-13T13:00:00+03:00", "2026-08-13T15:00:00+03:00"),
        ("2026-08-13T16:00:00+03:00", "2026-08-13T17:00:00+03:00"),
    ]


def test_all_day_block_removes_all_availability_for_its_date() -> None:
    range_start = datetime.fromisoformat("2026-08-13T00:00:00+03:00")
    range_end = range_start + timedelta(days=1)
    all_day = CalendarBlockRecord(
        id=uuid4(),
        title="Holiday",
        category=None,
        notes=None,
        load_class="personal",
        start_at=None,
        end_at=None,
        all_day_date=range_start.date(),
        version=1,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    result = compute_free_busy(
        range_start,
        range_end,
        planning_timezone="Europe/Istanbul",
        availability_windows=(_availability(weekday=range_start.date().weekday()),),
        calendar_blocks=(all_day,),
        recurring_blocks=(),
        scheduled_sessions=(),
    )

    assert result.free == ()
    assert _times(result.busy) == [("2026-08-13T00:00:00+03:00", "2026-08-14T00:00:00+03:00")]


def test_compute_free_busy_rejects_ambiguous_recurring_wall_time() -> None:
    range_start = datetime(2026, 11, 1, 4, tzinfo=UTC)
    range_end = datetime(2026, 11, 1, 9, tzinfo=UTC)
    ambiguous_window = _availability(
        weekday=date(2026, 11, 1).weekday(),
        start=time(1, 30),
        end=time(2, 30),
    )

    with pytest.raises(FreeBusyError, match="ambiguous local time"):
        compute_free_busy(
            range_start,
            range_end,
            planning_timezone="America/New_York",
            availability_windows=(ambiguous_window,),
            calendar_blocks=(),
            recurring_blocks=(),
            scheduled_sessions=(),
        )


def test_compute_free_busy_rejects_ranges_over_31_days() -> None:
    range_start = datetime(2026, 8, 1, tzinfo=UTC)

    with pytest.raises(FreeBusyError, match="cannot exceed 31 days"):
        compute_free_busy(
            range_start,
            range_start + timedelta(days=32),
            planning_timezone="Europe/Istanbul",
            availability_windows=(),
            calendar_blocks=(),
            recurring_blocks=(),
            scheduled_sessions=(),
        )


def test_local_date_bounds_treats_midnight_end_as_exclusive() -> None:
    assert local_date_bounds(
        datetime.fromisoformat("2026-08-13T00:00:00+03:00"),
        datetime.fromisoformat("2026-08-14T00:00:00+03:00"),
        "Europe/Istanbul",
    ) == (date(2026, 8, 13), date(2026, 8, 13))
