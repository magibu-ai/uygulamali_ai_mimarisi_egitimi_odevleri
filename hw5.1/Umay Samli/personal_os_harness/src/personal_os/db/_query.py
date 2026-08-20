"""Shared validation for bounded PostgreSQL read queries."""

from datetime import date, datetime


def bounded_limit(limit: int, *, maximum: int = 500) -> int:
    if not 1 <= limit <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return limit


def valid_offset(offset: int) -> int:
    if offset < 0:
        raise ValueError("offset cannot be negative")
    return offset


def validate_aware_datetime(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def validate_datetime_range(range_start: datetime, range_end: datetime) -> None:
    validate_aware_datetime(range_start, "range_start")
    validate_aware_datetime(range_end, "range_end")
    if range_start >= range_end:
        raise ValueError("range_start must be before range_end")


def validate_date_range(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")
