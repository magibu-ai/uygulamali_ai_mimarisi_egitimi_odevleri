from __future__ import annotations

import asyncio
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import gradio as gr

from x_research_agent.agent.runner import AgentRunner
from x_research_agent.config import get_settings
from x_research_agent.domain.schemas import ResearchConstraints, SortMode, ToolCallRecord
from x_research_agent.providers.openrouter import OpenRouterClient
from x_research_agent.providers.xquik import XquikClient
from x_research_agent.security import generate_session_id
from x_research_agent.tools.runtime import AgentRuntime

from .rendering import export_report_files, render_report, render_timeline

settings = get_settings()


def new_state() -> dict[str, Any]:
    return {
        "session_id": generate_session_id(),
        "conversation": [],
        "runtime": None,
        "usage": None,
        "latest_report": None,
        "models": {},
    }


async def load_models(api_key: str, state: dict[str, Any]):
    if not api_key.strip():
        raise gr.Error("OpenRouter API anahtarı gerekli.")
    async with OpenRouterClient(
        api_key,
        base_url=settings.openrouter_base_url,
        app_url=settings.openrouter_app_url,
        app_name=settings.openrouter_app_name,
        timeout=settings.request_timeout_seconds,
    ) as client:
        models = await client.list_tool_models()
    state["models"] = {model.id: model.model_dump() for model in models}
    choices = _model_choices(models)
    providers = sorted({model.provider for model in models})
    return (
        gr.Dropdown(choices=choices, value=None),
        gr.Dropdown(choices=[("Tümü", "")] + [(item, item) for item in providers], value=""),
        state,
        f"{len(models)} tool modeli bulundu.",
    )


def filter_models(
    search: str,
    provider: str,
    structured_only: bool,
    model_sort: str,
    state: dict[str, Any],
):
    from x_research_agent.domain.schemas import ModelInfo

    models = [ModelInfo.model_validate(item) for item in state.get("models", {}).values()]
    needle = search.strip().lower()
    if needle:
        models = [model for model in models if needle in f"{model.name} {model.id}".lower()]
    if provider:
        models = [model for model in models if model.provider == provider]
    if structured_only:
        models = [model for model in models if model.supports_structured_output]
    if model_sort == "context":
        models.sort(key=lambda model: model.context_length or 0, reverse=True)
    elif model_sort == "price":
        models.sort(key=lambda model: _price_number(model.prompt_price))
    elif model_sort == "structured":
        models.sort(key=lambda model: (not model.supports_structured_output, model.name.lower()))
    return gr.Dropdown(choices=_model_choices(models), value=None)


def _price_number(value: str | None) -> float:
    try:
        return float(value or "inf")
    except ValueError:
        return float("inf")


def _model_choices(models):
    choices = []
    for model in models:
        prompt_per_million = _price_number(model.prompt_price) * 1_000_000
        price = "?" if prompt_per_million == float("inf") else f"${prompt_per_million:g}/M"
        badge = "◆ Structured Output · " if model.supports_structured_output else ""
        label = (
            f"{badge}{model.name} · {model.provider} · "
            f"ctx {model.context_length or '?'} · giriş {price}"
        )
        choices.append((label, model.id))
    return choices


async def test_xquik(api_key: str):
    if not api_key.strip():
        raise gr.Error("Xquik API anahtarı gerekli.")
    async with XquikClient(
        api_key, base_url=settings.xquik_base_url, timeout=settings.request_timeout_seconds
    ) as client:
        result = await client.check_connection()
    balance = result.get("credit_balance") or "bilinmiyor"
    return f"Bağlantı başarılı · plan: {result.get('plan') or 'bilinmiyor'} · kredi: {balance}"


async def run_research(
    question: str,
    chat_history: list[dict[str, Any]],
    openrouter_key: str,
    xquik_key: str,
    model_id: str,
    language: str,
    start_date: str,
    end_date: str,
    include_retweets: bool,
    sort_mode: str,
    budget: int,
    state: dict[str, Any],
):
    if not model_id:
        raise gr.Error("Önce bir OpenRouter modeli seçin.")
    if not openrouter_key.strip() or not xquik_key.strip():
        raise gr.Error("OpenRouter ve Xquik API anahtarları gerekli.")
    constraints = ResearchConstraints(
        language=language.strip() or None,
        start_date=date.fromisoformat(start_date) if start_date else None,
        end_date=date.fromisoformat(end_date) if end_date else None,
        include_retweets=include_retweets,
        sort=SortMode(sort_mode),
        post_budget=int(budget),
    )
    queue: asyncio.Queue[ToolCallRecord] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    runtime = state.get("runtime")
    if runtime is None:
        runtime = AgentRuntime(
            session_id=state["session_id"],
            user_question=question,
            selected_model=model_id,
            constraints=constraints,
        )
        state["runtime"] = runtime

    def progress(record: ToolCallRecord) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, record)

    runner = AgentRunner(settings)
    task = asyncio.create_task(
        runner.run(
            user_message=question,
            session_id=state["session_id"],
            model_id=model_id,
            openrouter_key=openrouter_key,
            xquik_key=xquik_key,
            constraints=constraints,
            conversation=state.get("conversation"),
            runtime=runtime,
            progress=progress,
        )
    )
    chat_history = list(chat_history or []) + [{"role": "user", "content": question}]
    yield chat_history, "Araştırma başlatıldı…", state, None, None, ""
    while not task.done():
        try:
            await asyncio.wait_for(queue.get(), timeout=0.25)
        except TimeoutError:
            pass
        yield chat_history, render_timeline(runtime), state, None, None, ""
    try:
        report, conversation, runtime, usage = await task
    except Exception as exc:
        raise gr.Error(f"Araştırma tamamlanamadı: {exc}") from exc
    state.update(
        {
            "conversation": conversation,
            "runtime": runtime,
            "usage": usage,
            "latest_report": report,
        }
    )
    report_md = render_report(report, runtime)
    chat_history.append({"role": "assistant", "content": report_md})
    export_dir = Path(tempfile.gettempdir()) / "x-twitter-research-agent" / runtime.session_id
    md_file, json_file = export_report_files(report=report, runtime=runtime, export_dir=export_dir)
    access = (
        f"Araştırma ID: `{runtime.thread_id}` · Erişim kodu: `{runtime.access_code}` · "
        "Son etkinlikten itibaren 7 gün saklanır."
    )
    yield chat_history, render_timeline(runtime, usage), state, md_file, json_file, access


