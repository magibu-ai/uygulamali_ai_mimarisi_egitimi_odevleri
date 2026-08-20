"""Cinema-AI — Gradio arayüzü (Hugging Face Space giriş noktası).

Modern, sinema temalı bir sohbet arayüzü. Solda konuşma, sağda modelin arka
planda tetiklediği tool-call'ların canlı akışı gösterilir; bu panel
"arka planda tetiklenen tool-call çıktısı" görünürlüğünü sağlar.

Çalıştırma:
    python app.py          # http://localhost:7860
"""

from __future__ import annotations

import json

import gradio as gr

from src.agent import respond
from src.config import get_llm_config

# --------------------------------------------------------------------------- #
# Görsel tema
# --------------------------------------------------------------------------- #
THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.violet,
    secondary_hue=gr.themes.colors.indigo,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
)

CSS = """
:root {
  --cin-bg: #07070d;
  --cin-panel: rgba(255,255,255,0.045);
  --cin-border: rgba(255,255,255,0.09);
  --cin-violet: #8b5cf6;
  --cin-indigo: #6366f1;
  --cin-pink: #ec4899;
  --cin-gold: #f5c518;
  --cin-text-dim: #9aa0b4;
}

/* Sayfa zemini: derin sinema karanlığı + hafif ışık halesi */
.gradio-container {
  max-width: 1200px !important;
  margin: 0 auto !important;
  background:
    radial-gradient(900px 500px at 8% -5%, rgba(139,92,246,0.10), transparent 60%),
    radial-gradient(800px 500px at 100% 0%, rgba(236,72,153,0.08), transparent 55%) !important;
}

@keyframes gradientShift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
@keyframes floaty { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
@keyframes glowPulse { 0%,100%{opacity:.55} 50%{opacity:1} }
@keyframes fadeUp { from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:translateY(0)} }
@keyframes sweep { from{background-position:-200% 0} to{background-position:200% 0} }

/* ---------- Hero ---------- */
#hero {
  position: relative; overflow: hidden;
  border-radius: 24px;
  margin-bottom: 20px;
  border: 1px solid var(--cin-border);
  background: linear-gradient(120deg, #1b1436, #140f28, #0f1030, #171132);
  background-size: 300% 300%;
  animation: gradientShift 14s ease infinite;
  box-shadow: 0 24px 70px -28px rgba(124,58,237,0.75), inset 0 1px 0 rgba(255,255,255,0.06);
}
#hero::after {  /* üstten geçen ışık parıltısı */
  content:""; position:absolute; inset:0;
  background: radial-gradient(600px 200px at 20% -30%, rgba(255,255,255,0.10), transparent 60%);
  pointer-events:none;
}
.hero-inner { position: relative; padding: 30px 36px 32px; animation: fadeUp .6s ease both; }
.filmstrip {  /* dekoratif film şeridi noktaları */
  position:absolute; left:0; right:0; top:0; height:14px;
  background:
    repeating-linear-gradient(90deg, transparent 0 14px, rgba(0,0,0,0.55) 14px 20px),
    linear-gradient(90deg, var(--cin-violet), var(--cin-pink), var(--cin-gold), var(--cin-indigo));
  background-size: 20px 14px, 300% 14px;
  animation: sweep 8s linear infinite;
  opacity:.9;
}
.hero-kicker {
  font-size:.72rem; font-weight:700; letter-spacing:.28em;
  color:#c4b5fd; margin-bottom:10px; text-transform:uppercase;
}
#hero h1 {
  font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em;
  margin: 0 0 10px 0; color: #fff;
  text-shadow: 0 2px 40px rgba(139,92,246,0.6);
}
#hero h1 .accent {
  background: linear-gradient(90deg, var(--cin-gold), #ffe58a);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
#hero p { color: #cdd0e3; margin: 0; font-size: 1.04rem; line-height: 1.55; max-width: 720px; }
#hero p b { color:#fff; }
.no-hall { color: var(--cin-gold); font-weight: 700; }

.badges { margin-top: 18px; display: flex; gap: 9px; flex-wrap: wrap; }
.badge {
  font-size: 0.78rem; font-weight: 600;
  padding: 6px 13px; border-radius: 999px;
  border: 1px solid var(--cin-border);
  background: rgba(255,255,255,0.06); color: #e6e8f2;
  backdrop-filter: blur(8px);
  animation: floaty 6s ease-in-out infinite;
}
.badge:nth-child(2){animation-delay:.4s} .badge:nth-child(3){animation-delay:.8s} .badge:nth-child(4){animation-delay:1.2s}
.badge.gold {
  border-color: rgba(245,197,24,0.45); color: var(--cin-gold);
  box-shadow: 0 0 20px -6px rgba(245,197,24,0.6);
  animation: floaty 6s ease-in-out infinite, glowPulse 3s ease-in-out infinite;
}

/* ---------- Cam efektli paneller ---------- */
.panel-card {
  border: 1px solid var(--cin-border);
  border-radius: 20px;
  padding: 8px 10px 10px;
  background: rgba(255,255,255,0.035);
  backdrop-filter: blur(10px);
  box-shadow: 0 16px 50px -30px rgba(0,0,0,0.9);
}
.section-title {
  font-weight: 700; font-size: 0.82rem; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--cin-text-dim);
  margin: 8px 8px 10px;
}

/* ---------- Sohbet ---------- */
#chatbot { border: none !important; background: transparent !important; }
#chatbot .message-row { animation: fadeUp .35s ease both; }
#chatbot .message.user {
  background: linear-gradient(135deg, var(--cin-violet), var(--cin-indigo)) !important;
  color: #fff !important; border: none !important;
  box-shadow: 0 8px 24px -10px rgba(124,58,237,0.8) !important;
}
#chatbot .message.bot {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--cin-border) !important;
  color: #eef0fb !important;
}

/* ---------- Tool-call akış paneli ---------- */
#tool-panel {
  min-height: 470px;
  border-radius: 16px;
  padding: 16px 18px !important;
  background: linear-gradient(180deg, #0b0b16, #08080f);
  border: 1px solid var(--cin-border);
  font-size: 0.9rem;
  box-shadow: inset 0 0 40px -20px rgba(139,92,246,0.5);
}
#tool-panel h3 {
  margin: 14px 0 4px; font-size: 0.94rem; color: #e9e6ff;
  padding-left: 10px; border-left: 3px solid var(--cin-violet);
  animation: fadeUp .4s ease both;
}
#tool-panel code { color: var(--cin-gold); font-size:.82rem; }
#tool-panel pre {
  border-radius: 12px; border: 1px solid var(--cin-border);
  background: #05050c !important; box-shadow: inset 0 0 20px -12px rgba(139,92,246,0.6);
}

/* ---------- Örnek chip'ler ---------- */
.chip button {
  border-radius: 999px !important;
  border: 1px solid var(--cin-border) !important;
  background: rgba(255,255,255,0.05) !important;
  color: #e4e7f5 !important;
  font-weight: 500 !important;
  transition: all .2s cubic-bezier(.2,.8,.2,1);
}
.chip button:hover {
  border-color: var(--cin-violet) !important;
  background: rgba(139,92,246,0.2) !important;
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -12px rgba(139,92,246,0.9) !important;
}

/* Metin kutusu + Gönder */
#msg-box textarea {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--cin-border) !important;
  border-radius: 14px !important;
}
#send-btn {
  background: linear-gradient(135deg, var(--cin-violet), var(--cin-pink)) !important;
  border: none !important; color: #fff !important; font-weight: 700 !important;
  border-radius: 14px !important;
  box-shadow: 0 12px 30px -12px rgba(236,72,153,0.8) !important;
  transition: transform .15s ease, box-shadow .15s ease;
}
#send-btn:hover { transform: translateY(-2px); box-shadow: 0 16px 40px -12px rgba(236,72,153,0.95) !important; }

/* İnce scrollbar */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.35); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.6); }

footer { display: none !important; }

/* ---------- Responsive ---------- */
@media (max-width: 980px) {
  #main-row { flex-direction: column !important; flex-wrap: nowrap !important; }
  #main-row > * { min-width: 100% !important; width: 100% !important; }
  #tool-panel { min-height: 260px; }
}
@media (max-width: 680px) {
  .gradio-container { max-width: 100% !important; padding: 6px !important; }
  .hero-inner { padding: 22px 18px 24px; }
  #hero { border-radius: 18px; }
  #hero h1 { font-size: 1.85rem; }
  #hero p { font-size: 0.95rem; }
  .hero-kicker { letter-spacing: .18em; font-size: .66rem; }
  .badge { font-size: 0.72rem; padding: 5px 10px; }
  #chatbot { height: 380px !important; }
  #send-btn { padding-left: 14px !important; padding-right: 14px !important; }
  .chip button { font-size: 0.8rem !important; }
}
@media (max-width: 420px) {
  #hero h1 { font-size: 1.6rem; }
  .badges { gap: 6px; }
}
"""


