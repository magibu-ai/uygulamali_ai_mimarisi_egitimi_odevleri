"""Parametreli sorgular kullanan SQLite veri erisim katmani."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from core.domain import PlanDraft, Task, TaskCreate, TaskStatus


class DatabaseError(RuntimeError):
    """Kullaniciya guvenli bicimde aktarilabilecek veri katmani hatasi."""


class Database:
    def __init__(self, path: str | Path = "data/planner.db") -> None:
        """Veritabani yolunu hazirlar ve ust dizini gerekirse olusturur."""

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """SQLite baglantisini ayarlayip kullanim sonunda guvenle kapatir."""

        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Gorev tablosunu ve sorgu indeksini mevcut degilse olusturur."""

        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL,
                    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'completed')),
                    scheduled_start TEXT,
                    scheduled_end TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_session_status "
                "ON tasks(session_id, status)"
            )
            connection.commit()

    def create_task(self, session_id: str, payload: TaskCreate) -> Task:
        """Dogrulanmis bir gorevi oturuma kaydedip olusan kaydi dondurur."""

        created_at = datetime.now().astimezone()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (
                    session_id, title, deadline, estimated_minutes,
                    priority, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    session_id,
                    payload.title,
                    payload.deadline.isoformat(),
                    payload.estimated_minutes,
                    payload.priority.value,
                    created_at.isoformat(),
                ),
            )
            connection.commit()
            task_id = int(cursor.lastrowid or 0)
        task = self.get_task(session_id, task_id)
        if task is None:
            raise DatabaseError("Olusturulan gorev yeniden okunamadi")
        return task

    def get_task(self, session_id: str, task_id: int) -> Task | None:
        """Kimligi verilen gorevi yalnizca ilgili oturum icinden getirir."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE session_id = ? AND id = ?",
                (session_id, task_id),
            ).fetchone()
        return self._to_task(row) if row else None

    def list_tasks(
        self,
        session_id: str,
        status: TaskStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Task]:
        """Oturum gorevlerini durum ve deadline araligina gore listeler."""

        clauses = ["session_id = ?"]
        parameters: list[object] = [session_id]
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)
        if date_from is not None:
            clauses.append("deadline >= ?")
            parameters.append(date_from.isoformat())
        if date_to is not None:
            clauses.append("deadline <= ?")
            parameters.append(date_to.isoformat())
        query = "SELECT * FROM tasks WHERE " + " AND ".join(clauses)
        query += " ORDER BY deadline ASC, id ASC"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_task(row) for row in rows]

    def update_task_status(
        self, session_id: str, task_id: int, status: TaskStatus
    ) -> Task:
        """Mevcut bir gorevin durumunu degistirip guncel kaydi dondurur."""

        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET status = ?,
                    scheduled_start = CASE WHEN ? = 'completed' THEN scheduled_start ELSE NULL END,
                    scheduled_end = CASE WHEN ? = 'completed' THEN scheduled_end ELSE NULL END
                WHERE session_id = ? AND id = ?
                """,
                (status.value, status.value, status.value, session_id, task_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError("Bu oturumda belirtilen gorev bulunamadi")
            connection.commit()
        task = self.get_task(session_id, task_id)
        if task is None:
            raise DatabaseError("Guncellenen gorev yeniden okunamadi")
        return task

    def save_plan(self, session_id: str, draft: PlanDraft) -> list[Task]:
        """Dogrulanmis plan bloklarini tek transaction ile gorevlere kaydeder."""

        if not draft.blocks:
            return []
        task_ids = [block.task_id for block in draft.blocks]
        if len(task_ids) != len(set(task_ids)):
            raise DatabaseError("Bir gorev planda birden fazla kez bulunuyor")

        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                placeholders = ",".join("?" for _ in task_ids)
                rows = connection.execute(
                    f"SELECT id, status FROM tasks WHERE session_id = ? "
                    f"AND id IN ({placeholders})",
                    [session_id, *task_ids],
                ).fetchall()
                if len(rows) != len(task_ids):
                    raise DatabaseError("Plandaki gorevlerden biri bu oturuma ait degil")
                if any(row["status"] != TaskStatus.ACTIVE.value for row in rows):
                    raise DatabaseError("Tamamlanmis gorev planlanamaz")
                for block in draft.blocks:
                    connection.execute(
                        """
                        UPDATE tasks SET scheduled_start = ?, scheduled_end = ?
                        WHERE session_id = ? AND id = ?
                        """,
                        (
                            block.start.isoformat(),
                            block.end.isoformat(),
                            session_id,
                            block.task_id,
                        ),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        saved: list[Task] = []
        for task_id in task_ids:
            task = self.get_task(session_id, task_id)
            if task is not None:
                saved.append(task)
        return saved

    @staticmethod
    def _to_task(row: sqlite3.Row) -> Task:
        """SQLite satirini uygulamanin tipli Task modeline donusturur."""

        return Task(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            deadline=datetime.fromisoformat(row["deadline"]),
            estimated_minutes=row["estimated_minutes"],
            priority=row["priority"],
            status=row["status"],
            scheduled_start=(
                datetime.fromisoformat(row["scheduled_start"])
                if row["scheduled_start"]
                else None
            ),
            scheduled_end=(
                datetime.fromisoformat(row["scheduled_end"])
                if row["scheduled_end"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
