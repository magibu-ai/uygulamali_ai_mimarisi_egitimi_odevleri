"""
app.py — Hugging Face Space (Gradio) arayuzu
--------------------------------------------
Lezzet Kafe tool-calling asistani icin sohbet arayuzu.

- Sohbet penceresi (kullanici <-> asistan)   [Gradio 'messages' formati]
- Sag tarafta canli TOOL-CALL / TOOL-RESULT logu (halusinasyon seffafligi)

Ortam degiskenleri:
    LLM_BACKEND = hf | mock   (varsayilan: mock -> anahtarsiz calisir)
    HF_TOKEN    = hf_xxx      (hf backend icin)
    MODEL_ID    = <model>     (varsayilan: Qwen/Qwen2.5-7B-Instruct)
"""

import os
import inspect
import gradio as gr

try:
    import spaces

    @spaces.GPU
    def _zerogpu_warmup():
        return "ok"
except Exception:
    pass

# Gradio 5'te Chatbot(type="messages") gerekir; Gradio 6'da bu parametre
# kaldirildi (messages tek/varsayilan format). Surumler arasi uyum icin
# parametreyi yalnizca destekleniyorsa geciriyoruz.
_CHATBOT_KW = {}
if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
    _CHATBOT_KW["type"] = "messages"

from src.database import init_db
from src.agent import chat
from src.llm import ACTIVE_BACKEND, MODEL_ID

init_db()  # sema + seed (idempotent)


def respond(user_msg, chat_history, state_history):
    """chat_history: Gradio 'messages' listesi | state_history: tam rol/icerik gecmisi."""
    if not user_msg or not user_msg.strip():
        return chat_history, state_history, "(bos mesaj)", ""

    logs = []
    state_history, answer = chat(
        state_history + [{"role": "user", "content": user_msg}],
        log=logs.append,
    )
    chat_history = chat_history + [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": answer},
    ]
    log_text = "\n".join(logs) if logs else "(bu turda arac cagrilmadi)"
    return chat_history, state_history, log_text, ""


with gr.Blocks(title="Lezzet Kafe — Tool-Calling Asistan") as demo:
    if ACTIVE_BACKEND == "hf":
        _mode = f"🟢 Gercek model — `{MODEL_ID}` (HF Inference Providers)"
    else:
        _mode = "🟡 Mock backend (offline demo; gercek model icin HF_TOKEN ayarlayin)"
    gr.Markdown(
        "# 🍽️ Lezzet Kafe — Tool-Calling Asistan\n"
        "Menu sorgulama, siparis olusturma ve siparis durumu — hepsi gercek "
        "SQLite veritabanina bagli araclarla. Model yalnizca araclardan donen "
        f"gercek veriyi kullanir (halusinasyon engelleme).\n\n**Mod:** {_mode}"
    )

    state = gr.State([])  # tam mesaj gecmisi (rol/icerik)

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=440, label="Sohbet", **_CHATBOT_KW)
            msg = gr.Textbox(
                placeholder="Or: 'Tatli menusunde ne var?' / '2 kunefe siparis et'",
                label="Mesajiniz",
            )
            with gr.Row():
                send = gr.Button("Gonder", variant="primary")
                clear = gr.Button("Temizle")
        with gr.Column(scale=2):
            tool_log = gr.Textbox(label="🔧 Tool-Call Logu", lines=20, interactive=False)

    gr.Examples(
        examples=[
            "Tatli menusunde neler var?",
            "2 adet kunefe siparis etmek istiyorum.",
            "1 numarali siparisimin durumu ne?",
            "Bir tane uzay burgeri alabilir miyim?",
        ],
        inputs=msg,
    )

    send.click(respond, [msg, chatbot, state], [chatbot, state, tool_log, msg])
    msg.submit(respond, [msg, chatbot, state], [chatbot, state, tool_log, msg])
    clear.click(lambda: ([], [], "", ""), None, [chatbot, state, tool_log, msg])


if __name__ == "__main__":
    demo.launch()
