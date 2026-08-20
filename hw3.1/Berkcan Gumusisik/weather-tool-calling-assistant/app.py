"""SkyBrief — weather tool-calling assistant (Gradio / Hugging Face Spaces).

Design: a dark "observatory console" split into two panes — a conversational
transcript on the left, and a live tool-call console on the right that
renders every function call / result as the agent executes it. This makes
the tool-calling mechanics (the actual point of the assignment) the visual
centerpiece instead of an afterthought buried in a text block.
"""

from __future__ import annotations

import html as _html
import json as _json
import re as _re

import gradio as gr

from agent import AgentResponse, run_agent
from tools import TOOL_DEFINITIONS

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --bg-0: #05070c;
  --bg-1: #0a0e18;
  --panel: rgba(255, 255, 255, 0.035);
  --panel-strong: rgba(255, 255, 255, 0.06);
  --line: rgba(255, 255, 255, 0.09);
  --line-soft: rgba(255, 255, 255, 0.05);
  --ink: #eef1f8;
  --ink-dim: #8a93ab;
  --ink-faint: #5b6580;
  --teal: #5eead4;
  --teal-deep: #14b8a6;
  --amber: #fbbf24;
  --violet: #a78bfa;
  --good: #4ade80;
}

html, body, .gradio-container {
  min-height: 100% !important;
  background: var(--bg-0) !important;
}

body {
  margin: 0;
  background:
    radial-gradient(680px 420px at 8% -8%, rgba(94, 234, 212, 0.16), transparent 60%),
    radial-gradient(620px 400px at 100% 0%, rgba(167, 139, 250, 0.14), transparent 55%),
    radial-gradient(900px 600px at 50% 110%, rgba(20, 184, 166, 0.08), transparent 60%),
    var(--bg-0) !important;
  background-attachment: fixed !important;
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.5;
  background-image: radial-gradient(rgba(255, 255, 255, 0.55) 0.6px, transparent 0.6px);
  background-size: 22px 22px;
  mask-image: radial-gradient(ellipse 75% 55% at 50% 0%, black 0%, transparent 70%);
}

.gradio-container {
  position: relative;
  z-index: 1;
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding: 0 18px 56px !important;
  font-family: "Inter", sans-serif !important;
  color: var(--ink) !important;
}

footer {
  display: none !important;
}

.contain > .gap > .padded {
  background: transparent !important;
  box-shadow: none !important;
  border: none !important;
}

/* ---------------- Header ---------------- */
#hero {
  padding: 44px 4px 26px;
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  align-items: flex-end;
  justify-content: space-between;
  animation: fade-up 700ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

.hero-left .kicker {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--teal);
  margin: 0 0 10px;
}

.hero-left h1 {
  font-family: "Space Grotesk", sans-serif;
  font-weight: 700;
  font-size: clamp(2.4rem, 5vw, 3.4rem);
  line-height: 1;
  letter-spacing: -0.03em;
  margin: 0;
  color: var(--ink);
}

.hero-left h1 em {
  font-style: normal;
  color: var(--teal);
}

.hero-left p {
  margin: 12px 0 0;
  max-width: 34rem;
  font-size: 0.98rem;
  line-height: 1.55;
  color: var(--ink-dim);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border-radius: 999px;
  background: var(--panel);
  border: 1px solid var(--line);
  font-family: "JetBrains Mono", monospace;
  font-size: 0.76rem;
  color: var(--ink-dim);
  white-space: nowrap;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--good);
  box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.18);
  animation: pulse 2.4s ease-in-out infinite;
}

/* ---------------- Grid ---------------- */
.main-grid {
  display: grid !important;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr) !important;
  gap: 18px !important;
  align-items: stretch;
  animation: fade-up 800ms 100ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

@media (max-width: 880px) {
  .main-grid { grid-template-columns: minmax(0, 1fr) !important; }
}

.pane {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 18px;
  backdrop-filter: blur(18px) saturate(140%);
  display: flex !important;
  flex-direction: column !important;
  /* Gradio's own .column base style sets flex-wrap:wrap, which — combined
     with a constrained height — silently wraps overflowing children into an
     invisible second column instead of stacking/scrolling. Must force nowrap. */
  flex-wrap: nowrap !important;
}