def _format_trace(trace: list[dict]) -> str:
    """Tool izini Markdown olarak biçimlendirir (panelde gösterim)."""
    if not trace:
        return (
            "<div style='color:#9aa0b4;padding:20px 6px;text-align:center'>"
            "🛰️ Perde arkası.<br>Bir şey sorduğun an, hangi aracı çalıştırdığımı ve "
            "veritabanından ne döndüğünü tam burada, canlı göreceksin.</div>"
        )
    lines: list[str] = []
    for i, step in enumerate(trace, 1):
        args = json.dumps(step["arguments"], ensure_ascii=False)
        result = json.dumps(step["result"], ensure_ascii=False, indent=2)
        lines.append(f"### `{i}` 🔧 {step['name']}")
        lines.append(f"**Argümanlar:** `{args}`")
        lines.append("**Veritabanından dönen sonuç:**")
        lines.append(f"```json\n{result}\n```")
    return "\n\n".join(lines)


def chat_fn(user_message: str, history: list[dict]):
    """Kullanıcı mesajına yanıt üretir; (sohbet, tool_paneli) döndürür."""
    history = history or []
    if not user_message.strip():
        return history, _format_trace([])

    cfg = get_llm_config()
    try:
        reply, trace = respond(history, user_message, cfg=cfg)
    except Exception as exc:  # ağ/anahtar hataları arayüzü çökertmesin
        reply, trace = f"⚠️ Bir hata oluştu: {exc}", []

    history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return history, _format_trace(trace)


