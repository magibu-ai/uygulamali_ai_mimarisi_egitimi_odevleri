from datetime import datetime
from zoneinfo import ZoneInfo

from database.database_layer import Database
from services.agent_service import AgentService
from tools.task_tools import TaskTools


class FakeChatClient:
    def __init__(self):
        """Agent testi icin once tool-call sonra nihai yanit sirasi hazirlar."""

        self.responses = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "create_task",
                            "arguments": {
                                "title": "Proje sunumu",
                                "deadline": "2026-08-07T17:00:00+03:00",
                                "estimated_minutes": 120,
                                "priority": "high",
                            },
                        },
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "Gorev veritabanina kaydedildi.",
                "tool_calls": [],
            },
        ]

    def chat(self, messages, tools=None, format_schema=None):
        """Hazirlanan model yanitlarini cagri sirasiyla dondurur."""

        return self.responses.pop(0)


def test_tools_reject_unknown_tool_and_isolate_sessions(tmp_path):
    """Izinsiz tool'un reddini ve tool seviyesinde oturum izolasyonunu dogrular."""

    database = Database(tmp_path / "planner.db")
    database.initialize()
    tools = TaskTools(database)

    assert tools.execute("drop_database", {}, "a")["ok"] is False
    created = tools.execute(
        "create_task",
        {
            "title": "Rapor",
            "deadline": "2026-08-07",
            "estimated_minutes": 60,
            "priority": "medium",
        },
        "a",
    )
    assert created["ok"] is True
    assert tools.execute("list_tasks", {}, "b")["count"] == 0


def test_agent_executes_and_logs_tool_call(tmp_path):
    """Agentin tool-call'i calistirip sonucu ve olayi kaydettigini dogrular."""

    database = Database(tmp_path / "planner.db")
    database.initialize()
    service = AgentService(FakeChatClient(), TaskTools(database))

    result = service.chat(
        "Cuma 17:00'ye kadar iki saatlik sunum ekle.",
        "session-a",
    )

    assert result.content == "Gorev veritabanina kaydedildi."
    assert result.events[0].tool == "create_task"
    assert result.events[0].result["ok"] is True
    assert database.list_tasks("session-a")[0].title == "Proje sunumu"


def test_missing_duration_is_rejected_by_validation(tmp_path):
    """Tahmini suresi olmayan gorevin kaydedilmeden reddedildigini dogrular."""

    database = Database(tmp_path / "planner.db")
    database.initialize()
    result = TaskTools(database).execute(
        "create_task",
        {
            "title": "Eksik gorev",
            "deadline": datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(),
            "priority": "medium",
        },
        "session-a",
    )
    assert result["ok"] is False
    assert database.list_tasks("session-a") == []
