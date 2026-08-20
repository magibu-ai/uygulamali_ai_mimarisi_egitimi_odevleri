"""
Tool Calling Demo — Saat Dilimi Farkı
=====================================

Bir LLM'in kullanıcı sorusuna göre doğru fonksiyonları (Tool / Function
Calling) çağırmasını sağlayan, timeapi.io (ücretsiz, anahtarsız) API'sinden
gerçek veri çeken ve çağrılan araçları arayüzde açıkça gösteren bir uygulama.

Araçlar:
  - get_current_time(timezone)                 -> o an ilgili zaman diliminde saat + UTC farkı
  - time_difference(timezone1, timezone2)      -> iki zaman dilimi arasındaki saat farkı

Not: timeapi.io'ya ulaşılamazsa Python'un yerleşik `zoneinfo` (IANA veritabanı)
kütüphanesine otomatik düşülür; böylece demo her koşulda çalışır.

Model: Hugging Face Inference Providers üzerinden tool-calling destekli bir
sohbet modeli (varsayılan: openai/gpt-oss-120b).
"""

import os
import json
from datetime import datetime

import requests
import gradio as gr
from huggingface_hub import InferenceClient

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # çok eski sürümler için
    ZoneInfo = None

# ---------------------------------------------------------------------------
# ZeroGPU uyumluluğu
# ---------------------------------------------------------------------------
# HF Spaces ZeroGPU donanımı, başlatılabilmek için en az bir @spaces.GPU
# fonksiyonu ister. Bu uygulama GPU kullanmaz (yalnızca API çağırır); aşağıdaki
# fonksiyon sadece ZeroGPU'nun başlatma kontrolünü geçmek için vardır.
try:
    import spaces

    @spaces.GPU
    def _zerogpu_warmup():
        return True
except Exception:
    pass
  
MODEL_ID = os.environ.get("MODEL_ID", "openai/gpt-oss-120b")
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
HF_PROVIDER = os.environ.get("HF_PROVIDER", "auto")
MAX_TURNS = 6  # Sonsuz döngüye karşı üst sınır

_client_kwargs = {"model": MODEL_ID, "token": HF_TOKEN}
if HF_PROVIDER:
    _client_kwargs["provider"] = HF_PROVIDER
client = InferenceClient(**_client_kwargs)

TIMEAPI_BASE = "https://timeapi.io/api"

