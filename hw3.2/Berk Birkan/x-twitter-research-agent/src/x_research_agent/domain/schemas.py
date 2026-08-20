from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SortMode(str, Enum):
    RELEVANCE = "relevance"
    LATEST = "latest"
    TOP = "top"


class ResearchConstraints(BaseModel):
    language: str | None = Field(default=None, max_length=12)
    start_date: date | None = None
    end_date: date | None = None
    include_retweets: bool = False
    sort: SortMode = SortMode.RELEVANCE
    post_budget: int = Field(default=50, ge=10, le=200)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> ResearchConstraints:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date cannot be later than end_date")
        return self


class XAuthor(BaseModel):
    id: str | None = None
    username: str
    name: str | None = None


class XPost(BaseModel):
    id: str
    text: str
    author: XAuthor
    created_at: datetime | None = None
    language: str | None = None
    like_count: int | None = None
    repost_count: int | None = None
    reply_count: int | None = None
    view_count: int | None = None
    url: str

    @field_validator("id")
    @classmethod
    def id_is_opaque_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("post id cannot be empty")
        return value


class SearchPage(BaseModel):
    search_call_id: str
    query: str
    posts: list[XPost]
    has_more: bool = False
    next_cursor: str | None = None


class Evidence(BaseModel):
    post_id: str
    claim: str = Field(min_length=1, max_length=1000)


class Theme(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    post_ids: list[str] = Field(min_length=1)


class ResearchReport(BaseModel):
    short_answer: str = Field(min_length=1, max_length=4000)
    sentiment_overview: str = Field(min_length=1, max_length=3000)
    positive_themes: list[Theme] = Field(default_factory=list)
    negative_themes: list[Theme] = Field(default_factory=list)
    answer_to_user_question: str = Field(min_length=1, max_length=8000)
    evidence: list[Evidence] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    def cited_post_ids(self) -> set[str]:
        ids = {item.post_id for item in self.evidence}
        for theme in self.positive_themes + self.negative_themes:
            ids.update(theme.post_ids)
        return ids


class ToolCallRecord(BaseModel):
    sequence: int
    tool_name: str
    arguments: dict[str, Any]
    status: Literal["started", "succeeded", "failed", "cancelled"]
    result_summary: str | None = None
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelInfo(BaseModel):
    id: str
    name: str
    context_length: int | None = None
    prompt_price: str | None = None
    completion_price: str | None = None
    provider: str
    supports_structured_output: bool = False
    supported_parameters: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
