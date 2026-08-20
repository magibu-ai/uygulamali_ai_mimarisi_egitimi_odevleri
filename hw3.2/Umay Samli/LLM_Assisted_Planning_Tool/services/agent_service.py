"""Ollama tool-call dongusunu ve guvenli arac yonlendirmesini yonetir."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from core.domain import ToolEvent
from tools.task_tools import TaskTools


class ChatClient(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mesajlari modele gonderip normalize edilmis yaniti dondurur."""

        ...


@dataclass
class AgentResult:
    content: str
    events: list[ToolEvent]


class AgentService:
    def __init__(
        self,
        client: ChatClient,
        task_tools: TaskTools,
        timezone: str = "Europe/Istanbul",
        max_tool_rounds: int = 6,
    ) -> None:
        """Agentin model, tool, saat dilimi ve dongu siniri bagimliliklarini kurar."""

        self.client = client
        self.task_tools = task_tools
        self.timezone = ZoneInfo(timezone)
        self.max_tool_rounds = max_tool_rounds

    def chat(
        self,
        user_message: str,
        session_id: str,
        history: list[dict[str, str]] | None = None,
    ) -> AgentResult:
        """Kullanici mesajini tool-call dongusunden gecirip yanit ve loglari uretir."""

        now = datetime.now(self.timezone)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._system_prompt(now),
            }
        ]
        for item in (history or [])[-12:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append(
                    {"role": item["role"], "content": str(item["content"])}
                )
        messages.append({"role": "user", "content": user_message})
        events: list[ToolEvent] = []

        for _ in range(self.max_tool_rounds):
            response = self.client.chat(messages, tools=self.task_tools.schemas)
            calls = response.get("tool_calls") or []
            if not calls:
                content = str(response.get("content") or "").strip()
                return AgentResult(
                    content=content or "Bu istek icin bir yanit uretemedim.",
                    events=events,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("content") or "",
                    "tool_calls": calls,
                }
            )
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {"_raw": arguments}
                result = self.task_tools.execute(name, arguments, session_id)
                event = ToolEvent(
                    tool=name,
                    arguments=arguments,
                    result=result,
                    timestamp=datetime.now(self.timezone),
                )
                events.append(event)
                print(
                    json.dumps(
                        {
                            "event": "tool_call",
                            **event.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return AgentResult(
            content=(
                "Guvenlik siniri nedeniyle arac cagrisi dongusunu durdurdum. "
                "Lutfen istegi daha acik yazarak yeniden deneyin."
            ),
            events=events,
        )

    @staticmethod
    def _system_prompt(now: datetime) -> str:
        """Modele verilecek halusinasyon ve tool kullanimi kurallarini olusturur."""

        return f"""
Sen Turkce konusan bir haftalik planlama asistanisin.
Su anki tarih ve saat: {now.isoformat()}.
Gorevler hakkindaki tek dogru kaynak sana verilen araclardir.

Kurallar:
- Yeni gorev icin baslik, deadline ve tahmini sure gerekir.
- Tahmini sure verilmediyse ASLA tahmin etme; kullaniciya sor.
- Oncelik verilmediyse medium kullanabilirsin.
- Gorev ekleme isteginde create_task kullan.
- Gorev listeleme veya gorevler hakkinda bilgi verme isteginde list_tasks kullan.
- Bir gorevi tamamlamak icin kimligi bilmiyorsan once list_tasks, sonra
  update_task_status kullan.
- Arac sonucu ok=false ise islemin basarili oldugunu soyleme.
- Veritabaninda bulunmayan gorev, kimlik, tarih veya durum uydurma.
- Kullaniciya kisa, acik ve Turkce cevap ver.
""".strip()