def cancel_research(state: dict[str, Any]):
    runtime = state.get("runtime")
    if runtime:
        runtime.cancelled.set()
        return "İptal istendi; yeni tool çağrıları durdurulacak."
    return "Aktif araştırma yok."


def build_app() -> gr.Blocks:
    with gr.Blocks(title="X/Twitter Research Agent") as demo:
        state = gr.State(new_state)
        gr.Markdown(
            "# X/Twitter Research Agent\n"
            "OpenRouter tool calling, Xquik salt-okunur API ve PostgreSQL "
            "destekli araştırma asistanı."
        )
        with gr.Accordion("API ve model ayarları", open=True):
            with gr.Row():
                openrouter_key = gr.Textbox(label="OpenRouter API Key", type="password")
                xquik_key = gr.Textbox(label="Xquik API Key", type="password")
            with gr.Row():
                models_button = gr.Button("Tool modellerini getir", variant="primary")
                xquik_button = gr.Button("Xquik bağlantısını test et")
            model_dropdown = gr.Dropdown(label="OpenRouter modeli", choices=[])
            with gr.Row():
                model_search = gr.Textbox(label="Model ara", placeholder="Model adı veya slug")
                provider_filter = gr.Dropdown(label="Sağlayıcı", choices=[("Tümü", "")], value="")
                structured_only = gr.Checkbox(label="Yalnızca Structured Output", value=False)
                model_sort = gr.Dropdown(
                    label="Model sıralama",
                    choices=[
                        ("Structured Output önce", "structured"),
                        ("Düşük giriş fiyatı", "price"),
                        ("Yüksek context", "context"),
                    ],
                    value="structured",
                )
            connection_status = gr.Markdown()
        with gr.Accordion("Gelişmiş araştırma sınırları", open=False):
            with gr.Row():
                language = gr.Textbox(label="Dil kodu", placeholder="tr, en veya boş")
                start_date = gr.Textbox(label="Başlangıç", placeholder="YYYY-MM-DD")
                end_date = gr.Textbox(label="Bitiş", placeholder="YYYY-MM-DD")
            with gr.Row():
                include_retweets = gr.Checkbox(label="Retweetleri dahil et", value=False)
                sort_mode = gr.Dropdown(
                    label="Sıralama",
                    choices=[
                        ("İlgili", SortMode.RELEVANCE.value),
                        ("En yeni", SortMode.LATEST.value),
                        ("Öne çıkan", SortMode.TOP.value),
                    ],
                    value=SortMode.RELEVANCE.value,
                )
                budget = gr.Slider(10, 200, value=50, step=10, label="Gönderi bütçesi")
        chatbot = gr.Chatbot(label="Araştırma sohbeti", type="messages", height=520)
        question = gr.Textbox(
            label="Araştırma sorusu",
            placeholder="Örn. Son bir haftada OpenRouter hakkındaki fiyat şikâyetlerini araştır.",
            lines=3,
        )
        with gr.Row():
            research_button = gr.Button("Araştır", variant="primary")
            cancel_button = gr.Button("Araştırmayı durdur", variant="stop")
        with gr.Accordion("Araştırma süreci ve tool çağrıları", open=True):
            timeline = gr.Markdown("Henüz tool çağrısı yok.")
        access_info = gr.Markdown()
        with gr.Row():
            markdown_download = gr.File(label="Markdown raporu")
            json_download = gr.File(label="JSON raporu")

        models_button.click(
            load_models,
            inputs=[openrouter_key, state],
            outputs=[model_dropdown, provider_filter, state, connection_status],
        )
        filter_inputs = [model_search, provider_filter, structured_only, model_sort, state]
        for component in [model_search, provider_filter, structured_only, model_sort]:
            component.change(filter_models, inputs=filter_inputs, outputs=model_dropdown)
        xquik_button.click(test_xquik, inputs=xquik_key, outputs=connection_status)
        research_event = research_button.click(
            run_research,
            inputs=[
                question,
                chatbot,
                openrouter_key,
                xquik_key,
                model_dropdown,
                language,
                start_date,
                end_date,
                include_retweets,
                sort_mode,
                budget,
                state,
            ],
            outputs=[
                chatbot,
                timeline,
                state,
                markdown_download,
                json_download,
                access_info,
            ],
        )
        question.submit(
            run_research,
            inputs=[
                question,
                chatbot,
                openrouter_key,
                xquik_key,
                model_dropdown,
                language,
                start_date,
                end_date,
                include_retweets,
                sort_mode,
                budget,
                state,
            ],
            outputs=[
                chatbot,
                timeline,
                state,
                markdown_download,
                json_download,
                access_info,
            ],
        )
        cancel_button.click(
            cancel_research, inputs=state, outputs=timeline, cancels=[research_event]
        )
    return demo