.pane-title {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 2px 4px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pane-title .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.pane-title .dot.teal { background: var(--teal); }
.pane-title .dot.amber { background: var(--amber); }

/* ---------------- Chat pane ---------------- */
#chatbot {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  flex: 1;
  min-height: 360px;
}

#chatbot .message,
#chatbot .message-row {
  font-family: "Inter", sans-serif !important;
  font-size: 0.95rem !important;
  line-height: 1.6 !important;
}

#chatbot .user,
#chatbot .message.user {
  background: linear-gradient(135deg, rgba(94, 234, 212, 0.18), rgba(94, 234, 212, 0.08)) !important;
  border: 1px solid rgba(94, 234, 212, 0.25) !important;
  border-radius: 16px 16px 4px 16px !important;
  color: var(--ink) !important;
}

#chatbot .bot,
#chatbot .message.bot,
#chatbot .message.assistant {
  background: var(--panel-strong) !important;
  border: 1px solid var(--line) !important;
  border-radius: 16px 16px 16px 4px !important;
  color: var(--ink) !important;
}

/* Gradio's markdown renderer sets its own (light-theme) text color directly on
   <p>/<li>/etc and dims the wrapper to opacity:0.8 — both override the
   inherited color from .user/.bot above, since an element's own explicit
   color always wins over an inherited one regardless of ancestor !important.
   Must force color + full opacity at every descendant level. */
#chatbot .message-content,
#chatbot .message-content *,
#chatbot .prose,
#chatbot .prose *,
#chatbot .role {
  color: var(--ink) !important;
  opacity: 1 !important;
}

#chatbot a { color: var(--teal) !important; }
#chatbot strong { color: var(--ink) !important; font-weight: 600 !important; }
#chatbot code {
  background: rgba(255, 255, 255, 0.08) !important;
  color: var(--amber) !important;
}

#chatbot .placeholder,
#chatbot .empty {
  color: var(--ink-faint) !important;
}

.composer {
  margin-top: 14px;
  gap: 10px !important;
  align-items: stretch !important;
}

#inp, #inp textarea {
  background: rgba(255, 255, 255, 0.04) !important;
  border: 1px solid var(--line) !important;
  border-radius: 16px !important;
  color: var(--ink) !important;
  font-family: "Inter", sans-serif !important;
  font-size: 0.96rem !important;
  box-shadow: none !important;
  transition: border-color 180ms ease, background 180ms ease;
}

#inp textarea::placeholder { color: var(--ink-faint) !important; }

#inp textarea:focus {
  border-color: rgba(94, 234, 212, 0.55) !important;
  background: rgba(94, 234, 212, 0.05) !important;
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(94, 234, 212, 0.12) !important;
}

#send-btn {
  min-width: 118px !important;
  min-height: 54px !important;
  border-radius: 16px !important;
  border: none !important;
  background: linear-gradient(135deg, var(--teal), var(--teal-deep)) !important;
  color: #04140f !important;
  font-family: "Space Grotesk", sans-serif !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
  box-shadow: 0 8px 24px -8px rgba(20, 184, 166, 0.55) !important;
  transition: transform 160ms ease, box-shadow 160ms ease !important;
}

#send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px -6px rgba(20, 184, 166, 0.7) !important;
}

/* Examples */
.examples-label {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 14px 4px 8px;
}
.examples-row { gap: 8px !important; }
.example-chip {
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  color: var(--ink-dim) !important;
  font-family: "Inter", sans-serif !important;
  font-size: 0.82rem !important;
  font-weight: 400 !important;
  line-height: 1.45 !important;
  padding: 10px 14px !important;
  box-shadow: none !important;
  transition: all 160ms ease !important;
  white-space: normal !important;
  text-align: left !important;
  justify-content: flex-start !important;
  height: auto !important;
  width: 100% !important;
}
.example-chip:hover {
  border-color: rgba(94, 234, 212, 0.5) !important;
  color: var(--teal) !important;
  background: rgba(94, 234, 212, 0.06) !important;
}

/* ---------------- Console pane ---------------- */
/* .pane-console gets a hard, !important-pinned height so it can't collapse
   or get stretched to 0 by the CSS Grid row-sizing algorithm (a max-height
   without !important can lose to Gradio's own compiled component styles).
   #console-wrap is the flex child that actually scrolls: flex items default
   to min-height:auto (= their content size), which silently defeats
   overflow — min-height:0 is required to make the scroll work. */
