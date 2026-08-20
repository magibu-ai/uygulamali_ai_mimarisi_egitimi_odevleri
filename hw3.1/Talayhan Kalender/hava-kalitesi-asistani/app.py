"""
Tool Calling Ödevi — Hava Kalitesi Asistanı
--------------------------------------------
Public API: OpenAQ v3 (https://api.openaq.org) — dünya çapında gerçek zamanlı
            hava kirliliği ölçüm verisi sunan açık, resmi bir platform.
            NOT: OpenAQ v3, ücretsiz ama KAYIT gerektiren bir API key kullanır
            (bkz. README "OpenAQ API Key Alma" bölümü).
Yardımcı:   Open-Meteo Geocoding API (key gerektirmez) — şehir ismini
            enlem/boylama çevirmek için kullanılır (OpenAQ konum bazlı
            sorgu yapıyor, şehir ismiyle direkt aramıyor).

Model: Hugging Face Inference Providers üzerinden "openai/gpt-oss-120b"
       (OpenAI-uyumlu chat completions endpoint'i, tool calling destekli)

Arayüz: Gradio, Hugging Face Spaces'e deploy edilecek şekilde tasarlandı.
"""

import os
import json
import requests
import gradio as gr
from openai import OpenAI

# ---------------------------------------------------------------------------
# 1) MODEL CLIENT
# ---------------------------------------------------------------------------
# HF Space "Settings -> Repository secrets" kısmına HF_TOKEN eklenmelidir.
HF_TOKEN = os.environ.get("HF_TOKEN")
# OpenAQ ücretsiz ama key gerektirir: https://explore.openaq.org/register
OPENAQ_API_KEY = os.environ.get("OPENAQ_API_KEY")

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN,
)

MODEL_ID = "openai/gpt-oss-120b"

SYSTEM_PROMPT = (
    "Sen yardımsever bir hava kalitesi asistanısın. Hava kalitesiyle ilgili "
    "sorularda mutlaka sana verilen tool'ları (get_air_quality, interpret_aqi) "
    "kullan. Tool sonucu gelmeden asla veri uydurma. get_air_quality bir şehrin "
    "PM2.5 değerini µg/m³ cinsinden döndürür; bu değeri yorumlamak istediğinde "
    "interpret_aqi tool'unu çağır. Tüm tool sonuçları elinde olduğunda "
    "kullanıcıya net, kısa bir özet ver."
)

# ---------------------------------------------------------------------------
# 2) PUBLIC API'Yİ SARAN GERÇEK FONKSİYONLAR
# ---------------------------------------------------------------------------

OPENAQ_BASE_URL = "https://api.openaq.org/v3"


