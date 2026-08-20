import traceback
from typing import Any

import gradio as gr

from agent import run_agent


APP_TITLE = "AI Developer Assistant - Miço"

APP_DESCRIPTION = """
Python paketlerini inceleyen, GitHub repository'lerini araştıran
ve Stack Overflow üzerinde teknik çözüm arayan yapay zekâ destekli
geliştirici asistanı.
"""


def process_user_message(
    user_message: str,
) -> tuple[
    str,
    dict[str, Any],
    list[dict[str, Any]],
    str,
]:
    """
    Gradio arayüzünden alınan kullanıcı mesajını
    agent pipeline'ına gönderir.
    """

    if not user_message or not user_message.strip():
        return (
            "Herhangi bir planner analizi oluşturulmadı.",
            {
                "calls": [],
            },
            [],
            (
                "⚠️ Lütfen çalıştırmadan önce "
                "bir geliştirici sorusu girin."
            ),
        )

    try:
        return run_agent(
            user_message.strip()
        )

    except Exception as exc:
        traceback.print_exc()

        error_message = str(exc)

        return (
            (
                "Agent çalıştırılırken hata oluştu.\n\n"
                f"{error_message}"
            ),
            {
                "calls": [],
            },
            [
                {
                    "success": False,
                    "error": error_message,
                }
            ],
            (
                "## İşlem başarısız\n\n"
                "Agent çalıştırılırken bir hata oluştu.\n\n"
                f"```text\n{error_message}\n```"
            ),
        )


def clear_interface() -> tuple[
    str,
    str,
    dict[str, Any],
    list[Any],
    str,
]:
    """
    Arayüzdeki giriş ve sonuç alanlarını temizler.
    """

    return (
        "",
        "",
        {
            "calls": [],
        },
        [],
        "",
    )


with gr.Blocks(
    title=APP_TITLE,
) as demo:

    gr.Markdown(
        f"""
# 🤖 {APP_TITLE}
{APP_DESCRIPTION}
Desteklenen araçlar:
- **PyPI:** Python paket bilgileri
- **GitHub:** Repository bilgileri ve repository araması
- **Stack Overflow:** Programlama hataları ve teknik sorular
"""
    )

    with gr.Row():
        user_input = gr.Textbox(
            label="Geliştirici Sorusu",
            placeholder=(
                "Örnek: requests ve httpx paketlerini karşılaştır."
            ),
            lines=5,
            max_lines=12,
            autofocus=True,
        )

    with gr.Row():
        submit_button = gr.Button(
            "🚀 Agent'ı Çalıştır",
            variant="primary",
        )

        clear_button = gr.Button(
            "🗑️ Temizle",
            variant="secondary",
        )

    gr.Markdown("---")

    with gr.Accordion(
        "🧠 Planner Analizi",
        open=False,
    ):
        thinking_output = gr.Textbox(
            label="Planner Thinking",
            lines=10,
            interactive=False,
        )

    with gr.Accordion(
        "🛠️ Tool Plan",
        open=True,
    ):
        plan_output = gr.JSON(
            label="Oluşturulan Tool Planı",
            value={
                "calls": [],
            },
        )

    with gr.Accordion(
        "📦 Tool Sonuçları",
        open=True,
    ):
        tool_results_output = gr.JSON(
            label="Tool Execution Results",
            value=[],
        )

    gr.Markdown("## 💬 Nihai Cevap")

    final_answer_output = gr.Markdown(
        value=(
            "Agent cevabı burada görüntülenecek."
        )
    )

    gr.Markdown("---")

    gr.Examples(
        examples=[
            [
                "requests ve httpx paketlerini karşılaştır."
            ],
            [
                (
                    "Python ile geliştirilen popüler LLM agent "
                    "GitHub repository'lerini bul."
                )
            ],
            [
                (
                    "Python'da TypeError: 'list' object is not "
                    "callable hatası alıyorum. Benzer Stack "
                    "Overflow sorularını bul ve açıkla."
                )
            ],
            [
                (
                    "FastAPI paketinin güncel PyPI bilgilerini "
                    "göster."
                )
            ],
            [
                (
                    "openai/openai-python GitHub repository'sini "
                    "incele."
                )
            ],
        ],
        inputs=user_input,
        label="Örnek Sorular",
    )

    submit_button.click(
        fn=process_user_message,
        inputs=[
            user_input,
        ],
        outputs=[
            thinking_output,
            plan_output,
            tool_results_output,
            final_answer_output,
        ],
    )

    user_input.submit(
        fn=process_user_message,
        inputs=[
            user_input,
        ],
        outputs=[
            thinking_output,
            plan_output,
            tool_results_output,
            final_answer_output,
        ],
    )

    clear_button.click(
        fn=clear_interface,
        inputs=[],
        outputs=[
            user_input,
            thinking_output,
            plan_output,
            tool_results_output,
            final_answer_output,
        ],
    )


if __name__ == "__main__":
    demo.queue(
        default_concurrency_limit=2,
    ).launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
        ssr_mode=False,
        pwa=False,
    )