.pane-console {
  height: 560px !important;
  max-height: 560px !important;
  overflow: hidden !important;
}

.tool-legend {
  flex: 0 0 auto !important;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

.tool-legend-title {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.66rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-right: 2px;
  flex: 0 0 100%;
}

.tool-chip {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  color: var(--teal);
  background: rgba(94, 234, 212, 0.08);
  border: 1px solid rgba(94, 234, 212, 0.22);
  border-radius: 999px;
  padding: 4px 10px;
}

#console-wrap {
  display: block !important;
  background: #05070d;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  padding: 16px 16px 4px;
  flex: 1 1 auto !important;
  width: 100%;
  height: auto !important;
  min-height: 0 !important;
  max-height: none !important;
  overflow-y: auto !important;
}

#console-wrap::-webkit-scrollbar { width: 8px; }
#console-wrap::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 8px;
}
#console-wrap::-webkit-scrollbar-track { background: transparent; }

.console-idle {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.85rem;
  color: var(--ink-faint);
  padding: 20px 4px;
}

.console-idle .cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  background: var(--teal);
  margin-left: 2px;
  animation: blink 1.1s step-end infinite;
  vertical-align: middle;
}

.console-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  color: var(--violet);
  background: rgba(167, 139, 250, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.25);
  border-radius: 999px;
  padding: 4px 10px;
  margin-bottom: 14px;
}

.console-turn { margin-bottom: 16px; }

.console-turn-title {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--line-soft);
}

.console-call {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.82rem;
  line-height: 1.55;
  margin-bottom: 10px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--line-soft);
  border-radius: 10px;
}

.console-call .call-line { color: var(--ink); word-break: break-word; }
.console-call .call-line .chevron { color: var(--teal); margin-right: 6px; }
.console-call .call-line .fn { color: var(--teal); font-weight: 600; }
.console-call .call-line .args { color: var(--ink-dim); }

.console-call .result-line {
  margin-top: 5px;
  color: var(--ink-dim);
  word-break: break-word;
  white-space: pre-wrap;
}
.console-call .result-line .chevron { color: var(--amber); margin-right: 6px; }
.console-call .result-line .json-key { color: var(--amber); }
.console-call .result-line .json-str { color: var(--teal); }
.console-call .result-line .json-num { color: var(--violet); }
.console-call .result-line .json-bool { color: var(--ink-faint); font-style: italic; }

.console-final {
  margin-top: 4px;
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.08), rgba(94, 234, 212, 0.04));
  border: 1px solid rgba(74, 222, 128, 0.22);
}

.console-final .console-turn-title {
  color: var(--good);
  border-bottom-color: rgba(74, 222, 128, 0.2);
}

.console-final .final-text {
  font-family: "Inter", sans-serif;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
}

/* ---------------- Accordion / schema ---------------- */
.gradio-container .label-wrap,
.gradio-container .label-wrap span,
.gradio-container .label-wrap button {
  font-family: "JetBrains Mono", monospace !important;
  font-size: 0.74rem !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: var(--ink-dim) !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.gradio-container .label-wrap svg { color: var(--ink-faint) !important; }

#raw-trace textarea {
  font-family: "JetBrains Mono", monospace !important;
  font-size: 0.78rem !important;
  background: #05070d !important;
  border: 1px solid var(--line-soft) !important;
  border-radius: 12px !important;
  color: var(--ink-dim) !important;
  box-shadow: none !important;
}

.docs-block {
  color: var(--ink-dim);
  font-size: 0.92rem;
  line-height: 1.6;
}
.docs-block a {
  color: var(--teal) !important;
  text-decoration: none;
  border-bottom: 1px solid rgba(94, 234, 212, 0.35);
}
.docs-block code {
  background: rgba(255, 255, 255, 0.06);
  color: var(--amber);
  border-radius: 4px;
  padding: 1px 5px;
}

.gradio-container h3 { color: var(--ink) !important; font-family: "Space Grotesk", sans-serif !important; }
.gradio-container strong code { color: var(--teal) !important; }

.footer-line {
  margin-top: 34px;
  text-align: center;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

@keyframes fade-up {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.18); }
  50% { box-shadow: 0 0 0 6px rgba(74, 222, 128, 0.05); }
}

@keyframes blink {
  50% { opacity: 0; }
}