def _geocode_city(city: str) -> dict:
    """Open-Meteo Geocoding API (key gerektirmez) ile şehir ismini
    enlem/boylama çevirir. OpenAQ konum bazlı (coordinates+radius) sorgu
    yaptığı için bu ara adım gereklidir."""
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    resp = requests.get(geo_url, params={"name": city, "count": 1, "language": "tr"}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        return None
    result = data["results"][0]
    return {
        "lat": result["latitude"],
        "lon": result["longitude"],
        "name": result.get("name", city),
        "country": result.get("country", ""),
    }


def get_air_quality(city: str) -> dict:
    """OpenAQ v3 API'sini kullanarak bir şehre en yakın istasyondaki güncel
    PM2.5 (ince partikül madde) ölçümünü döndürür.

    Akış:
      1) Open-Meteo ile şehir -> (lat, lon)
      2) GET /v3/locations?coordinates=lat,lon&radius=25000  -> yakın istasyonlar
      3) PM2.5 sensörü olan ilk istasyonu seç
      4) GET /v3/locations/{id}/latest -> o istasyondaki en güncel ölçümler
      5) sensorsId eşleştirerek PM2.5 değerini bul
    """
    if not OPENAQ_API_KEY:
        return {"error": "OPENAQ_API_KEY tanımlı değil. README'deki kurulum adımlarına bakın."}

    geo = _geocode_city(city)
    if geo is None:
        return {"error": f"'{city}' için konum bulunamadı."}

    headers = {"X-API-Key": OPENAQ_API_KEY}

    # 2) Yakındaki istasyonları bul (nokta + yarıçap sorgusu, max 25km)
    loc_resp = requests.get(
        f"{OPENAQ_BASE_URL}/locations",
        headers=headers,
        params={
            "coordinates": f"{geo['lat']},{geo['lon']}",
            "radius": 25000,
            "limit": 10,
        },
        timeout=10,
    )
    loc_resp.raise_for_status()
    locations = loc_resp.json().get("results", [])

    if not locations:
        return {"error": f"'{geo['name']}' yakınında (25 km içinde) hava kalitesi istasyonu bulunamadı."}

    # En yakın mesafeye göre sırala (distance alanı metre cinsindendir)
    locations.sort(key=lambda l: l.get("distance") or float("inf"))

    # 3) PM2.5 sensörü olan ilk istasyonu bul
    for loc in locations:
        pm25_sensor = next(
            (s for s in loc.get("sensors", []) if s.get("parameter", {}).get("name") == "pm25"),
            None,
        )
        if pm25_sensor is None:
            continue

        # 4) O istasyonun en güncel ölçümlerini çek
        latest_resp = requests.get(
            f"{OPENAQ_BASE_URL}/locations/{loc['id']}/latest",
            headers=headers,
            timeout=10,
        )
        latest_resp.raise_for_status()
        latest_results = latest_resp.json().get("results", [])

        # 5) sensorsId eşleştir
        reading = next((r for r in latest_results if r.get("sensorsId") == pm25_sensor["id"]), None)
        if reading is None:
            continue

        return {
            "city": geo["name"],
            "station": loc.get("name"),
            "distance_km": round((loc.get("distance") or 0) / 1000, 1),
            "pm25_ugm3": reading["value"],
            "unit": pm25_sensor["parameter"]["units"],
            "measured_at_utc": reading["datetime"]["utc"],
        }

    return {"error": f"'{geo['name']}' yakınındaki istasyonlarda PM2.5 verisi bulunamadı."}


def interpret_aqi(pm25_ugm3: float) -> dict:
    """Bir PM2.5 (µg/m³) değerini ABD EPA AQI kategorilerine göre
    (basitleştirilmiş) yorumlar. Bu fonksiyon API çağırmaz; saf hesaplamadır."""
    value = float(pm25_ugm3)

    # ABD EPA PM2.5 24 saatlik AQI eşikleri (basitleştirilmiş)
    breakpoints = [
        (0, 12.0, "İyi", "Hava kalitesi tatmin edici, dışarıda aktivite güvenli."),
        (12.1, 35.4, "Orta", "Hassas gruplar (astım, kalp/akciğer hastası) uzun süreli dış mekan aktivitesini sınırlamalı."),
        (35.5, 55.4, "Hassas Gruplar İçin Sağlıksız", "Çocuklar, yaşlılar ve solunum hastaları dışarıda yoğun aktiviteden kaçınmalı."),
        (55.5, 150.4, "Sağlıksız", "Herkes dışarıdaki uzun/yoğun aktiviteyi azaltmalı."),
        (150.5, 250.4, "Çok Sağlıksız", "Dışarı çıkışları en aza indirin, mümkünse maske kullanın."),
        (250.5, 500.4, "Tehlikeli", "Dışarı çıkmaktan kaçının, pencereleri kapalı tutun."),
    ]

    for low, high, category, advice in breakpoints:
        if low <= value <= high:
            return {"pm25_ugm3": value, "category": category, "advice": advice}

    return {"pm25_ugm3": value, "category": "Tehlikeli (ölçek dışı)", "advice": "Dışarı çıkmaktan kaçının."}


AVAILABLE_FUNCTIONS = {
    "get_air_quality": get_air_quality,
    "interpret_aqi": interpret_aqi,
}

# ---------------------------------------------------------------------------
# 3) TOOL / FUNCTION ŞEMALARI (OpenAI-uyumlu JSON Schema formatı)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_air_quality",
            "description": (
                "Verilen bir şehre en yakın OpenAQ istasyonundaki güncel PM2.5 "
                "(ince partikül madde) hava kirliliği ölçümünü µg/m³ cinsinden döndürür."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava kalitesi sorgulanacak şehir adı, örn. 'İstanbul' veya 'Berlin'",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interpret_aqi",
            "description": (
                "Bir PM2.5 değerini (µg/m³) ABD EPA hava kalitesi kategorilerine göre "
                "yorumlar ve sağlık tavsiyesi döndürür."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pm25_ugm3": {
                        "type": "number",
                        "description": "Yorumlanacak PM2.5 değeri (µg/m³ cinsinden)",
                    }
                },
                "required": ["pm25_ugm3"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# 4) TOOL-CALLING DÖNGÜSÜ (model <-> fonksiyonlar arası çok turlu iletişim)
# ---------------------------------------------------------------------------

def run_agent(user_message: str, max_turns: int = 5):
    if not HF_TOKEN:
        return (
            "⚠️ HF_TOKEN tanımlı değil. Lütfen Hugging Face Space secrets kısmına "
            "HF_TOKEN ekleyin (Settings -> Variables and secrets -> New secret).",
            "",
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    trace_lines = []
    turn = 0
    final_answer = ""

    while turn < max_turns:
        turn += 1
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0].message

        if not choice.tool_calls:
            final_answer = choice.content or ""
            messages.append({"role": "assistant", "content": final_answer})
            break

        trace_lines.append(f"[Turn {turn}] Araç Çağrıları:")

        messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
            }
        )

        for tool_call in choice.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            args_str = ", ".join(f"{k}={v!r}" for k, v in fn_args.items())
            trace_lines.append(f"   -> {fn_name}({args_str})")

            fn = AVAILABLE_FUNCTIONS.get(fn_name)
            if fn is None:
                fn_result = {"error": f"Bilinmeyen fonksiyon: {fn_name}"}
            else:
                try:
                    fn_result = fn(**fn_args)
                except Exception as e:
                    fn_result = {"error": str(e)}

            trace_lines.append(f"   <- {fn_result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(fn_result, ensure_ascii=False),
                }
            )
    else:
        final_answer = "⚠️ Maksimum tur sayısına ulaşıldı, cevap tamamlanamadı."

    trace_lines.append(f"\n[Turn {turn}] Nihai Yanıt:")
    trace_lines.append(final_answer)

    return final_answer, "\n".join(trace_lines)


