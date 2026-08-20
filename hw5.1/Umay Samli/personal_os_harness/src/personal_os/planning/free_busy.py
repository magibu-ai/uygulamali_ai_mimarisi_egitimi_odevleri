"""Deterministic free/busy calculation over timezone-aware half-open intervals.

Recurring local-wall-time rules are expanded here; persistence only supplies facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from personal_os.db._query import validate_datetime_range
from personal_os.db.models import (
    AvailabilityWindowRecord,
    CalendarBlockRecord,
    FreeBusyResult,
    RecurringBlockRuleRecord,
    ScheduledSessionRecord,
    TimeInterval,
)

_MAX_RANGE = timedelta(days=31)
_NON_BLOCKING_SESSION_STATUSES = frozenset({"skipped", "cancelled"})


class FreeBusyError(ValueError):
    """Raised when a complete, unambiguous free/busy result cannot be computed."""


def local_date_bounds(
    range_start: datetime,
    range_end: datetime,
    timezone_name: str,
) -> tuple[date, date]:
    """Return inclusive local dates touched by an aware half-open range."""
    validate_datetime_range(range_start, range_end)
    zone = _timezone(timezone_name)
    start_date = range_start.astimezone(zone).date()
    end_date = (range_end - timedelta(microseconds=1)).astimezone(zone).date()
    return start_date, end_date


def compute_free_busy(
    range_start: datetime,
    range_end: datetime,
    *,
    planning_timezone: str,
    availability_windows: Sequence[AvailabilityWindowRecord],
    calendar_blocks: Sequence[CalendarBlockRecord],
    recurring_blocks: Sequence[RecurringBlockRuleRecord],
    scheduled_sessions: Sequence[ScheduledSessionRecord],
) -> FreeBusyResult:
    """Compute merged availability, busy, and free half-open intervals."""
    validate_datetime_range(range_start, range_end)
    if range_end - range_start > _MAX_RANGE:
        raise FreeBusyError("free/busy range cannot exceed 31 days")

    planning_zone = _timezone(planning_timezone)
    # Normalize set operations to UTC. Convert back to the planning zone only
    # after interval arithmetic is complete.
    range_start_utc = range_start.astimezone(UTC)
    range_end_utc = range_end.astimezone(UTC)
    planning_dates = tuple(_dates_covering(range_start_utc, range_end_utc, planning_zone))

    availability: list[TimeInterval] = []
    for window in availability_windows:
        if not window.enabled:
            continue
        for local_date in planning_dates:
            if local_date.weekday() == window.weekday and _date_is_effective(
                local_date,
                window.effective_from,
                window.effective_until,
            ):
                interval = _local_interval(
                    local_date,
                    window.start_local_time,
                    window.end_local_time,
                    planning_zone,
                )
                _append_clipped(
                    availability,
                    interval,
                    range_start_utc,
                    range_end_utc,
                )

    busy: list[TimeInterval] = []
    for block in calendar_blocks:
        if block.all_day_date is not None:
            # An all-day value is a civil date in the planning zone, not a fixed
            # 24-hour UTC duration.
            interval = _local_interval(
                block.all_day_date,
                time.min,
                time.min,
                planning_zone,
                end_on_next_date=True,
            )
        elif block.start_at is not None and block.end_at is not None:
            interval = TimeInterval(block.start_at, block.end_at)
        else:
            raise FreeBusyError(f"calendar block {block.id} has no valid interval")
        _append_clipped(busy, interval, range_start_utc, range_end_utc)

    for rule in recurring_blocks:
        if not rule.enabled:
            continue
        rule_zone = _timezone(rule.planning_timezone)
        for local_date in _dates_covering(range_start_utc, range_end_utc, rule_zone):
            if local_date.weekday() == rule.weekday and _date_is_effective(
                local_date,
                rule.effective_from,
                rule.effective_until,
            ):
                interval = _local_interval(
                    local_date,
                    rule.start_local_time,
                    rule.end_local_time,
                    rule_zone,
                )
                _append_clipped(busy, interval, range_start_utc, range_end_utc)

    for session in scheduled_sessions:
        if session.status in _NON_BLOCKING_SESSION_STATUSES:
            continue
        _append_clipped(
            busy,
            TimeInterval(session.start_at, session.end_at),
            range_start_utc,
            range_end_utc,
        )

    merged_availability = _merge_intervals(availability)
    merged_busy = _merge_intervals(busy)
    free = _subtract_intervals(merged_availability, merged_busy)

    return FreeBusyResult(
        range_start=range_start_utc.astimezone(planning_zone),
        range_end=range_end_utc.astimezone(planning_zone),
        planning_timezone=planning_timezone,
        interval_semantics="[start_at, end_at)",
        availability=_in_timezone(merged_availability, planning_zone),
        busy=_in_timezone(merged_busy, planning_zone),
        free=_in_timezone(free, planning_zone),
    )


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise FreeBusyError(f"unknown planning timezone: {name}") from error


def _dates_covering(
    range_start_utc: datetime,
    range_end_utc: datetime,
    zone: ZoneInfo,
) -> Sequence[date]:
    current = range_start_utc.astimezone(zone).date()
    final = range_end_utc.astimezone(zone).date()
    dates: list[date] = []
    while current <= final:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _date_is_effective(
    local_date: date,
    effective_from: date | None,
    effective_until: date | None,
) -> bool:
    return (effective_from is None or local_date >= effective_from) and (
        effective_until is None or local_date <= effective_until
    )


def _local_interval(
    local_date: date,
    start_time: time,
    end_time: time,
    zone: ZoneInfo,
    *,
    end_on_next_date: bool = False,
) -> TimeInterval:
    start_naive = datetime.combine(local_date, start_time.replace(tzinfo=None))
    end_date = local_date + timedelta(days=1) if end_on_next_date else local_date
    end_naive = datetime.combine(end_date, end_time.replace(tzinfo=None))
    start_at = _attach_unambiguous(start_naive, zone)
    end_at = _attach_unambiguous(end_naive, zone)
    if start_at >= end_at:
        raise FreeBusyError("local interval start must be before end")
    return TimeInterval(start_at, end_at)


def _attach_unambiguous(value: datetime, zone: ZoneInfo) -> datetime:
    # zoneinfo attaches offsets without rejecting DST gaps. Trying both folds and
    # round-tripping through UTC distinguishes a gap from a valid time and detects
    # repeated wall times that require an explicit user choice.
    candidates: dict[datetime, datetime] = {}
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        utc_value = candidate.astimezone(UTC)
        round_trip = utc_value.astimezone(zone)
        if round_trip.replace(tzinfo=None) == value:
            candidates[utc_value] = candidate

    if not candidates:
        raise FreeBusyError(f"nonexistent local time {value.isoformat()} in {zone.key}")
    if len(candidates) > 1:
        raise FreeBusyError(f"ambiguous local time {value.isoformat()} in {zone.key}")
    return next(iter(candidates.values()))


def _append_clipped(
    target: list[TimeInterval],
    interval: TimeInterval,
    range_start_utc: datetime,
    range_end_utc: datetime,
) -> None:
    start_at = interval.start_at.astimezone(UTC)
    end_at = interval.end_at.astimezone(UTC)
    clipped_start = max(start_at, range_start_utc)
    clipped_end = min(end_at, range_end_utc)
    if clipped_start < clipped_end:
        target.append(TimeInterval(clipped_start, clipped_end))


def _merge_intervals(intervals: Sequence[TimeInterval]) -> tuple[TimeInterval, ...]:
    ordered = sorted(intervals, key=lambda interval: (interval.start_at, interval.end_at))
    merged: list[TimeInterval] = []
    for interval in ordered:
        # Adjacent half-open intervals have no gap. Merging them preserves the
        # represented set while producing a smaller result.
        if not merged or interval.start_at > merged[-1].end_at:
            merged.append(interval)
            continue
        previous = merged[-1]
        merged[-1] = TimeInterval(
            previous.start_at,
            max(previous.end_at, interval.end_at),
        )
    return tuple(merged)


def _subtract_intervals(
    available: Sequence[TimeInterval],
    busy: Sequence[TimeInterval],
) -> tuple[TimeInterval, ...]:
    # Both inputs are sorted and merged. The inner loop can therefore stop once
    # a busy interval starts after the current availability window.
    free: list[TimeInterval] = []
    for available_interval in available:
        cursor = available_interval.start_at
        for busy_interval in busy:
            if busy_interval.end_at <= cursor:
                continue
            if busy_interval.start_at >= available_interval.end_at:
                break
            if busy_interval.start_at > cursor:
                free.append(
                    TimeInterval(
                        cursor,
                        min(busy_interval.start_at, available_interval.end_at),
                    )
                )
            cursor = max(cursor, busy_interval.end_at)
            if cursor >= available_interval.end_at:
                break
        if cursor < available_interval.end_at:
            free.append(TimeInterval(cursor, available_interval.end_at))
    return tuple(free)


def _in_timezone(
    intervals: Sequence[TimeInterval],
    zone: ZoneInfo,
) -> tuple[TimeInterval, ...]:
    return tuple(
        TimeInterval(
            interval.start_at.astimezone(zone),
            interval.end_at.astimezone(zone),
        )
        for interval in intervals
    )