def _fetch_zone(timezone: str) -> dict:
    """
    Önce yerel IANA veritabanından (anlık ve doğru) hesaplar; bu mümkün değilse
    timeapi.io public API'sine düşer.
    Döner: {"timezone", "local_time", "utc_offset_hours"}
    """
    if ZoneInfo is not None:
        try:
            now = datetime.now(ZoneInfo(timezone))
            return {
                "timezone": timezone,
                "local_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "utc_offset_hours": round(now.utcoffset().total_seconds() / 3600, 2),
                "source": "zoneinfo (yerel)",
            }
        except Exception:
            pass  # geçersiz timezone olabilir -> API'yi dene

   
    try:
        r = requests.get(
            f"{TIMEAPI_BASE}/timezone/zone",
            params={"timeZone": timezone},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        offset_sec = data["currentUtcOffset"]["seconds"]
        local_raw = data.get("currentLocalTime", "")
        # "2026-07-30T15:30:00.123" -> "2026-07-30 15:30:00"
        local_time = local_raw.replace("T", " ").split(".")[0]
        return {
            "timezone": data.get("timeZone", timezone),
            "local_time": local_time,
            "utc_offset_hours": round(offset_sec / 3600, 2),
            "source": "timeapi.io",
        }
    except Exception:
        pass

    return {"error": f"'{timezone}' geçerli bir IANA zaman dilimi değil (örn. 'Europe/Istanbul')."}

def get_current_time(timezone: str) -> dict:
    """Belirtilen IANA zaman diliminde güncel saati ve UTC farkını döndürür."""
    return _fetch_zone(timezone)


def time_difference(timezone1: str, timezone2: str) -> dict:
    """İki IANA zaman dilimi arasındaki saat farkını hesaplar."""
    z1 = _fetch_zone(timezone1)
    z2 = _fetch_zone(timezone2)
    if "error" in z1:
        return z1
    if "error" in z2:
        return z2

    diff = round(z2["utc_offset_hours"] - z1["utc_offset_hours"], 2)
    if diff > 0:
        note = f"{z2['timezone']}, {z1['timezone']}'dan {abs(diff)} saat ileridedir."
    elif diff < 0:
        note = f"{z2['timezone']}, {z1['timezone']}'dan {abs(diff)} saat geridedir."
    else:
        note = f"{z1['timezone']} ve {z2['timezone']} aynı saat dilimindedir."

    return {
        "timezone1": z1["timezone"],
        "timezone2": z2["timezone"],
        "difference_hours": diff,
        "note": note,
    }


TOOL_FUNCS = {
    "get_current_time": get_current_time,
    "time_difference": time_difference,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "Belirtilen zaman diliminde o anki yerel saati ve UTC farkını "
                "döndürür."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": (
                            "IANA zaman dilimi kimliği, örn. 'Europe/Istanbul', "
                            "'America/New_York', 'Asia/Tokyo'. Kullanıcı şehir adı "
                            "verirse uygun IANA kimliğine çevir."
                        ),
                    }
                },
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "time_difference",
            "description": "İki zaman dilimi arasındaki saat farkını hesaplar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone1": {
                        "type": "string",
                        "description": "Birinci IANA zaman dilimi, örn. 'America/New_York'.",
                    },
                    "timezone2": {
                        "type": "string",
                        "description": "İkinci IANA zaman dilimi, örn. 'Asia/Tokyo'.",
                    },
                },
                "required": ["timezone1", "timezone2"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Sen araç kullanabilen yardımcı bir asistansın. Saat ve zaman dilimi "
    "sorularında ASLA bilgi uydurma; her zaman verilen araçları "
    "(get_current_time, time_difference) çağırarak gerçek verilere ulaş. "
    "Kullanıcı şehir adı verirse ('New York', 'Tokyo', 'İstanbul'), bunu doğru "
    "IANA zaman dilimi kimliğine çevir (örn. 'America/New_York', 'Asia/Tokyo', "
    "'Europe/Istanbul'). Birden fazla yer sorulduğunda her biri için ayrı araç "
    "çağır. Son yanıtını kullanıcının diliyle, kısa ve net ver."
)


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def run_agent(user_message: str, history_messages: list):
    """Modeli araçlarla çalıştırır. (nihai_yanit, adim_izi) döner."""
    if not HF_TOKEN:
        return (
            "⚠️ HF_TOKEN ayarlı değil. HF Spaces > Settings > Secrets bölümünden "
            "`HF_TOKEN` ekleyin (huggingface.co/settings/tokens).",
            "",
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history_messages)
    messages.append({"role": "user", "content": user_message})

    trace_lines = []

    for turn in range(1, MAX_TURNS + 1):
        try:
            resp = client.chat_completion(
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.2,
            )
        except Exception as exc:
            return f"Model çağrısı başarısız oldu: {exc}", "\n".join(trace_lines)

        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            final = msg.content or "(boş yanıt)"
            if trace_lines:
                trace_lines.append(f"\n[Turn {turn}] Nihai Yanıt:")
                trace_lines.append(final)
            return final, "\n".join(trace_lines)

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        trace_lines.append(f"[Turn {turn}] Araç Çağrıları:")
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            func = TOOL_FUNCS.get(name)
            result = func(**args) if func else {"error": f"Bilinmeyen araç: {name}"}

            trace_lines.append(f"   -> {name}({_fmt_args(args)})")
            trace_lines.append(f"   <- {result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return "Adım sınırına ulaşıldı, yanıt tamamlanamadı.", "\n".join(trace_lines)


def respond(message, chat_history):
    history_messages = [
        {"role": t["role"], "content": t["content"]} for t in chat_history
    ]
    final, trace = run_agent(message, history_messages)
    chat_history = chat_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": final},
    ]
    return chat_history, trace, ""


with gr.Blocks(title="Tool Calling — Saat Dilimi Farkı") as demo:
    gr.Markdown(
        "# 🕐 Tool Calling Demo — Saat Dilimi Farkı\n"
        "Model, sorunuza göre **`get_current_time`** ve **`time_difference`** "
        "araçlarını otomatik çağırır. Sağ tarafta arka planda çağrılan araçları "
        "ve adımları görebilirsiniz.\n\n"
        f"**Model:** `{MODEL_ID}` · **Veri kaynağı:** timeapi.io"
    )

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=420, label="Sohbet")
            msg = gr.Textbox(
                placeholder="Örn: New York ile Tokyo arasında kaç saat fark var, şu an saat kaç?",
                label="Sorunuz",
            )
            with gr.Row():
                send = gr.Button("Gönder", variant="primary")
                clear = gr.Button("Temizle")
        with gr.Column(scale=2):
            trace_box = gr.Textbox(
                label="🔧 Araç Çağrı Adımları (Tool Trace)",
                lines=22,
                interactive=False,
            )

    gr.Examples(
        examples=[
            "New York ile Tokyo arasında kaç saat fark var, şu an oralarda saat kaç?",
            "İstanbul'da şu an saat kaç?",
            "Londra mı ileride Los Angeles mı, aradaki fark nedir?",
            "Sidney ile Berlin arasındaki saat farkı kaç saat?",
        ],
        inputs=msg,
    )

    send.click(respond, [msg, chatbot], [chatbot, trace_box, msg])
    msg.submit(respond, [msg, chatbot], [chatbot, trace_box, msg])
    clear.click(lambda: ([], "", ""), None, [chatbot, trace_box, msg])


if __name__ == "__main__":
    demo.launch()
