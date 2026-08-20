from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from x_research_agent.db.base import Base
from x_research_agent.db.repository import AccessDeniedError, RepositoryError, ResearchRepository
from x_research_agent.domain.schemas import (
    Evidence,
    ResearchConstraints,
    ResearchReport,
    XAuthor,
    XPost,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_report(post_id: str) -> ResearchReport:
    return ResearchReport(
        short_answer="Kısa yanıt",
        sentiment_overview="Karışık görüşler var.",
        answer_to_user_question="Kanıtlar fiyat tartışmasına işaret ediyor.",
        evidence=[Evidence(post_id=post_id, claim="Fiyat tartışılıyor")],
        limitations=["Küçük örneklem"],
    )


def test_report_can_only_cite_saved_posts(session: Session):
    repo = ResearchRepository(session)
    repo.ensure_thread(
        thread_id="thr_one",
        session_id="ses_one",
        access_code="ABCD-1234",
        access_salt="salt",
        title="Test",
        user_question="Fiyatlar nasıl?",
        constraints=ResearchConstraints(),
        selected_model="vendor/model",
    )
    post = XPost(
        id="123456",
        text="Pricing is confusing",
        author=XAuthor(username="alice"),
        created_at=datetime.now(timezone.utc),
        url="https://x.com/alice/status/123456",
    )
    repo.save_search_results(
        thread_id="thr_one", search_call_id="src_one", query="pricing", posts=[post]
    )

    row = repo.finalize_report(
        thread_id="thr_one",
        user_question="Fiyatlar nasıl?",
        report=make_report("123456"),
        model_id="vendor/model",
    )
    assert row.version == 1

    with pytest.raises(RepositoryError, match="unknown post IDs"):
        repo.finalize_report(
            thread_id="thr_one",
            user_question="Uydurma kaynak",
            report=make_report("999999"),
            model_id="vendor/model",
        )


def test_access_code_or_session_is_required(session: Session):
    repo = ResearchRepository(session)
    repo.ensure_thread(
        thread_id="thr_secure",
        session_id="ses_owner",
        access_code="ABCD-1234",
        access_salt="salt",
        title="Secure",
        user_question="Question",
        constraints=ResearchConstraints(),
        selected_model="vendor/model",
    )
    session.commit()

    assert repo.load_thread(thread_id="thr_secure", access_code="abcd-1234").id == "thr_secure"
    assert repo.load_thread(thread_id="thr_secure", session_id="ses_owner").id == "thr_secure"
    with pytest.raises(AccessDeniedError):
        repo.load_thread(thread_id="thr_secure", access_code="WRONG")
