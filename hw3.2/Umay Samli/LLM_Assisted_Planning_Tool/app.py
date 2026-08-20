"""Gradio tabanli haftalik planlama arayuzu."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import gradio as gr
from dotenv import load_dotenv

from core.config import Settings
from core.domain import Availability, PlanDraft, Task
from database.database_layer import Database
from llm.ollama_client import OllamaClient
from services.agent_service import AgentService
from services.pdf_service import PDFService
from services.planning_service import PlanningError, PlanningService
from tools.task_tools import TaskTools

load_dotenv()

DAY_LABELS = {
    "Pazartesi": 0,
    "Sali": 1,
    "Carsamba": 2,
    "Persembe": 3,
    "Cuma": 4,
    "Cumartesi": 5,
    "Pazar": 6,
}
DAY_NAMES = {number: label for label, number in DAY_LABELS.items()}
TASK_HEADERS = [
    "ID", "Gorev", "Deadline", "Sure (dk)", "Oncelik", "Durum",
    "Planlanan baslangic",
]
EXAMPLE_PROMPTS = [
    [
        "Yarin saat 17:00'ye kadar tamamlanmasi gereken 90 dakikalik "
        "rapor yazma gorevi ekle, onceligi yuksek."
    ],
    [
        "Bu cuma saat 16:00'ya kadar 60 dakikalik haftalik toplanti "
        "hazirligi gorevi ekle, onceligi orta."
    ],
    ["Aktif gorevlerimi deadline sirasiyla listele."],
    ["1 numarali gorevi tamamlandi olarak isaretle."],
]
pdf_service = PDFService()
PLAN_HEADERS = ["Gun", "Baslangic", "Bitis", "Gorev", "Task ID", "Durum"]

settings = Settings.from_env()
database = Database(settings.database_path)
database.initialize()
ollama_client = OllamaClient(
    model=settings.ollama_model,
    host=settings.ollama_base_url,
    timeout=settings.ollama_timeout,
)
task_tools = TaskTools(database, settings.timezone)
agent_service = AgentService(ollama_client, task_tools, settings.timezone)
planning_service = PlanningService(database, ollama_client, settings.timezone)


def _task_rows(session_id: str) -> list[list[Any]]:
    """Oturum gorevlerini Gradio tablosunun bekledigi satirlara donusturur."""

    tasks = database.list_tasks(session_id)
    return [
        [
            task.id,
            task.title,
            task.deadline.strftime("%d.%m.%Y %H:%M"),
            task.estimated_minutes,
            {"low": "Dusuk", "medium": "Orta", "high": "Yuksek"}[
                task.priority.value
            ],
            "Aktif" if task.status.value == "active" else "Tamamlandi",
            task.scheduled_start.strftime("%d.%m.%Y %H:%M")
            if task.scheduled_start
            else "-",
        ]
        for task in tasks
    ]


def _plan_rows(draft: PlanDraft, tasks: list[Task]) -> list[list[Any]]:
    """Plan bloklari ve planlanamayan gorevler icin arayuz satirlari olusturur."""

    task_map = {task.id: task for task in tasks}
    rows = [
        [
            DAY_NAMES[block.start.weekday()],
            block.start.strftime("%d.%m.%Y %H:%M"),
            block.end.strftime("%H:%M"),
            block.title,
            block.task_id,
            "Taslak",
        ]
        for block in draft.blocks
    ]
    for item in draft.unscheduled:
        task = task_map.get(item.task_id)
        rows.append(
            [
                "-", "-", "-",
                task.title if task else f"Gorev {item.task_id}",
                item.task_id,
                f"Planlanamadi: {item.reason}",
            ]
        )
    return rows


def _parse_availability(
    week_start_raw: str,
    selected_days: list[str],
    start_raw: str,
    end_raw: str,
) -> Availability:
    """Arayuzdeki tarih, gun ve saat alanlarini Availability modeline cevirir."""

    timezone = ZoneInfo(settings.timezone)
    try:
        week_date = date.fromisoformat(week_start_raw.strip())
        start_time = time.fromisoformat(start_raw.strip())
        end_time = time.fromisoformat(end_raw.strip())
    except ValueError as error:
        raise ValueError(
            "Hafta YYYY-AA-GG, saatler SS:DD biciminde olmalidir."
        ) from error
    weekdays = {DAY_LABELS[label] for label in selected_days if label in DAY_LABELS}
    return Availability(
        week_start=datetime.combine(week_date, time.min, tzinfo=timezone),
        weekdays=weekdays,
        day_start=start_time,
        day_end=end_time,
    )


def initialize_session() -> tuple[str, list[list[Any]], list[dict[str, Any]]]:
    """Yeni tarayici oturumu icin benzersiz kimlik ve bos arayuz verisi uretir."""

    session_id = str(uuid4())
    return session_id, _task_rows(session_id), []


def handle_chat(
    message: str,
    history: list[dict[str, str]] | None,
    session_id: str,
) -> tuple[str, list[dict[str, str]], list[list[Any]], list[dict[str, Any]]]:
    """Sohbet mesajini agente iletip gecmisi, gorevleri ve tool loglarini yeniler."""

    chat_history = list(history or [])
    if not message.strip():
        return "", chat_history, _task_rows(session_id), []
    try:
        result = agent_service.chat(message.strip(), session_id, chat_history)
        answer = result.content
        logs = [event.model_dump(mode="json") for event in result.events]
    except Exception as error:
        answer = f"Islem tamamlanamadi: {error}"
        logs = []
    chat_history.extend(
        [
            {"role": "user", "content": message.strip()},
            {"role": "assistant", "content": answer},
        ]
    )
    return "", chat_history, _task_rows(session_id), logs


def refresh_tasks(session_id: str) -> list[list[Any]]:
    """Gorev tablosunu ilgili oturumun guncel verileriyle yeniler."""

    return _task_rows(session_id)


def generate_plan(
    week_start_raw: str,
    selected_days: list[str],
    start_raw: str,
    end_raw: str,
    session_id: str,
) -> tuple[
    list[list[Any]], dict[str, Any] | None, str, str | None
]:
    """Uygunluk girdilerinden plan taslagi, durum mesaji ve PDF uretir."""

    try:
        availability = _parse_availability(
            week_start_raw, selected_days, start_raw, end_raw
        )
        draft = planning_service.generate(session_id, availability)
        tasks = database.list_tasks(session_id)
        pdf_path = pdf_service.generate(draft, tasks, session_id)
        status = (
            f"{len(draft.blocks)} gorev planlandi, "
            f"{len(draft.unscheduled)} gorev planlanamadi. "
            "Kaydetmek icin plani onaylayin."
        )
        return (
            _plan_rows(draft, tasks),
            draft.model_dump(mode="json"),
            status,
            pdf_path,
        )
    except (ValueError, PlanningError) as error:
        return [], None, f"Plan olusturulamadi: {error}", None
    except Exception as error:
        return [], None, f"Ollama veya uygulama hatasi: {error}", None


def approve_plan(
    draft_data: dict[str, Any] | None, session_id: str
) -> tuple[
    list[list[Any]], list[list[Any]], dict[str, Any] | None, str, str | None
]:
    """Kullanici onayindaki taslagi DB'ye kaydedip onaylanmis PDF'i uretir."""

    if not draft_data:
        return [], _task_rows(session_id), None, "Onaylanacak bir taslak yok.", None
    try:
        draft = PlanDraft.model_validate(draft_data)
        saved = database.save_plan(session_id, draft)
        tasks = database.list_tasks(session_id)
        confirmed_rows = _plan_rows(draft, tasks)
        pdf_path = pdf_service.generate(draft, tasks, session_id, confirmed=True)
        for row in confirmed_rows:
            if row[-1] == "Taslak":
                row[-1] = "Kaydedildi"
        return (
            confirmed_rows,
            _task_rows(session_id),
            None,
            f"Plan kaydedildi: {len(saved)} gorev guncellendi.",
            pdf_path,
        )
    except Exception as error:
        return (
            [],
            _task_rows(session_id),
            draft_data,
            f"Plan kaydedilemedi: {error}",
            None,
        )


def cancel_plan() -> tuple[list[list[Any]], dict[str, Any] | None, str, None]:
    """Taslagi veritabanina dokunmadan arayuz durumundan temizler."""

    return (
        [], None, "Taslak iptal edildi. Veritabaninda degisiklik yapilmadi.", None
    )


def build_demo() -> gr.Blocks:
    """Gradio bilesenlerini ve olay baglantilarini iceren uygulamayi kurar."""

    today = datetime.now(ZoneInfo(settings.timezone)).date()
    monday = today - timedelta(days=today.weekday())

    with gr.Blocks(title="LLM Destekli Haftalik Planlayici") as demo:
        session_state = gr.State()
        draft_state = gr.State()

        gr.Markdown(
            """
