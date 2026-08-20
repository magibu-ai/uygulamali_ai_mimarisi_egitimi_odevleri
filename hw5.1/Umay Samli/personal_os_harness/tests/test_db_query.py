from datetime import UTC, date, datetime, timedelta

import pytest

from personal_os.db._query import (
    bounded_limit,
    valid_offset,
    validate_aware_datetime,
    validate_date_range,
    validate_datetime_range,
)
from personal_os.db.postgres import DatabasePool


@pytest.mark.parametrize("limit", [1, 50, 500])
def test_bounded_limit_accepts_its_closed_range(limit: int) -> None:
    assert bounded_limit(limit) == limit


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_bounded_limit_rejects_values_outside_its_closed_range(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be between"):
        bounded_limit(limit)


def test_valid_offset_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="offset cannot be negative"):
        valid_offset(-1)


def test_datetime_validators_require_aware_ordered_values() -> None:
    aware_start = datetime(2026, 8, 13, 9, tzinfo=UTC)
    aware_end = aware_start + timedelta(hours=1)

    validate_aware_datetime(aware_start, "start")
    validate_datetime_range(aware_start, aware_end)

    with pytest.raises(ValueError, match="must be timezone-aware"):
        validate_aware_datetime(datetime(2026, 8, 13, 9), "start")
    with pytest.raises(ValueError, match="range_start must be before range_end"):
        validate_datetime_range(aware_end, aware_start)


def test_date_range_rejects_reverse_order() -> None:
    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        validate_date_range(date(2026, 8, 14), date(2026, 8, 13))


@pytest.mark.parametrize(
    ("min_size", "max_size", "timeout_seconds"),
    [(-1, 1, 1.0), (2, 1, 1.0), (0, 0, 1.0), (0, 1, 0.0)],
)
def test_database_pool_rejects_invalid_bounds(
    min_size: int, max_size: int, timeout_seconds: float
) -> None:
    with pytest.raises(ValueError):
        DatabasePool(
            "postgresql://unused",
            name="test",
            min_size=min_size,
            max_size=max_size,
            timeout_seconds=timeout_seconds,
        )
