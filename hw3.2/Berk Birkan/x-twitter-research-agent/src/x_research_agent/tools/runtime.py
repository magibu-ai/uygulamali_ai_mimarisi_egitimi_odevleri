from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from threading import Event
from typing import Any

from x_research_agent.domain.schemas import ResearchConstraints, SearchPage, ToolCallRecord
from x_research_agent.security import generate_access_code, generate_thread_id


@dataclass
class AgentRuntime:
    session_id: str
    user_question: str
    selected_model: str
    constraints: ResearchConstraints
    thread_id: str = field(default_factory=generate_thread_id)
    access_code: str = field(default_factory=generate_access_code)
    access_salt: str = field(default_factory=lambda: secrets.token_hex(16))
    search_cache: dict[str, SearchPage] = field(default_factory=dict)
    searched_keys: set[str] = field(default_factory=set)
    saved_search_ids: set[str] = field(default_factory=set)
    unique_post_ids: set[str] = field(default_factory=set)
    search_calls: int = 0
    finalize_attempts: int = 0
    logs: list[ToolCallRecord] = field(default_factory=list)
    persisted_log_count: int = 0
    db_thread_ready: bool = False
    authorized_thread_ids: set[str] = field(default_factory=set)
    cancelled: Event = field(default_factory=Event)
    finalized: bool = False
    latest_report: dict[str, Any] | None = None
    latest_version: int | None = None

    @property
    def remaining_budget(self) -> int:
        return max(0, self.constraints.post_budget - len(self.unique_post_ids))
