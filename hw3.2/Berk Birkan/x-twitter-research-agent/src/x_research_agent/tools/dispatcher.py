from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from x_research_agent.config import Settings
from x_research_agent.db.repository import ResearchRepository
from x_research_agent.db.session import session_scope
from x_research_agent.domain.schemas import ResearchReport, ToolCallRecord
from x_research_agent.providers.xquik import XquikClient
from x_research_agent.security import redact

from .runtime import AgentRuntime


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(ge=1, le=50)
    cursor: str | None = None
    purpose: str = Field(min_length=1, max_length=300)


class GetPostArgs(BaseModel):
    post_id_or_url: str


class SaveSearchArgs(BaseModel):
    search_call_id: str


class FinalizeArgs(BaseModel):
    report: ResearchReport


class LoadResearchArgs(BaseModel):
    thread_id: str
    access_code: str


class DeleteResearchArgs(BaseModel):
    thread_id: str
    confirmed: bool


class ToolExecutionError(RuntimeError):
    pass


class ToolDispatcher:
    def __init__(
        self,
        *,
        settings: Settings,
        runtime: AgentRuntime,
        xquik: XquikClient,
        progress: Callable[[ToolCallRecord], None] | None = None,
    ):
        self.settings = settings
        self.runtime = runtime
        self.xquik = xquik
        self.progress = progress or (lambda _: None)

    async def execute(self, name: str, raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
        if self.runtime.cancelled.is_set():
            raise ToolExecutionError("Research was cancelled")
        try:
            arguments = (
                json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            )
        except json.JSONDecodeError as exc:
            raise ToolExecutionError("Tool arguments are not valid JSON") from exc
        sequence = len(self.runtime.logs) + 1
        started = time.perf_counter()
        record = ToolCallRecord(
            sequence=sequence,
            tool_name=name,
            arguments=redact(arguments),
            status="started",
        )
        self.progress(record)
        try:
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                raise ToolExecutionError(f"Unknown tool: {name}")
            result = await handler(arguments)
            record.status = "succeeded"
            record.result_summary = self._summarize(name, result)
            return result
        except (ValidationError, ValueError) as exc:
            record.status = "failed"
            record.result_summary = str(exc)
            raise ToolExecutionError(str(exc)) from exc
        except Exception as exc:
            record.status = "failed"
            record.result_summary = str(exc)
            raise
        finally:
            record.duration_ms = int((time.perf_counter() - started) * 1000)
            self.runtime.logs.append(record)
            self.progress(record)
            if self.runtime.db_thread_ready:
                with session_scope() as session:
                    repository = ResearchRepository(session)
                    persisted_count = self._add_pending_logs(repository)
                self.runtime.persisted_log_count = persisted_count

    async def _tool_search_x_posts(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = SearchArgs.model_validate(raw)
        if self.runtime.search_calls >= self.settings.max_search_calls:
            raise ToolExecutionError("Maximum Xquik search-call limit reached")
        if self.runtime.remaining_budget <= 0:
            raise ToolExecutionError("Research post budget is exhausted")
        key = f"{args.query.strip()}::{args.cursor or ''}"
        if key in self.runtime.searched_keys:
            raise ToolExecutionError("The same query and cursor cannot be requested twice")
        limit = min(args.limit, self.runtime.remaining_budget, 50)
        search_call_id = f"src_{uuid.uuid4().hex[:16]}"
        page = await self.xquik.search_posts(
            search_call_id=search_call_id,
            query=args.query,
            limit=limit,
            constraints=self.runtime.constraints,
            cursor=args.cursor,
        )
        self.runtime.search_calls += 1
        self.runtime.searched_keys.add(key)
        new_posts = [post for post in page.posts if post.id not in self.runtime.unique_post_ids]
        page.posts = new_posts[: self.runtime.remaining_budget]
        self.runtime.unique_post_ids.update(post.id for post in page.posts)
        self.runtime.search_cache[search_call_id] = page
        return page.model_dump(mode="json")

    async def _tool_get_x_post(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = GetPostArgs.model_validate(raw)
        if self.runtime.remaining_budget <= 0:
            raise ToolExecutionError("Research post budget is exhausted")
        post = await self.xquik.get_post(args.post_id_or_url)
        call_id = f"src_{uuid.uuid4().hex[:16]}"
        from x_research_agent.domain.schemas import SearchPage

        page = SearchPage(search_call_id=call_id, query=f"post:{post.id}", posts=[post])
        self.runtime.search_cache[call_id] = page
        self.runtime.unique_post_ids.add(post.id)
        return page.model_dump(mode="json")

    async def _tool_save_search_results(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = SaveSearchArgs.model_validate(raw)
        page = self.runtime.search_cache.get(args.search_call_id)
        if page is None:
            raise ToolExecutionError("Unknown or expired search_call_id")
        with session_scope() as session:
            repository = ResearchRepository(session)
            self._ensure_thread(repository)
            count = repository.save_search_results(
                thread_id=self.runtime.thread_id,
                search_call_id=page.search_call_id,
                query=page.query,
                posts=page.posts,
            )
            persisted_count = self._add_pending_logs(repository)
        self.runtime.db_thread_ready = True
        self.runtime.persisted_log_count = persisted_count
        self.runtime.saved_search_ids.add(page.search_call_id)
        return {"saved": count, "search_call_id": page.search_call_id}

    async def _tool_finalize_research(self, raw: dict[str, Any]) -> dict[str, Any]:
        self.runtime.finalize_attempts += 1
        if self.runtime.finalize_attempts > 2:
            raise ToolExecutionError("Only one report-schema correction attempt is allowed")
        args = FinalizeArgs.model_validate(raw)
        unsaved = set(self.runtime.search_cache) - self.runtime.saved_search_ids
        cited = args.report.cited_post_ids()
        unsaved_cited = {
            post.id
            for call_id in unsaved
            for post in self.runtime.search_cache[call_id].posts
            if post.id in cited
        }
        if unsaved_cited:
            raise ToolExecutionError(
                "Report cites results that were not saved; call save_search_results first"
            )
        with session_scope() as session:
            repository = ResearchRepository(session)
            self._ensure_thread(repository)
            row = repository.finalize_report(
                thread_id=self.runtime.thread_id,
                user_question=self.runtime.user_question,
                report=args.report,
                model_id=self.runtime.selected_model,
            )
            persisted_count = self._add_pending_logs(repository)
            version = row.version
        self.runtime.db_thread_ready = True
        self.runtime.persisted_log_count = persisted_count
        self.runtime.finalized = True
        self.runtime.latest_report = args.report.model_dump(mode="json")
        self.runtime.latest_version = version
        return {
            "status": "saved",
            "thread_id": self.runtime.thread_id,
            "access_code": self.runtime.access_code,
            "version": version,
            "report": self.runtime.latest_report,
        }

    async def _tool_get_saved_research(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = LoadResearchArgs.model_validate(raw)
        with session_scope() as session:
            thread = ResearchRepository(session).load_thread(
                thread_id=args.thread_id,
                access_code=args.access_code,
                session_id=self.runtime.session_id,
            )
            result = self._serialize_thread(thread)
            self.runtime.thread_id = thread.id
            self.runtime.access_code = args.access_code
            self.runtime.authorized_thread_ids.add(thread.id)
            self.runtime.db_thread_ready = True
            if result["reports"]:
                latest = result["reports"][-1]
                self.runtime.latest_report = latest["report"]
                self.runtime.latest_version = latest["version"]
                self.runtime.finalized = True
            return result

    async def _tool_list_session_research(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw:
            raise ToolExecutionError("list_session_research takes no arguments")
        with session_scope() as session:
            rows = ResearchRepository(session).list_session_threads(self.runtime.session_id)
            result = {
                "threads": [
                    {
                        "thread_id": row.id,
                        "title": row.title,
                        "completed": row.completed,
                        "last_activity_at": row.last_activity_at.isoformat(),
                    }
                    for row in rows
                ]
            }
            self.runtime.latest_report = self._management_report(
                short_answer=f"Bu anonim oturumda {len(result['threads'])} araştırma bulundu.",
                answer=json.dumps(result, ensure_ascii=False),
            )
            self.runtime.finalized = True
            return result

    async def _tool_delete_research(self, raw: dict[str, Any]) -> dict[str, Any]:
        args = DeleteResearchArgs.model_validate(raw)
        with session_scope() as session:
            ResearchRepository(session).delete_thread(
                thread_id=args.thread_id,
                session_id=self.runtime.session_id,
                confirmed=args.confirmed,
                access_code=(
                    self.runtime.access_code
                    if args.thread_id in self.runtime.authorized_thread_ids
                    else None
                ),
            )
        if args.thread_id == self.runtime.thread_id:
            self.runtime.db_thread_ready = False
            self.runtime.saved_search_ids.clear()
            self.runtime.search_cache.clear()
        self.runtime.latest_report = self._management_report(
            short_answer="Araştırma kalıcı olarak silindi.",
            answer=f"Silinen araştırma ID: {args.thread_id}",
        )
        self.runtime.finalized = True
        return {"status": "deleted", "thread_id": args.thread_id}

    def _ensure_thread(self, repository: ResearchRepository) -> None:
        repository.purge_expired(self.settings.research_retention_days)
        repository.ensure_thread(
            thread_id=self.runtime.thread_id,
            session_id=self.runtime.session_id,
            access_code=self.runtime.access_code,
            access_salt=self.runtime.access_salt,
            title=self.runtime.user_question[:240],
            user_question=self.runtime.user_question,
            constraints=self.runtime.constraints,
            selected_model=self.runtime.selected_model,
            authorized=self.runtime.thread_id in self.runtime.authorized_thread_ids,
        )

    def _add_pending_logs(self, repository: ResearchRepository) -> int:
        for record in self.runtime.logs[self.runtime.persisted_log_count :]:
            repository.add_tool_log(self.runtime.thread_id, record)
        return len(self.runtime.logs)

    @staticmethod
    def _serialize_thread(thread: Any) -> dict[str, Any]:
        return {
            "thread_id": thread.id,
            "title": thread.title,
            "user_question": thread.user_question,
            "reports": [
                {
                    "version": row.version,
                    "user_question": row.user_question,
                    "report": row.report,
                    "source_post_ids": row.source_post_ids,
                    "created_at": row.created_at.isoformat(),
                }
                for row in thread.reports
            ],
            "tool_logs": [
                {
                    "sequence": row.sequence,
                    "tool_name": row.tool_name,
                    "status": row.status,
                    "result_summary": row.result_summary,
                }
                for row in thread.tool_logs
            ],
        }

    @staticmethod
    def _summarize(name: str, result: dict[str, Any]) -> str:
        if name in {"search_x_posts", "get_x_post"}:
            return f"{len(result.get('posts', []))} unique public posts returned"
        if name == "save_search_results":
            return f"{result.get('saved', 0)} posts saved"
        if name == "finalize_research":
            return f"Research report v{result.get('version')} saved"
        if name == "list_session_research":
            return f"{len(result.get('threads', []))} threads returned"
        return str(result.get("status", "completed"))

    @staticmethod
    def _management_report(*, short_answer: str, answer: str) -> dict[str, Any]:
        return {
            "short_answer": short_answer,
            "sentiment_overview": "Bu işlem bir araştırma analizi değildir.",
            "positive_themes": [],
            "negative_themes": [],
            "answer_to_user_question": answer,
            "evidence": [],
            "limitations": [],
        }
