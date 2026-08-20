"""LLM plan onerilerini deterministik kurallarla dogrular."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from database.database_layer import Database
from core.domain import (
    Availability,
    PlanAssignment,
    PlanBlock,
    PlanDraft,
    PlanProposal,
    Task,
    TaskStatus,
    UnscheduledTask,
)
from services.agent_service import ChatClient


class PlanningError(RuntimeError):
    """Plan olusturma veya dogrulama kullanici hatasi."""


class PlanningService:
    def __init__(
        self,
        database: Database,
        client: ChatClient,
        timezone: str = "Europe/Istanbul",
        max_attempts: int = 3,
    ) -> None:
        """Plan uretimi icin veritabani, model ve yeniden deneme ayarlarini saklar."""

        self.database = database
        self.client = client
        self.timezone = ZoneInfo(timezone)
        self.max_attempts = max_attempts

    def generate(self, session_id: str, availability: Availability) -> PlanDraft:
        """Aktif gorevlerden model destekli ve dogrulanmis bir haftalik taslak uretir."""

        tasks = self.database.list_tasks(session_id, status=TaskStatus.ACTIVE)
        if not tasks:
            raise PlanningError("Planlanacak aktif gorev bulunmuyor.")

        task_payload = [
            {
                "id": task.id,
                "title": task.title,
                "deadline": task.deadline.isoformat(),
                "estimated_minutes": task.estimated_minutes,
                "priority": task.priority.value,
            }
            for task in tasks
        ]
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Sen bir zaman planlama motorusun. Yalniz verilen gorev kimliklerini "
                    "kullan. Her gorevi ya assignments ya da unscheduled listesine tam bir "
                    "kez koy; kimlikleri degistirme ve ayni kimligi tekrarlama. Assignments "
                    "ve unscheduled icindeki toplam nesne sayisi task_count ile tam olarak "
                    "ayni olmali. Baslangiclar ISO 8601 ve saat dilimli olsun. Gorev "
                    "suresini, uygun gunleri, gunluk saat araligini ve deadline'i asma. "
                    "Yuksek oncelik ve yakin deadline'lari once planla. Markdown yazma."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "timezone": str(self.timezone),
                        "task_count": len(tasks),
                        "allowed_task_ids": [task.id for task in tasks],
                        "week_start": availability.week_start.isoformat(),
                        "weekdays": sorted(availability.weekdays),
                        "day_start": availability.day_start.isoformat(),
                        "day_end": availability.day_end.isoformat(),
                        "tasks": task_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        last_error = "Bilinmeyen planlama hatasi"
        for _ in range(self.max_attempts):
            response = self.client.chat(
                messages, format_schema=PlanProposal.model_json_schema()
            )
            content = str(response.get("content") or "")
            try:
                proposal = PlanProposal.model_validate_json(content)
                return self.validate(proposal, tasks, availability)
            except (ValidationError, PlanningError) as error:
                last_error = str(error)
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "Onceki taslak gecersizdi. Su hatalari duzeltip tum "
                                "gorevleri, allowed_task_ids listesindeki kimlikleri "
                                f"aynen ve yalniz birer kez kullanarak tekrar dondur: {last_error}"
                            ),
                        },
                    ]
                )
        print(
            json.dumps(
                {
                    "event": "planning_fallback",
                    "reason": last_error,
                    "task_ids": [task.id for task in tasks],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return self._fallback(tasks, availability)

    def validate(
        self,
        proposal: PlanProposal,
        tasks: list[Task],
        availability: Availability,
    ) -> PlanDraft:
        """Model onerilerini kimlik, zaman, deadline ve cakisma kurallariyla dogrular."""

        task_map = {task.id: task for task in tasks}
        assignment_ids = [item.task_id for item in proposal.assignments]
        unscheduled_ids = [item.task_id for item in proposal.unscheduled]
        all_ids = assignment_ids + unscheduled_ids

        if len(all_ids) != len(set(all_ids)):
            raise PlanningError("Bir gorev birden fazla kez belirtildi.")
        unknown = set(all_ids) - set(task_map)
        if unknown:
            raise PlanningError(f"Bilinmeyen gorev kimlikleri: {sorted(unknown)}")
        missing = set(task_map) - set(all_ids)
        if missing:
            raise PlanningError(f"Eksik gorev kimlikleri: {sorted(missing)}")

        week_start = availability.week_start.astimezone(self.timezone)
        week_end = week_start + timedelta(days=7)
        blocks: list[PlanBlock] = []
        for assignment in proposal.assignments:
            task = task_map[assignment.task_id]
            start = assignment.start.astimezone(self.timezone)
            end = start + timedelta(minutes=task.estimated_minutes)
            if not (week_start <= start < week_end):
                raise PlanningError(f"{task.id} numarali gorev secili hafta disinda.")
            if start.weekday() not in availability.weekdays:
                raise PlanningError(f"{task.id} numarali gorev uygun olmayan bir gunde.")
            if start.minute % 15 or start.second or start.microsecond:
                raise PlanningError(
                    f"{task.id} numarali gorev 15 dakikalik izgara uzerinde degil."
                )
            if (
                start.time().replace(tzinfo=None) < availability.day_start
                or end.time().replace(tzinfo=None) > availability.day_end
                or end.date() != start.date()
            ):
                raise PlanningError(f"{task.id} numarali gorev calisma saatleri disinda.")
            if end > task.deadline.astimezone(self.timezone):
                raise PlanningError(f"{task.id} numarali gorev deadline sonrasina tasiyor.")
            blocks.append(
                PlanBlock(
                    task_id=task.id,
                    title=task.title,
                    start=start,
                    end=end,
                )
            )

        blocks.sort(key=lambda block: block.start)
        for previous, current in zip(blocks, blocks[1:]):
            if current.start < previous.end:
                raise PlanningError(
                    f"{previous.task_id} ve {current.task_id} numarali gorevler cakisiyor."
                )
        return PlanDraft(
            blocks=blocks,
            unscheduled=proposal.unscheduled,
            week_start=week_start,
        )

    def _fallback(
        self, tasks: list[Task], availability: Availability
    ) -> PlanDraft:
        """Model taslagi gecersizse ayni girdilerle guvenli bir plan kurar."""

        priority_order = {"high": 0, "medium": 1, "low": 2}
        ordered_tasks = sorted(
            tasks,
            key=lambda task: (
                priority_order[task.priority.value],
                task.deadline,
                task.id,
            ),
        )
        week_start = availability.week_start.astimezone(self.timezone)
        assignments: list[PlanAssignment] = []
        unscheduled: list[UnscheduledTask] = []
        occupied: list[tuple[datetime, datetime]] = []

        for task in ordered_tasks:
            selected_start: datetime | None = None
            duration = timedelta(minutes=task.estimated_minutes)
            deadline = task.deadline.astimezone(self.timezone)
            for day_offset in range(7):
                current_date = (week_start + timedelta(days=day_offset)).date()
                if current_date.weekday() not in availability.weekdays:
                    continue
                candidate = datetime.combine(
                    current_date, availability.day_start, tzinfo=self.timezone
                )
                day_end = datetime.combine(
                    current_date, availability.day_end, tzinfo=self.timezone
                )
                while candidate + duration <= day_end:
                    candidate_end = candidate + duration
                    overlaps = any(
                        candidate < occupied_end and candidate_end > occupied_start
                        for occupied_start, occupied_end in occupied
                    )
                    if not overlaps and candidate_end <= deadline:
                        selected_start = candidate
                        break
                    candidate += timedelta(minutes=15)
                if selected_start is not None:
                    break

            if selected_start is None:
                unscheduled.append(
                    UnscheduledTask(
                        task_id=task.id,
                        reason="Deadline oncesinde uygun ve cakismayan zaman bulunamadi.",
                    )
                )
            else:
                assignments.append(
                    PlanAssignment(task_id=task.id, start=selected_start)
                )
                occupied.append((selected_start, selected_start + duration))

        return self.validate(
            PlanProposal(assignments=assignments, unscheduled=unscheduled),
            tasks,
            availability,
        )
