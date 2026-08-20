"""
ayarlicazhocam-tool-agent
=========================
Gemma-4-12B (Gemini API üzerinden) + Open-Meteo public API ile Tool / Function
Calling yapan, Hugging Face Spaces'te canlıya alınan bir Gradio uygulaması.

Mimari:
    Kullanıcı (Gradio chat)
      -> google-genai SDK -> Gemma-4 (Gemini API)
           system_instruction: ayarlicazhocam persona
           tools: [get_weather, convert_temperature]
      -> model function_call döndürür
      -> Python tarafında gerçek Open-Meteo isteği (tools.py)
      -> function_response olarak modele geri verilir
      -> model nihai doğal dil cevabını üretir
      -> Gradio ekranında hem tool-call trace'i hem nihai cevap gösterilir

ayarlicazhocam ekosistemi:
    - ayarlicazhocam-training : kimlik/persona (LoRA fine-tune)
    - mihenk-benchmark        : akıl yürütme ölçümü
    - ayarlicazhocam-tool-agent (bu repo) : dış dünyayla etkileşim
"""

from __future__ import annotations

import json
import os
import re
import time

import gradio as gr
from google import genai
from google.genai import types

from tools import ToolError, dispatch

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # HF Spaces'te secrets ortam değişkeni olarak gelir
    pass


# --------------------------------------------------------------------------- #
# Persona (system_instruction)
# --------------------------------------------------------------------------- #
PERSONA = (
    "Sen ayarlicazhocam'sın: sakin, net ve biraz esprili bir kişisel yapay zeka "
    "asistanı. Türkçe konuşursun. Artık gerçek zamanlı verilere erişebiliyorsun: "
    "elindeki araçlarla güncel hava durumunu çekebilir ve sıcaklık birimi "
    "çevirebilirsin. Bir soruyu yanıtlamak için gerçek veriye ihtiyaç varsa "
    "uygun aracı çağır; asla veri uydurma. Araçlardan dönen sonuçları yorumlayıp "
    "kullanıcıya sade, anlaşılır bir dille aktar. Birden fazla şehir ya da çevrim "
    "gerekiyorsa gerekli araçları sırayla çağır."
)


# --------------------------------------------------------------------------- #
# Araç şemaları — tipli FunctionDeclaration (elle JSON string yazmaktan güvenli)
# --------------------------------------------------------------------------- #
GET_WEATHER_DECL = types.FunctionDeclaration(
    name="get_weather",
    description=(
        "Belirtilen şehrin GÜNCEL hava durumunu getirir (sıcaklık Celsius, nem, "
        "rüzgâr, genel durum). Open-Meteo public API kullanır."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(
                type=types.Type.STRING,
                description="Hava durumu istenen şehir adı, örn. 'Ankara' veya 'Londra'.",
            ),
        },
        required=["city"],
    ),
)

CONVERT_TEMPERATURE_DECL = types.FunctionDeclaration(
    name="convert_temperature",
    description=(
        "Bir sıcaklık değerini hedef birime çevirir. to_unit='F' ise değer Celsius "
        "kabul edilip Fahrenheit'a; to_unit='C' ise Fahrenheit kabul edilip "
        "Celsius'a çevrilir."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "value": types.Schema(
                type=types.Type.NUMBER,
                description="Çevrilecek sıcaklık değeri.",
            ),
            "to_unit": types.Schema(
                type=types.Type.STRING,
                enum=["C", "F"],
                description="Hedef birim: 'C' (Celsius) veya 'F' (Fahrenheit).",
            ),
        },
        required=["value", "to_unit"],
    ),
)

TOOLS = types.Tool(function_declarations=[GET_WEATHER_DECL, CONVERT_TEMPERATURE_DECL])

MAX_TOOL_ROUNDS = 6  # sonsuz döngü koruması


