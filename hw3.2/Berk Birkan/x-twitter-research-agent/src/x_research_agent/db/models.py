from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ResearchThread(Base):
    __tablename__ = "research_threads"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(80), index=True)
    access_code_hash: Mapped[str] = mapped_column(String(128))
    access_code_salt: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(240))
    user_question: Mapped[str] = mapped_column(Text)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON)
    selected_model: Mapped[str] = mapped_column(String(240))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    searches: Mapped[list[SearchRun]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )
    reports: Mapped[list[ReportVersion]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="ReportVersion.version"
    )
    tool_logs: Mapped[list[ToolLog]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="ToolLog.sequence"
    )


class XPostRecord(Base):
    __tablename__ = "x_posts"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    author_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    author_username: Mapped[str] = mapped_column(String(100))
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    like_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repost_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reply_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    view_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class SearchRun(Base):
    __tablename__ = "search_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", "search_call_id", name="uq_thread_search_call"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("research_threads.id", ondelete="CASCADE"), index=True
    )
    search_call_id: Mapped[str] = mapped_column(String(100))
    query: Mapped[str] = mapped_column(Text)
    post_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    thread: Mapped[ResearchThread] = relationship(back_populates="searches")
    posts: Mapped[list[SearchPost]] = relationship(cascade="all, delete-orphan")


class SearchPost(Base):
    __tablename__ = "search_posts"

    search_run_id: Mapped[int] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"), primary_key=True
    )
    post_id: Mapped[str] = mapped_column(
        ForeignKey("x_posts.id", ondelete="CASCADE"), primary_key=True
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("thread_id", "version", name="uq_thread_report_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("research_threads.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    user_question: Mapped[str] = mapped_column(Text)
    report: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_post_ids: Mapped[list[str]] = mapped_column(JSON)
    model_id: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    thread: Mapped[ResearchThread] = relationship(back_populates="reports")


class ToolLog(Base):
    __tablename__ = "tool_logs"
    __table_args__ = (Index("ix_tool_logs_thread_sequence", "thread_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("research_threads.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    thread: Mapped[ResearchThread] = relationship(back_populates="tool_logs")