@media (max-width: 640px) {
  #hero { padding-top: 28px; }
  .pane { padding: 14px; }
  #send-btn { min-width: 100% !important; }
  .composer { flex-direction: column !important; }
}
"""

IDLE_CONSOLE_HTML = """
<div class="console-idle">$ skybrief agent hazır — bir soru bekleniyor<span class="cursor"></span></div>
"""

EXAMPLE_QUERIES = [
    ["İstanbul'da bugün koşuya çıkılır mı? Hava kalitesi de önemli."],
    ["Tokyo ile Berlin'in önümüzdeki 3 günlük ufuk tahmini nasıl?"],
    ["Kapadokya (Nevşehir) için fotoğraf brifingi: UV, rüzgar ve açık hava uygunluğu?"],
    ["Antalya'da yarın piknik planı için kısa bir atmosfer brifingi ver."],
]


_JSON_TOKEN_RE = _re.compile(
    r'"(?:\\.|[^"\\])*"|-?\d+\.?\d*(?:[eE][+-]?\d+)?|true|false|null'
)


def _colorize_json(payload: dict) -> str:
    """Render a dict as compact JSON, tokenized and colorized for the console.

    Tokenizes the raw JSON text (strings/numbers/booleans) before escaping so
    numeric-looking substrings inside string values (e.g. ISO timestamps)
    never get misclassified as numbers.
    """
    raw = _json.dumps(payload, ensure_ascii=False)
    out: list[str] = []
    pos = 0
    for match in _JSON_TOKEN_RE.finditer(raw):
        out.append(_html.escape(raw[pos:match.start()]))
        token = match.group(0)
        lookahead = raw[match.end():match.end() + 2].lstrip()
        if token.startswith('"'):
            css_class = "json-key" if lookahead.startswith(":") else "json-str"
        elif token in ("true", "false", "null"):
            css_class = "json-bool"
        else:
            css_class = "json-num"
        out.append(f'<span class="{css_class}">{_html.escape(token)}</span>')
        pos = match.end()
    out.append(_html.escape(raw[pos:]))
    return "".join(out)


def render_console(result: AgentResponse) -> str:
    if not result.turns:
        message = _html.escape(result.final_answer or "Yanıt üretilemedi.")
        return (
            f'<div class="console-badge">mode · {_html.escape(result.mode)}</div>'
            f'<div class="console-final"><div class="console-turn-title">sonuç</div>'
            f'<div class="final-text">{message}</div></div>'
        )

    parts = [f'<div class="console-badge">mode · {_html.escape(result.mode)}</div>']

    for turn in result.turns:
        parts.append('<div class="console-turn">')
        parts.append(f'<div class="console-turn-title">turn {turn.index} · araç çağrıları</div>')
        for call in turn.calls:
            args_str = _html.escape(
                ", ".join(
                    f"{k}={v!r}" if isinstance(v, str) else f"{k}={v}"
                    for k, v in call.arguments.items()
                )
            )
            result_str = _colorize_json(call.result)
            parts.append(
                '<div class="console-call">'
                f'<div class="call-line"><span class="chevron">→</span>'
                f'<span class="fn">{_html.escape(call.name)}</span>'
                f'<span class="args">({args_str})</span></div>'
                f'<div class="result-line"><span class="chevron">←</span>{result_str}</div>'
                "</div>"
            )
        parts.append("</div>")

    final_text = _html.escape(result.final_answer or "").replace("\n", "<br>")
    parts.append(
        '<div class="console-final">'
        f'<div class="console-turn-title">turn {len(result.turns) + 1} · nihai yanıt</div>'
        f'<div class="final-text">{final_text}</div>'
        "</div>"
    )
    return "".join(parts)


def _schema_markdown() -> str:
    lines = ["### Tool / Function Definitions", ""]
    for item in TOOL_DEFINITIONS:
        fn = item["function"]
        lines.append(f"**`{fn['name']}`** — {fn['description']}")
        props = fn["parameters"].get("properties", {})
        req = set(fn["parameters"].get("required", []))
        for name, meta in props.items():
            mark = "required" if name in req else "optional"
            lines.append(
                f"- `{name}` ({meta.get('type', 'any')}, {mark}): {meta.get('description', '')}"
            )
        lines.append("")
    return "\n".join(lines)


def respond(message: str, history: list):
    result = run_agent(message)
    console_html = render_console(result)

    # gr.Chatbot (Gradio 5+/6) only accepts the "messages" format: a list of
    # {"role", "content"} dicts. The old tuple-of-lists format is rejected.
    history = (history or []) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": result.final_answer},
    ]

    return history, console_html, result.format_trace()


def build_ui() -> gr.Blocks:
    with gr.Blocks(css=CUSTOM_CSS, title="SkyBrief") as demo:
        gr.HTML(
            """
            <header id="hero">
              <div class="hero-left">
                <p class="kicker">Open-Meteo · Tool / Function Calling</p>
                <h1>Sky<em>Brief</em></h1>
                <p>
                  Konum çözümlemeden hava kalitesine, tahminden açık hava skoruna —
                  agent her adımını sağdaki konsolda canlı gösterir.
                </p>
              </div>
              <div class="status-pill">
                <span class="status-dot"></span>
                5 araç bağlı · anahtarsız API
              </div>
            </header>
            """
        )

        with gr.Row(elem_classes=["main-grid"]):
            with gr.Column(elem_classes=["pane", "pane-chat"]):
                gr.HTML(
                    '<div class="pane-title"><span class="dot teal"></span>sohbet</div>'
                )
                chatbot = gr.Chatbot(
                    show_label=False,
                    elem_id="chatbot",
                    height=360,
                    placeholder="Bir şehir veya karşılaştırma sorarak başlayın.",
                )
                with gr.Row(elem_classes=["composer"]):
                    inp = gr.Textbox(
                        show_label=False,
                        placeholder="Örn: Trabzon'da yarın yürüyüş için hava ve AQI nasıl?",
                        scale=5,
                        lines=2,
                        elem_id="inp",
                        container=False,
                    )
                    send = gr.Button("Sor →", elem_id="send-btn", scale=1)

                gr.HTML('<div class="examples-label">≡ örnekler</div>')
                with gr.Column(elem_classes=["examples-row"]):
                    for example_text, in EXAMPLE_QUERIES:
                        example_btn = gr.Button(
                            example_text, elem_classes=["example-chip"]
                        )
                        example_btn.click(
                            lambda text=example_text: text, outputs=[inp]
                        )

            with gr.Column(elem_classes=["pane", "pane-console"]):
                gr.HTML(
                    '<div class="pane-title"><span class="dot amber"></span>araç konsolu — canlı</div>'
                )
                console = gr.HTML(IDLE_CONSOLE_HTML, elem_id="console-wrap")
                gr.HTML(
                    """
