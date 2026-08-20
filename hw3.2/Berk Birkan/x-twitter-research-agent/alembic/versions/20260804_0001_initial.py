"""Initial research schema."""

import sqlalchemy as sa

from alembic import op

revision = "20260804_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_threads",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("session_id", sa.String(80), nullable=False),
        sa.Column("access_code_hash", sa.String(128), nullable=False),
        sa.Column("access_code_salt", sa.String(64), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("user_question", sa.Text, nullable=False),
        sa.Column("constraints", sa.JSON, nullable=False),
        sa.Column("selected_model", sa.String(240), nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_threads_session_id", "research_threads", ["session_id"])
    op.create_index(
        "ix_research_threads_last_activity_at", "research_threads", ["last_activity_at"]
    )
    op.create_table(
        "x_posts",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("author_id", sa.String(100)),
        sa.Column("author_username", sa.String(100), nullable=False),
        sa.Column("author_name", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("language", sa.String(16)),
        sa.Column("like_count", sa.Integer),
        sa.Column("repost_count", sa.Integer),
        sa.Column("reply_count", sa.Integer),
        sa.Column("view_count", sa.Integer),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "search_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "thread_id",
            sa.String(80),
            sa.ForeignKey("research_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("search_call_id", sa.String(100), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("post_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("thread_id", "search_call_id", name="uq_thread_search_call"),
    )
    op.create_index("ix_search_runs_thread_id", "search_runs", ["thread_id"])
    op.create_table(
        "search_posts",
        sa.Column(
            "search_run_id",
            sa.Integer,
            sa.ForeignKey("search_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "post_id",
            sa.String(100),
            sa.ForeignKey("x_posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "report_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "thread_id",
            sa.String(80),
            sa.ForeignKey("research_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("user_question", sa.Text, nullable=False),
        sa.Column("report", sa.JSON, nullable=False),
        sa.Column("source_post_ids", sa.JSON, nullable=False),
        sa.Column("model_id", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("thread_id", "version", name="uq_thread_report_version"),
    )
    op.create_index("ix_report_versions_thread_id", "report_versions", ["thread_id"])
    op.create_table(
        "tool_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "thread_id",
            sa.String(80),
            sa.ForeignKey("research_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("arguments", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_summary", sa.Text),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_logs_thread_id", "tool_logs", ["thread_id"])
    op.create_index("ix_tool_logs_thread_sequence", "tool_logs", ["thread_id", "sequence"])


def downgrade() -> None:
    op.drop_table("tool_logs")
    op.drop_table("report_versions")
    op.drop_table("search_posts")
    op.drop_table("search_runs")
    op.drop_table("x_posts")
    op.drop_table("research_threads")