# LLM Destekli Haftalik Planlayici

Gorevlerinizi Turkce yazin. Asistan yalnızca SQLite araclarindan gelen
gercek veriyi kullanir; haftalik plan kaydedilmeden once size gosterilir.
"""
        )
        with gr.Row():
            with gr.Column(scale=5):
                chatbot = gr.Chatbot(
                    label="Planlama asistani", height=430
                )
                message = gr.Textbox(
                    label="Mesaj",
                    placeholder=(
                        "Ornek: Persembe 17.00'ye kadar iki saatlik proje "
                        "sunumu hazirlamam gerekiyor, onceligi yuksek."
                    ),
                    lines=2,
                )
                gr.Examples(
                    examples=EXAMPLE_PROMPTS,
                    inputs=message,
                    label="Deneyebileceginiz ornek promptlar",
                )
                send = gr.Button("Gonder", variant="primary")
                with gr.Accordion("Tool-call loglari", open=False):
                    tool_logs = gr.JSON(label="Son istegin arac cagrilari", value=[])
            with gr.Column(scale=6):
                with gr.Tab("Gorevler"):
                    tasks_table = gr.Dataframe(
                        headers=TASK_HEADERS, value=[], interactive=False, wrap=True
                    )
                    refresh = gr.Button("Gorevleri yenile")
                with gr.Tab("Haftalik plan"):
                    week_start = gr.Textbox(
                        label="Hafta baslangici (Pazartesi)",
                        value=monday.isoformat(),
                    )
                    selected_days = gr.CheckboxGroup(
                        choices=list(DAY_LABELS),
                        value=list(DAY_LABELS)[:5],
                        label="Uygun gunler",
                    )
                    with gr.Row():
                        day_start = gr.Textbox(label="Baslangic", value="09:00")
                        day_end = gr.Textbox(label="Bitis", value="18:00")
                    create_plan = gr.Button("Plan Olustur", variant="primary")
                    plan_table = gr.Dataframe(
                        headers=PLAN_HEADERS, value=[], interactive=False, wrap=True
                    )
                    plan_status = gr.Markdown()
                    pdf_file = gr.File(
                        label="Haftalik plani PDF olarak indir",
                        interactive=False,
                    )
                    with gr.Row():
                        approve = gr.Button("Plani Onayla", variant="primary")
                        cancel = gr.Button("Taslagi Iptal")

        demo.load(
            initialize_session,
            outputs=[session_state, tasks_table, tool_logs],
        )
        chat_inputs = [message, chatbot, session_state]
        chat_outputs = [message, chatbot, tasks_table, tool_logs]
        send.click(handle_chat, inputs=chat_inputs, outputs=chat_outputs)
        message.submit(handle_chat, inputs=chat_inputs, outputs=chat_outputs)
        refresh.click(refresh_tasks, inputs=session_state, outputs=tasks_table)
        create_plan.click(
            generate_plan,
            inputs=[week_start, selected_days, day_start, day_end, session_state],
            outputs=[plan_table, draft_state, plan_status, pdf_file],
        )
        approve.click(
            approve_plan,
            inputs=[draft_state, session_state],
            outputs=[plan_table, tasks_table, draft_state, plan_status, pdf_file],
        )
        cancel.click(
            cancel_plan,
            outputs=[plan_table, draft_state, plan_status, pdf_file],
        )
    return demo


def launch_demo() -> None:
    """Gradio uygulamasini yapilandirilan host ve port uzerinde baslatir."""

    demo = build_demo()
    demo.queue(default_concurrency_limit=1).launch(
        server_name=settings.host,
        server_port=settings.port,
        show_error=True,
    )


if __name__ == "__main__":
    launch_demo()