<div class="tool-legend">
  <span class="tool-legend-title">kayıtlı araçlar</span>
  <span class="tool-chip">resolve_location</span>
  <span class="tool-chip">get_atmosphere_snapshot</span>
  <span class="tool-chip">get_horizon_forecast</span>
  <span class="tool-chip">get_air_quality_index</span>
  <span class="tool-chip">rank_outdoor_viability</span>
</div>
                    """
                )

        with gr.Accordion("Ham iz (kopyalanabilir)", open=False):
            raw_trace = gr.Textbox(show_label=False, lines=10, elem_id="raw-trace")

        with gr.Accordion("Şemalar ve veri kaynağı", open=False):
            gr.Markdown(
                """
<div class="docs-block">

Veri: <a href="https://open-meteo.com/">Open-Meteo</a> Geocoding + Forecast + Air Quality — API anahtarı gerekmez.

İsteğe bağlı LLM tool-calling: Space secrets içine <code>GROQ_API_KEY</code> eklenirse gerçek function-calling devreye girer; yoksa çok adımlı çevrimdışı planlayıcı aynı araçları çağırır.

</div>
                """,
                elem_classes=["docs-block"],
            )
            gr.Markdown(_schema_markdown())

        gr.HTML('<p class="footer-line">SkyBrief · tool-calling weather agent</p>')

        send.click(
            respond,
            inputs=[inp, chatbot],
            outputs=[chatbot, console, raw_trace],
        ).then(lambda: "", outputs=[inp])
        inp.submit(
            respond,
            inputs=[inp, chatbot],
            outputs=[chatbot, console, raw_trace],
        ).then(lambda: "", outputs=[inp])

    return demo


demo = build_ui()

if __name__ == "__main__":
    demo.launch()
