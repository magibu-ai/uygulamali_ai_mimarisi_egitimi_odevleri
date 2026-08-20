"""Gradio 6.20 UI for the isolated SQLite beehive assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import pandas as pd

try:  # Hugging Face ZeroGPU provides this package; local installs need not.
    import spaces
except ImportError:  # pragma: no cover - expected in the root .venv.
    spaces = None

try:  # ``python les6/app.py`` from the Space root and ``import les6.app``.
    from .agent import BeehiveAgent
    from .database import HiveDatabase, cleanup_session, create_session_database
    from .tools import TOOL_SCHEMAS, get_hive_details, list_hives, record_inspection
except ImportError:  # pragma: no cover - direct script execution.
    from agent import BeehiveAgent
    from database import HiveDatabase, cleanup_session, create_session_database
    from tools import TOOL_SCHEMAS, get_hive_details, list_hives, record_inspection

TOOLS = TOOL_SCHEMAS
TOOL_FUNCS = {
    "list_hives": list_hives,
    "get_hive_details": get_hive_details,
    "record_inspection": record_inspection,
}


READING_COLUMNS = ["recorded_at", "temperature_c", "humidity_percent", "ph", "weight_kg"]
APP_CSS = """
.les6-shell { max-width: 1180px; margin: 0 auto; }
.les6-note { color: #5f6b5b; font-size: 0.9rem; }
@media (max-width: 700px) { .les6-shell { padding: 0.5rem; } }
"""


def _open_session(state: str | Path | None) -> tuple[HiveDatabase, str]:
    if state:
        candidate = Path(state)
        if candidate.is_file():
            return HiveDatabase(candidate), str(candidate)
    database = create_session_database()
    return database, str(database.path)


def _history_for_chat(history: Sequence[Any] | None) -> list[Any]:
    return list(history or [])


def _sensor_outputs(result: dict[str, Any] | None) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if not result or "error" in result:
        return [], pd.DataFrame(columns=READING_COLUMNS)
    if "readings" in result:
        readings = list(result["readings"])
    elif "hives" in result:
        readings = [
            {"recorded_at": hive["latest_reading"]["recorded_at"], **{key: hive["latest_reading"][key] for key in READING_COLUMNS[1:]}, "hive_id": hive["hive_id"]}
            for hive in result["hives"]
            if hive.get("latest_reading")
        ]
    else:
        readings = []
    frame = pd.DataFrame(readings)
    for column in READING_COLUMNS:
        if column not in frame:
            frame[column] = None
    return readings, frame[READING_COLUMNS]


def _sensor_frame_from_results(last_result: dict[str, Any] | None, tool_logs: Sequence[Any] | None = None) -> pd.DataFrame:
    """Select the latest result that actually contains sensor rows.

    A chained request commonly ends with ``record_inspection``. That write
    result is important for the raw log but has no readings, so the table/plot
    must fall back to the previous ``get_hive_details`` or ``list_hives`` call.
    """

    if isinstance(last_result, dict) and isinstance(last_result.get("sensor_result"), dict):
        _, frame = _sensor_outputs(last_result["sensor_result"])
        if not frame.empty:
            return frame
    candidates: list[dict[str, Any]] = []
    if isinstance(last_result, dict):
        candidates.append(last_result)
    for log in reversed(list(tool_logs or [])):
        if isinstance(log, dict) and isinstance(log.get("result"), dict):
            candidates.append(log["result"])
    for candidate in candidates:
        if "readings" in candidate or "hives" in candidate:
            _, frame = _sensor_outputs(candidate)
            if not frame.empty:
                return frame
    return pd.DataFrame(columns=READING_COLUMNS)


def chat_message(message: str, history: Sequence[Any] | None, session_path: str | None):
    """Gradio event handler returning chat, logs, raw result, and plot data."""

    database, state = _open_session(session_path)
    try:
        try:
            result = BeehiveAgent(database).respond(message, _history_for_chat(history))
        except Exception:
            result = {
                "reply": "Model isteği tamamlanamadı. HF_TOKEN ve Router bağlantısını kontrol edin.",
                "tool_logs": [{"error": {"code": "MODEL_ERROR", "message": "Model isteği tamamlanamadı."}}],
                "last_result": {"error": {"code": "MODEL_ERROR", "message": "Model isteği tamamlanamadı."}},
            }
        updated = _history_for_chat(history)
        if message:
            updated.append({"role": "user", "content": message})
        updated.append({"role": "assistant", "content": result.get("reply", "")})
        logs = result.get("tool_logs", [])
        last = result.get("last_result")
        frame = _sensor_frame_from_results(last, logs)
        return updated, state, logs, last or {}, frame, frame
    finally:
        database.close()


def build_demo():
    import gradio as gr

    with gr.Blocks(title="Arı Kovanı Sağlık Asistanı") as demo:
        session_state = gr.State(value=None, time_to_live=3600, delete_callback=cleanup_session)
        with gr.Column(elem_classes="les6-shell"):
            gr.Markdown(
                "# 🐝 Arı Kovanı Sağlık Asistanı\n"
                "Kaynak sensör ölçümlerini istatistiksel eşiklerle özetler. **Normal / izle / dikkat** etiketleri biyolojik tanı değildir."
            )
            chatbot = gr.Chatbot(label="Sohbet", height=430, placeholder="Örn. Dikkat gerektiren kovanları bul.")
            with gr.Row():
                message = gr.Textbox(label="Mesaj", placeholder="Kovan-3 için kontrol kaydı oluştur...", scale=5)
                send = gr.Button("Gönder", variant="primary", scale=1)
            gr.Markdown("Her oturum kendi geçici SQLite kopyasını kullanır; oturum bitince dosya silinir.", elem_classes="les6-note")
            with gr.Row():
                tool_logs = gr.JSON(label="Tool-call günlükleri (ad, argüman, ham sonuç, süre)", open=True)
                raw_result = gr.JSON(label="Son ham tool sonucu", open=False)
            sensor_table = gr.Dataframe(label="Sensör geçmişi", headers=READING_COLUMNS, interactive=False, type="pandas")
            sensor_plot = gr.LinePlot(label="Sensör geçmişi grafiği", x="recorded_at", y="temperature_c", tooltip="all", height=300)
            gr.Examples(
                examples=[["Dikkat gerektiren kovanları bul. En riskli kovanın ayrıntılarını göster ve Kovan-3 için kraliçenin görüldüğü, varroa sayısının 3 olduğu bir kontrol kaydı oluştur."]],
                inputs=message,
                label="Örnek istek",
            )
        inputs = [message, chatbot, session_state]
        outputs = [chatbot, session_state, tool_logs, raw_result, sensor_table, sensor_plot]
        send.click(chat_message, inputs=inputs, outputs=outputs, api_name="chat")
        message.submit(chat_message, inputs=inputs, outputs=outputs, api_name="chat_submit")
        if spaces is not None:
            # ZeroGPU startup checks require one bound @spaces.GPU function.
            # The actual chat path stays CPU-only and calls the remote Router.
            @spaces.GPU(duration=1)
            def _zerogpu_startup_probe() -> str:
                """ZeroGPU discovery no-op; never handles a chat request."""

                return ""

            gr.Button(visible=False).click(_zerogpu_startup_probe, outputs=[])
    # Gradio 6.20 moved CSS from Blocks construction to launch(). Keep the
    # string on the demo for callers that launch it themselves.
    demo._les6_css = APP_CSS
    return demo


if __name__ == "__main__":  # pragma: no cover - manual Space/local launch.
    build_demo().launch(css=APP_CSS)


__all__ = ["APP_CSS", "build_demo", "chat_message", "cleanup_session"]