# --------------------------------------------------------------------------- #
# Client & model çözümleme
# --------------------------------------------------------------------------- #
_client: genai.Client | None = None
_model_id: str | None = None
_supports_system_instruction = True  # Gemma bazı sürümlerde desteklemeyebilir


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY bulunamadı. Local'de .env dosyasına, HF Space'te "
                "Settings > Secrets bölümüne ekleyin."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def resolve_model_id() -> str:
    """Model ID'yi hardcode etmeden, Gemini API'nin canlı listesinden çözer.

    Öncelik sırası:
      1) MODEL_ID ortam değişkeni (elle sabitleme)
      2) Canlı listede generateContent destekleyen bir Gemma-4 ~12B modeli
      3) Canlı listede herhangi bir Gemma-4 modeli
    Bulunamazsa, mevcut Gemma modellerini listeleyen açıklayıcı bir hata verir.
    """
    global _model_id
    if _model_id:
        return _model_id

    override = os.environ.get("MODEL_ID")
    if override:
        _model_id = override
        return _model_id

    client = get_client()
    available = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions or not actions:
            available.append(m.name)  # örn. "models/gemma-4-12b-it"

    def short(n: str) -> str:
        return n.split("/")[-1]

    gemma4 = [n for n in available if re.search(r"gemma-?4", short(n), re.I)]
    # Tercih sırası: seçilen model (26b-a4b MoE) -> 12B -> herhangi instruction-tuned -> herhangi Gemma-4.
    # (gemma-4-12b-it Gemini API'de sunulmuyor; canlı listeden en uygun mevcut model seçilir.)
    pref = [n for n in gemma4 if re.search(r"a4b", short(n), re.I) and short(n).endswith("it")]
    pref = pref or [n for n in gemma4 if re.search(r"12b", short(n), re.I) and short(n).endswith("it")]
    pref = pref or [n for n in gemma4 if re.search(r"12b", short(n), re.I)]
    pref = pref or [n for n in gemma4 if short(n).endswith("it")]
    pref = pref or gemma4

    if not pref:
        gemmas = sorted(short(n) for n in available if "gemma" in short(n).lower())
        raise RuntimeError(
            "Uygun bir Gemma-4 modeli bulunamadı. Bu API anahtarıyla erişilebilen "
            f"Gemma modelleri: {gemmas or 'yok'}. MODEL_ID ortam değişkeniyle elle "
            "belirtebilirsiniz."
        )

    _model_id = short(pref[0])
    return _model_id


# --------------------------------------------------------------------------- #
# Model çağrısı (system_instruction desteklenmezse persona'yı enjekte eden yedek)
# --------------------------------------------------------------------------- #
def _call_api(model_id: str, contents: list, config) -> types.GenerateContentResponse:
    """Geçici hatalarda (503/UNAVAILABLE, 429) kısa exponential backoff ile retry."""
    client = get_client()
    delay = 2.0
    last_exc = None
    for attempt in range(4):
        try:
            return client.models.generate_content(model=model_id, contents=contents, config=config)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            transient = (
                "unavailable" in msg
                or "503" in msg
                or "500" in msg
                or "internal" in msg
                or "429" in msg
                or "overloaded" in msg
                or "resource" in msg  # RESOURCE_EXHAUSTED
            )
            if not transient or attempt == 3:
                raise
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    raise last_exc  # ulaşılmaz ama tip güvenliği için


