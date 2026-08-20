"""Uygulamanin paylasilan veri modelleri."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    deadline: datetime
    estimated_minutes: int = Field(ge=15, le=720, multiple_of=15)
    priority: Priority = Priority.MEDIUM

    @field_validator("deadline")
    @classmethod
    def deadline_must_have_timezone(cls, value: datetime) -> datetime:
        """Deadline degerinin acik bir saat dilimi tasidigini dogrular."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deadline saat dilimi icermelidir")
        return value


class Task(BaseModel):
    id: int
    session_id: str
    title: str
    deadline: datetime
    estimated_minutes: int
    priority: Priority
    status: TaskStatus
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    created_at: datetime


class Availability(BaseModel):
    week_start: datetime
    weekdays: set[int] = Field(min_length=1)
    day_start: time
    day_end: time

    @field_validator("week_start")
    @classmethod
    def week_must_have_timezone(cls, value: datetime) -> datetime:
        """Hafta baslangicinin acik bir saat dilimi tasidigini dogrular."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("hafta baslangici saat dilimi icermelidir")
        return value

    @field_validator("weekdays")
    @classmethod
    def weekdays_are_valid(cls, value: set[int]) -> set[int]:
        """Secilen gunlerin Python hafta gunu araliginda oldugunu dogrular."""

        if not value.issubset(set(range(7))):
            raise ValueError("hafta gunleri 0 ile 6 arasinda olmalidir")
        return value

    @model_validator(mode="after")
    def working_window_is_valid(self) -> "Availability":
        """Calisma saatlerini ve haftanin Pazartesi basladigini dogrular."""

        if self.day_end <= self.day_start:
            raise ValueError("gunluk bitis saati baslangictan sonra olmalidir")
        if self.week_start.weekday() != 0:
            raise ValueError("hafta Pazartesi gunu baslamalidir")
        return self


class PlanAssignment(BaseModel):
    task_id: int
    start: datetime

    @field_validator("start")
    @classmethod
    def start_must_have_timezone(cls, value: datetime) -> datetime:
        """Planlanan baslangicin acik bir saat dilimi tasidigini dogrular."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan baslangici saat dilimi icermelidir")
        return value


class UnscheduledTask(BaseModel):
    task_id: int
    reason: str = Field(min_length=1, max_length=300)


class PlanProposal(BaseModel):
    assignments: list[PlanAssignment]
    unscheduled: list[UnscheduledTask]


class PlanBlock(BaseModel):
    task_id: int
    title: str
    start: datetime
    end: datetime


class PlanDraft(BaseModel):
    blocks: list[PlanBlock]
    unscheduled: list[UnscheduledTask]
    week_start: datetime


class ToolEvent(BaseModel):
    tool: str
    arguments: dict[str, object]
    result: dict[str, object]
    timestamp: datetime
