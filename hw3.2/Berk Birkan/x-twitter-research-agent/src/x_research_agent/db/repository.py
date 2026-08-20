from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from x_research_agent.domain.schemas import (
    ResearchConstraints,
    ResearchReport,
    ToolCallRecord,
    XPost,
)
from x_research_agent.security import hash_access_code, verify_access_code

from .models import (
    ReportVersion,
    ResearchThread,
    SearchPost,
    SearchRun,
    ToolLog,
    XPostRecord,
)


class RepositoryError(RuntimeError):
    pass


class AccessDeniedError(RepositoryError):
    pass


class ResearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def ensure_thread(
        self,
        *,
        thread_id: str,
        session_id: str,
        access_code: str,
        access_salt: str,
        title: str,
        user_question: str,
        constraints: ResearchConstraints,
        selected_model: str,
        authorized: bool = False,
    ) -> ResearchThread:
        thread = self.session.get(ResearchThread, thread_id)
        if thread:
            if thread.session_id != session_id and not authorized:
                raise AccessDeniedError("Research thread does not belong to this session")
            return thread
        thread = ResearchThread(
            id=thread_id,
            session_id=session_id,
            access_code_hash=hash_access_code(access_code, access_salt),
            access_code_salt=access_salt,
            title=title[:240],
            user_question=user_question,
            constraints=constraints.model_dump(mode="json"),
            selected_model=selected_model,
        )
        self.session.add(thread)
        self.session.flush()
        return thread

    def save_search_results(
        self,
        *,
        thread_id: str,
        search_call_id: str,
        query: str,
        posts: list[XPost],
    ) -> int:
        existing = self.session.scalar(
            select(SearchRun).where(
                SearchRun.thread_id == thread_id,
                SearchRun.search_call_id == search_call_id,
            )
        )
        if existing:
            return existing.post_count

        run = SearchRun(
            thread_id=thread_id,
            search_call_id=search_call_id,
            query=query,
            post_count=len(posts),
        )
        self.session.add(run)
        self.session.flush()
        post_ids: list[str] = []
        for post in posts:
            record = self.session.get(XPostRecord, post.id)
            values = post.model_dump()
            if record is None:
                record = XPostRecord(
                    id=post.id,
                    text=post.text,
                    author_id=post.author.id,
                    author_username=post.author.username,
                    author_name=post.author.name,
                    created_at=post.created_at,
                    language=post.language,
                    like_count=post.like_count,
                    repost_count=post.repost_count,
                    reply_count=post.reply_count,
                    view_count=post.view_count,
                    url=post.url,
                )
                self.session.add(record)
            else:
                record.text = values["text"]
                record.like_count = values["like_count"]
                record.repost_count = values["repost_count"]
                record.reply_count = values["reply_count"]
                record.view_count = values["view_count"]
            post_ids.append(post.id)

        # Persist parent post rows before their search-post associations. This is
        # deliberately explicit because later session.get() calls may autoflush.
        self.session.flush()
        for post_id in dict.fromkeys(post_ids):
            self.session.add(SearchPost(search_run_id=run.id, post_id=post_id))
        self._touch(thread_id)
        return len(posts)

    def available_post_ids(self, thread_id: str) -> set[str]:
        return set(
            self.session.scalars(
                select(SearchPost.post_id)
                .join(SearchRun, SearchRun.id == SearchPost.search_run_id)
                .where(SearchRun.thread_id == thread_id)
            )
        )

    def finalize_report(
        self,
        *,
        thread_id: str,
        user_question: str,
        report: ResearchReport,
        model_id: str,
    ) -> ReportVersion:
        available = self.available_post_ids(thread_id)
        cited = report.cited_post_ids()
        unknown = cited - available
        if unknown:
            raise RepositoryError(f"Report cites unknown post IDs: {sorted(unknown)}")
        version = (
            self.session.scalar(
                select(func.coalesce(func.max(ReportVersion.version), 0)).where(
                    ReportVersion.thread_id == thread_id
                )
            )
            or 0
        ) + 1
        row = ReportVersion(
            thread_id=thread_id,
            version=version,
            user_question=user_question,
            report=report.model_dump(mode="json"),
            source_post_ids=sorted(cited),
            model_id=model_id,
        )
        self.session.add(row)
        thread = self.session.get(ResearchThread, thread_id)
        if thread is None:
            raise RepositoryError("Research thread not found")
        thread.completed = True
        thread.last_activity_at = datetime.now(timezone.utc)
        self.session.flush()
        return row

    def load_thread(
        self, *, thread_id: str, access_code: str | None = None, session_id: str | None = None
    ) -> ResearchThread:
        thread = self.session.scalar(
            select(ResearchThread)
            .options(
                selectinload(ResearchThread.reports),
                selectinload(ResearchThread.searches),
                selectinload(ResearchThread.tool_logs),
            )
            .where(ResearchThread.id == thread_id)
        )
        if thread is None:
            raise RepositoryError("Research thread not found or expired")
        session_matches = session_id is not None and thread.session_id == session_id
        code_matches = access_code is not None and verify_access_code(
            access_code, thread.access_code_salt, thread.access_code_hash
        )
        if not (session_matches or code_matches):
            raise AccessDeniedError("Invalid research ID or access code")
        thread.last_activity_at = datetime.now(timezone.utc)
        return thread

    def list_session_threads(self, session_id: str) -> list[ResearchThread]:
        return list(
            self.session.scalars(
                select(ResearchThread)
                .where(ResearchThread.session_id == session_id)
                .order_by(ResearchThread.last_activity_at.desc())
                .limit(50)
            )
        )

    def delete_thread(
        self,
        *,
        thread_id: str,
        session_id: str,
        confirmed: bool,
        access_code: str | None = None,
    ) -> None:
        if not confirmed:
            raise RepositoryError("Deletion requires explicit confirmation")
        thread = self.session.get(ResearchThread, thread_id)
        code_matches = bool(
            thread
            and access_code
            and verify_access_code(access_code, thread.access_code_salt, thread.access_code_hash)
        )
        if thread is None or (thread.session_id != session_id and not code_matches):
            raise AccessDeniedError("Research thread not found in this session")
        self.session.delete(thread)
        self.session.flush()
        self._delete_orphan_posts()

    def add_tool_log(self, thread_id: str, record: ToolCallRecord) -> None:
        self.session.add(
            ToolLog(
                thread_id=thread_id,
                sequence=record.sequence,
                tool_name=record.tool_name,
                arguments=record.arguments,
                status=record.status,
                result_summary=record.result_summary,
                duration_ms=record.duration_ms,
                created_at=record.created_at,
            )
        )

    def purge_expired(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        ids = list(
            self.session.scalars(
                select(ResearchThread.id).where(ResearchThread.last_activity_at < cutoff)
            )
        )
        if ids:
            self.session.execute(delete(ResearchThread).where(ResearchThread.id.in_(ids)))
            self.session.flush()
            self._delete_orphan_posts()
        return len(ids)

    def _delete_orphan_posts(self) -> None:
        referenced = select(SearchPost.post_id)
        self.session.execute(delete(XPostRecord).where(XPostRecord.id.not_in(referenced)))

    def _touch(self, thread_id: str) -> None:
        thread = self.session.get(ResearchThread, thread_id)
        if thread:
            thread.last_activity_at = datetime.now(timezone.utc)
