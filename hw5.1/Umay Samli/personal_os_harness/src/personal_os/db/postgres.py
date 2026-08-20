"""Psycopg pool lifecycle and typed row-decoding helpers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType
from typing import TypeAlias, TypeVar

from psycopg import Connection, OperationalError
from psycopg.abc import Params, QueryNoTemplate
from psycopg.rows import TupleRow, class_row
from psycopg_pool import ConnectionPool, PoolTimeout

from personal_os.config import ConfigurationError, Settings

DatabaseConnection: TypeAlias = Connection[TupleRow]
RecordT = TypeVar("RecordT")


class DatabaseUnavailableError(RuntimeError):
    """Raised when a configured PostgreSQL database cannot be reached."""


class DatabasePool:
    """Own a bounded Psycopg pool without exposing connection credentials."""

    def __init__(
        self,
        dsn: str,
        *,
        name: str,
        min_size: int = 1,
        max_size: int = 4,
        timeout_seconds: float = 10.0,
    ) -> None:
        if min_size < 0:
            raise ValueError("min_size cannot be negative")
        if max_size < 1 or max_size < min_size:
            raise ValueError("max_size must be positive and at least min_size")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self._name = name
        self._timeout_seconds = timeout_seconds
        # Explicit open/close keeps database access out of module import time and
        # makes independent planning and memory failures observable.
        self._pool: ConnectionPool[DatabaseConnection] = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
            name=name,
            timeout=timeout_seconds,
            check=ConnectionPool.check_connection,
        )

    @property
    def name(self) -> str:
        return self._name

    def open(self) -> None:
        try:
            self._pool.open(wait=True, timeout=self._timeout_seconds)
        except (OperationalError, PoolTimeout) as error:
            raise DatabaseUnavailableError(
                f"{self._name} database pool could not be opened"
            ) from error

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Generator[DatabaseConnection, None, None]:
        try:
            with self._pool.connection(timeout=self._timeout_seconds) as connection:
                yield connection
        except (OperationalError, PoolTimeout) as error:
            raise DatabaseUnavailableError(
                f"{self._name} database connection is unavailable"
            ) from error

    def check(self) -> None:
        with self.connection() as connection:
            row = connection.execute("SELECT 1").fetchone()
            if row != (1,):
                raise DatabaseUnavailableError(
                    f"{self._name} database returned an invalid health response"
                )

    def __enter__(self) -> DatabasePool:
        self.open()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def create_planning_pool(settings: Settings) -> DatabasePool:
    dsn = settings.databases.planning_url
    if dsn is None:
        raise ConfigurationError("PLANNING_DATABASE_URL is required")
    return DatabasePool(dsn, name="planning")


def create_memory_pool(settings: Settings) -> DatabasePool:
    dsn = settings.databases.memory_url
    if dsn is None:
        raise ConfigurationError("MEMORY_DATABASE_URL is required")
    return DatabasePool(dsn, name="memory")


def fetch_one(
    connection: DatabaseConnection,
    query: QueryNoTemplate,
    params: Params | None,
    record_type: type[RecordT],
) -> RecordT | None:
    """Decode at most one query row into the requested record type."""
    # Localizing row_factory use here prevents Psycopg's tuple-row implementation
    # type from leaking through every repository interface.
    with connection.cursor(row_factory=class_row(record_type)) as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def fetch_all(
    connection: DatabaseConnection,
    query: QueryNoTemplate,
    params: Params | None,
    record_type: type[RecordT],
) -> tuple[RecordT, ...]:
    """Decode all bounded query rows into the requested record type."""
    with connection.cursor(row_factory=class_row(record_type)) as cursor:
        cursor.execute(query, params)
        return tuple(cursor.fetchall())
