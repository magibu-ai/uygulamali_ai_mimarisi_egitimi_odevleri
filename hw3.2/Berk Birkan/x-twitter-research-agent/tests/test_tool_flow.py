from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from x_research_agent.config import Settings
from x_research_agent.db import session as db_session
from x_research_agent.db.base import Base
from x_research_agent.db.models import ReportVersion, ResearchThread, SearchRun, ToolLog
from x_research_agent.db.repository import ResearchRepository
from x_research_agent.domain.schemas import (
    ResearchConstraints,
    SearchPage,
    XAuthor,
    XPost,
)
from x_research_agent.tools.dispatcher import ToolDispatcher
from x_research_agent.tools.runtime import AgentRuntime


class FakeXquik:
    async def search_posts(self, *, search_call_id, query, limit, constraints, cursor=None):
        post = XPost(
            id="123456789",
            text="The pricing page is confusing.",
            author=XAuthor(id="42", username="alice", name="Alice"),
            created_at=datetime.now(timezone.utc),
            like_count=5,
            url="https://x.com/alice/status/123456789",
        )
        return SearchPage(
            search_call_id=search_call_id,
            query=query,
            posts=[post][:limit],
            has_more=False,
        )


@pytest.mark.asyncio
async def test_model_driven_search_save_finalize_flow(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", test_session_factory)

    runtime = AgentRuntime(
        session_id="ses_test",
        user_question="Fiyat şikâyetleri neler?",
        selected_model="vendor/model",
        constraints=ResearchConstraints(post_budget=50),
    )
    dispatcher = ToolDispatcher(
        settings=Settings(database_url="sqlite+pysqlite:///:memory:"),
        runtime=runtime,
        xquik=FakeXquik(),
    )

    search = await dispatcher.execute(
        "search_x_posts",
        {"query": "OpenRouter pricing", "limit": 20, "purpose": "Fiyat görüşlerini bul"},
    )
    await dispatcher.execute("save_search_results", {"search_call_id": search["search_call_id"]})
    final = await dispatcher.execute(
        "finalize_research",
        {
            "report": {
                "short_answer": "Fiyatlandırma sayfası kafa karıştırıcı bulunuyor.",
                "sentiment_overview": "Örnek gönderi eleştirel bir görüş içeriyor.",
                "positive_themes": [],
                "negative_themes": [
                    {
                        "title": "Fiyat açıklığı",
                        "summary": "Kullanıcı fiyat sayfasını anlaşılması zor buluyor.",
                        "post_ids": ["123456789"],
                    }
                ],
                "answer_to_user_question": "Bulunan şikâyet fiyat sunumunun açıklığıyla ilgili.",
                "evidence": [{"post_id": "123456789", "claim": "Fiyat sayfası kafa karıştırıcı"}],
                "limitations": ["Yalnızca bir örnek gönderi bulundu."],
            }
        },
    )

    assert final["status"] == "saved"
    assert runtime.finalized is True
    with test_session_factory() as session:
        assert len(session.scalars(select(SearchRun)).all()) == 1
        assert len(session.scalars(select(ReportVersion)).all()) == 1
        logs = session.scalars(select(ToolLog).order_by(ToolLog.sequence)).all()
        assert [log.tool_name for log in logs] == [
            "search_x_posts",
            "save_search_results",
            "finalize_research",
        ]


@pytest.mark.asyncio
async def test_failed_initial_save_does_not_mark_rolled_back_thread_ready(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", test_session_factory)

    runtime = AgentRuntime(
        session_id="ses_rollback",
        user_question="Başarısız kayıt",
        selected_model="vendor/model",
        constraints=ResearchConstraints(post_budget=50),
    )
    dispatcher = ToolDispatcher(
        settings=Settings(database_url="sqlite+pysqlite:///:memory:"),
        runtime=runtime,
        xquik=FakeXquik(),
    )
    search = await dispatcher.execute(
        "search_x_posts",
        {"query": "rollback", "limit": 1, "purpose": "Transaction testi"},
    )

    def fail_save(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(ResearchRepository, "save_search_results", fail_save)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        await dispatcher.execute(
            "save_search_results", {"search_call_id": search["search_call_id"]}
        )

    assert runtime.db_thread_ready is False
    assert runtime.persisted_log_count == 0
    with test_session_factory() as session:
        assert session.get(ResearchThread, runtime.thread_id) is None
        assert session.scalars(select(ToolLog)).all() == []