# ---------------------------------------------------------------------------
# 5) GRADIO ARAYÜZÜ
# ---------------------------------------------------------------------------

def chat_fn(message, history):
    final_answer, trace = run_agent(message)
    trace_block = f"<details><summary>🔧 Tool çağrı adımları</summary>\n\n```\n{trace}\n```\n\n</details>"
    return f"{final_answer}\n\n{trace_block}"


demo = gr.ChatInterface(
    fn=chat_fn,
    title="🌫️ Tool Calling Demo — Hava Kalitesi Asistanı",
    description=(
        "Bu asistan, sorularınızı yanıtlamak için **OpenAQ public API**'sini "
        "(`get_air_quality`) ve bir **AQI yorumlayıcı** (`interpret_aqi`) tool'unu "
        "kullanır. Model, hangi tool'u ne zaman çağırdığını cevabın altındaki "
        "'Tool çağrı adımları' bölümünde gösterir.\n\n"
        "Örnek soru: *\"İstanbul'un hava kalitesi bugün nasıl, dışarıda spor yapmak güvenli mi?\"*"
    ),
    examples=[
        "İstanbul'un hava kalitesi bugün nasıl, dışarıda spor yapmak güvenli mi?",
        "Ankara mı Berlin mi daha kirli havaya sahip?",
        "Londra'daki PM2.5 değeri kaç ve bu ne anlama geliyor?",
    ],
)

if __name__ == "__main__":
    demo.launch()