def _generate(contents: list) -> types.GenerateContentResponse:
    global _supports_system_instruction
    model_id = resolve_model_id()

    base_kwargs = dict(
        tools=[TOOLS],
        temperature=0.2,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    if _supports_system_instruction:
        try:
            cfg = types.GenerateContentConfig(system_instruction=PERSONA, **base_kwargs)
            return _call_api(model_id, contents, cfg)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "system" in msg and "instruction" in msg:
                # Gemma bu model üzerinde system_instruction desteklemiyor -> yedek yola geç
                _supports_system_instruction = False
            else:
                raise

    # Yedek: persona'yı ilk kullanıcı turu olarak enjekte et
    cfg = types.GenerateContentConfig(**base_kwargs)
    injected = [
        types.Content(role="user", parts=[types.Part(text=PERSONA)]),
        types.Content(role="model", parts=[types.Part(text="Anladım, hazırım.")]),
    ] + contents
    return _call_api(model_id, injected, cfg)


# --------------------------------------------------------------------------- #
# Argüman doğrulama (execute etmeden önce tip/format kontrolü)
# --------------------------------------------------------------------------- #
def validate_args(name: str, args: dict) -> dict:
    args = dict(args or {})
    if name == "get_weather":
        city = args.get("city")
        if not isinstance(city, str) or not city.strip():
            raise ToolError("get_weather: 'city' boş olmayan bir metin olmalı.")
        return {"city": city.strip()}
    if name == "convert_temperature":
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            raise ToolError("convert_temperature: 'value' sayısal olmalı.")
        to_unit = str(args.get("to_unit", "")).strip().upper()
        if to_unit not in ("C", "F"):
            raise ToolError("convert_temperature: 'to_unit' 'C' veya 'F' olmalı.")
        return {"value": value, "to_unit": to_unit}
    raise ToolError(f"Bilinmeyen araç: {name}")


# --------------------------------------------------------------------------- #
# Tool-call trace mesajını (Gradio metadata ile açılır/kapanır) biçimlendir
# --------------------------------------------------------------------------- #
def _trace_message(turn: int, name: str, args: dict, result: dict, ok: bool) -> dict:
    status = "✅" if ok else "⚠️"
    args_json = json.dumps(args, ensure_ascii=False)
    result_json = json.dumps(result, ensure_ascii=False, indent=2)
    content = (
        f"**Fonksiyon:** `{name}`\n\n"
        f"**Argümanlar:** `{args_json}`\n\n"
        f"**Sonuç:**\n```json\n{result_json}\n```"
    )
    return {
        "role": "assistant",
        "content": content,
        "metadata": {"title": f"{status} [Turn {turn}] Araç Çağrısı: {name}"},
    }


# --------------------------------------------------------------------------- #
# Ana sohbet döngüsü (Gradio generator — adımları canlı gösterir)
# --------------------------------------------------------------------------- #
def chat_fn(user_msg: str, history: list, contents: list):
    """history: Gradio Chatbot mesajları (görüntü). contents: genai konuşma durumu."""
    user_msg = (user_msg or "").strip()
    if not user_msg:
        yield history, contents
        return

    history = history + [{"role": "user", "content": user_msg}]
    contents = contents + [types.Content(role="user", parts=[types.Part(text=user_msg)])]
    yield history, contents

    turn = 0
    try:
        while True:
            turn += 1
            if turn > MAX_TOOL_ROUNDS:
                history = history + [
                    {"role": "assistant", "content": "_(Araç çağrısı sınırına ulaşıldı.)_"}
                ]
                yield history, contents
                return

            response = _generate(contents)
            model_content = response.candidates[0].content
            contents = contents + [model_content]

            function_calls = response.function_calls or []

            if not function_calls:
                final_text = response.text or "_(Model boş yanıt döndürdü.)_"
                history = history + [{"role": "assistant", "content": final_text}]
                yield history, contents
                return

            # Bu turdaki tüm tool call'ları sırayla işle
            fr_parts = []
            for fc in function_calls:
                try:
                    clean_args = validate_args(fc.name, dict(fc.args or {}))
                    result = dispatch(fc.name, clean_args)
                    ok = True
                except ToolError as te:
                    clean_args = dict(fc.args or {})
                    result = {"error": str(te)}
                    ok = False
                except Exception as exc:  # noqa: BLE001  (ağ/HTTP hataları vb.)
                    clean_args = dict(fc.args or {})
                    result = {"error": f"Araç çalıştırılamadı: {exc}"}
                    ok = False

                history = history + [_trace_message(turn, fc.name, clean_args, result, ok)]
                yield history, contents

                fr_parts.append(
                    types.Part.from_function_response(name=fc.name, response={"result": result})
                )

            # Tüm function_response'ları modele geri gönder
            contents = contents + [types.Content(role="user", parts=fr_parts)]

    except Exception as exc:  # noqa: BLE001
        history = history + [{"role": "assistant", "content": f"⚠️ Hata: {exc}"}]
        yield history, contents
        return


# --------------------------------------------------------------------------- #
# Gradio arayüzü
# --------------------------------------------------------------------------- #
EXAMPLE_QUERIES = [
    "Ankara mı daha sıcak Londra mı? Ve farkı Fahrenheit olarak kaç eder?",
    "İstanbul'da hava nasıl?",
    "25 dereceyi Fahrenheit'a çevirir misin?",
    "Tokyo ve New York'ta şu an sıcaklık kaç derece?",
]


def _make_chatbot() -> gr.Chatbot:
    """Chatbot'u sürümden bağımsız kur (Gradio 5: type='messages' gerekli;
    Gradio 6: messages varsayılan, 'type' argümanı kaldırıldı)."""
    import inspect

    height = int(os.environ.get("CHATBOT_HEIGHT", "520"))
    kwargs = dict(height=height, label="ayarlicazhocam", render_markdown=True)
    if "type" in inspect.signature(gr.Chatbot.__init__).parameters:
        kwargs["type"] = "messages"
    return gr.Chatbot(**kwargs)


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="ayarlicazhocam · Tool Agent") as demo:
        gr.Markdown(
            "# 🎓 ayarlicazhocam · Tool Agent\n"
            "Gemma-4 (Gemini API) + **Open-Meteo** public API ile canlı hava "
            "durumu ve sıcaklık çevrimi. Her yanıtın altında modelin arka planda "
            "hangi araçları hangi argümanlarla çağırdığını görebilirsin.\n\n"
            "*Ekosistem: ayarlicazhocam-training (persona) · mihenk-benchmark "
            "(akıl yürütme) · **ayarlicazhocam-tool-agent** (dış dünya).*"
        )

        chatbot = _make_chatbot()
        contents_state = gr.State([])

        with gr.Row():
            txt = gr.Textbox(
                placeholder="Bir şey sor... (örn. 'Ankara mı sıcak Londra mı?')",
                scale=9,
                show_label=False,
                autofocus=True,
            )
            send_btn = gr.Button("Gönder", variant="primary", scale=1)

        gr.Examples(examples=EXAMPLE_QUERIES, inputs=txt)
        clear_btn = gr.Button("🗑️ Sohbeti temizle")

        # Event bağlantıları
        def _clear():
            return [], []

        send_event = send_btn.click(
            chat_fn, [txt, chatbot, contents_state], [chatbot, contents_state]
        )
        submit_event = txt.submit(
            chat_fn, [txt, chatbot, contents_state], [chatbot, contents_state]
        )
        # Gönderdikten sonra input'u temizle
        send_event.then(lambda: "", None, txt)
        submit_event.then(lambda: "", None, txt)

        clear_btn.click(_clear, None, [chatbot, contents_state])

    return demo


if __name__ == "__main__":
    build_demo().launch()