EXAMPLES = [
    "🚀 8.7 üstü bir bilim kurgu öner",
    "🎬 Christopher Nolan filmleri",
    "➕ Yeşil Yol'u listeme ekle",
    "📋 İzleme listemde ne var?",
    "🇹🇷 En iyi Türk dramı",
]


def build_demo() -> gr.Blocks:
    """Gradio arayüzünü kurar."""
    cfg = get_llm_config()
    backend_badge = (
        "<span class='badge gold'>🧪 Yerel Mock — API'siz</span>"
        if cfg.use_mock
        else f"<span class='badge gold'>🔌 {cfg.model}</span>"
    )

    with gr.Blocks(title="Cinema-AI", theme=THEME, css=CSS) as demo:
        gr.HTML(
            f"""
            <div id="hero">
              <div class="filmstrip"></div>
              <div class="hero-inner">
                <div class="hero-kicker">✦ BU AKŞAM NE İZLESEK?</div>
                <h1>🎬 Cinema<span class="accent">·AI</span></h1>
                <p>Karar veremediğin akşamlar için. Elimdeki filmler arasından sana
                uygun olanı bulur, beğendiğini listene atarım.
                <span class="no-hall">Uydurma yok</span> — önerdiğim her film gerçekten var.</p>
                <div class="badges">
                  <span class="badge">🛠️ Function Calling</span>
                  <span class="badge">🗄️ SQLite · okuma + yazma</span>
                  <span class="badge">🚫 Anti-halüsinasyon</span>
                  {backend_badge}
                </div>
              </div>
            </div>
            """
        )

        with gr.Row(equal_height=True, elem_id="main-row"):
            with gr.Column(scale=3):
                with gr.Group(elem_classes="panel-card"):
                    gr.HTML("<div class='section-title'>💬 Sohbet</div>")
                    chatbot = gr.Chatbot(
                        type="messages",
                        height=470,
                        elem_id="chatbot",
                        show_label=False,
                        show_copy_button=True,
                        avatar_images=(None, None),
                        placeholder=(
                            "<div style='text-align:center;color:#9aa0b4'>"
                            "🍿 Selam! Moduna göre bir film bulalım.<br>"
                            "Aşağıdakilerden birine dokun ya da aklındakini yaz.</div>"
                        ),
                    )
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="Bir tür, yönetmen ya da puan yaz — örn. '8.5 üstü bir gerilim'",
                            show_label=False,
                            scale=8,
                            autofocus=True,
                            container=False,
                            elem_id="msg-box",
                        )
                        send = gr.Button("Gönder", scale=1, elem_id="send-btn", variant="primary")
                    with gr.Row(elem_classes="chip"):
                        chip_btns = [gr.Button(ex, size="sm") for ex in EXAMPLES]
                    clear = gr.Button("🗑 Sohbeti temizle", size="sm")

            with gr.Column(scale=2):
                with gr.Group(elem_classes="panel-card"):
                    gr.HTML("<div class='section-title'>🛰️ Arka Plan · Tool-Call Akışı</div>")
                    tool_panel = gr.Markdown(_format_trace([]), elem_id="tool-panel")

        # ---- Olay bağlama ----
        def _submit(user_message, history):
            new_hist, trace = chat_fn(user_message, history)
            return new_hist, trace, ""  # textbox temizle

        msg.submit(_submit, [msg, chatbot], [chatbot, tool_panel, msg])
        send.click(_submit, [msg, chatbot], [chatbot, tool_panel, msg])

        # Chip'e tıklayınca örneği kutuya yaz (baştaki emoji'yi at).
        for btn, ex in zip(chip_btns, EXAMPLES):
            btn.click(lambda e=ex: e.split(" ", 1)[1], None, msg)

        clear.click(lambda: ([], _format_trace([])), None, [chatbot, tool_panel])

    return demo


if __name__ == "__main__":
    build_demo().launch()
