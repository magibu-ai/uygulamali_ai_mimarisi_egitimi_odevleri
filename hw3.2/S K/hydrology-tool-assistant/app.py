import inspect
import os

os.environ["GRADIO_SSR_MODE"] = "False"

import gradio as gr
import spaces

import agent


def _visible_chat(full_history):
    """Tool mesajlarını gizleyip yalnız kullanıcı/asistan diyaloğunu Gradio'ya verir."""
    visible = []
    for message in full_history or []:
        role = message.get("role")
        content = message.get("content") or ""

        # Tool çağıran boş assistant mesajlarını ve tool response'ları sohbet panelinde göstermiyoruz.
        if role == "user":
            visible.append({"role": "user", "content": content})
        elif role == "assistant" and not message.get("tool_calls") and content:
            visible.append({"role": "assistant", "content": content})

    return visible


@spaces.GPU(duration=30)
def run_agent_space(user_message, conversation_state):
    for log_text, answer_text, new_state in agent.run_agent(
        user_message,
        conversation_state,
    ):
        yield (
            log_text,
            answer_text,
            new_state,
            _visible_chat(new_state),
            "",
        )


def clear_conversation():
    return "", "", [], [], ""


css_ayari = """
#log-box {
    height: 70vh !important;
    max-height: 600px !important;
    overflow-y: auto !important;
    padding: 15px !important;
    border: 1px solid #444 !important;
    border-radius: 8px !important;
    background-color: #1e1e1e !important;
    font-family: monospace !important;
}
#answer-box {
    font-size: 16px !important;
    padding: 15px !important;
    background-color: #2b2b2b !important;
    border-radius: 8px !important;
    border: 1px solid #555 !important;
}
"""

with gr.Blocks(css=css_ayari, theme=gr.themes.Soft()) as demo:
    conversation_state = gr.State([])

    gr.Markdown("# 🌀 Akarsu Gözlem ve Debi Uyarı Asistanı (Tool-Calling)")
    gr.Markdown(
        "Bu demo tek bir komut yerine **çok turlu küçük bir senaryo** üzerinden çalışır. "
        "Asistan SQLite veritabanından veri okur, uyarı yazar ve sonraki mesajlarda konuşma bağlamını korur."
    )
    gr.Markdown(
        "**Örnek akış:** ① Kocaeli'deki istasyonları listele → "
        "② Kirazdere'nin son ölçümüne bak → "
        "③ Kirazdere için 65 m³/s eşikli uyarı oluştur → "
        "④ Kirazdere için oluşturduğum uyarıları göster."
    )

    with gr.Row():
        with gr.Column(scale=1):
            chatbot_kwargs = {
                "label": "Senaryo / Konuşma Akışı",
                "height": 360,
            }
            # Gradio 5.x mesaj sözlükleri için type="messages" ister;
            # Gradio 6.x'te bu artık varsayılandır ve argüman kaldırılmıştır.
            if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
                chatbot_kwargs["type"] = "messages"

            sohbet = gr.Chatbot(**chatbot_kwargs)

            mesaj = gr.Textbox(
                label="Mesajınız",
                placeholder="Örn: Kocaeli'deki aktif istasyonlar hangileri?",
                lines=2,
            )

            with gr.Row():
                gonder = gr.Button("Gönder", variant="primary")
                temizle = gr.Button("Konuşmayı Temizle")

            gr.Markdown("### 🤖 Son Yanıt")
            cevap_alani = gr.Markdown(elem_id="answer-box")

        with gr.Column(scale=1):
            gr.Markdown("### 🛠️ Bu Turun Tool-Call Günlüğü")
            log_alani = gr.Markdown(elem_id="log-box")

    event_outputs = [
        log_alani,
        cevap_alani,
        conversation_state,
        sohbet,
        mesaj,
    ]

    gonder.click(
        fn=run_agent_space,
        inputs=[mesaj, conversation_state],
        outputs=event_outputs,
    )

    mesaj.submit(
        fn=run_agent_space,
        inputs=[mesaj, conversation_state],
        outputs=event_outputs,
    )

    temizle.click(
        fn=clear_conversation,
        outputs=event_outputs,
        queue=False,
    )

if __name__ == "__main__":
    demo.launch()
