"""Deprem Asistanı: Tool Calling demo (USGS + OpenStreetMap Nominatim).

LLM, kullanıcı sorusuna göre araçları zincirleyerek çağırır; her çağrı ve dönen ham
veri arayüzde açıkça gösterilir, bulunan depremler OpenStreetMap haritasında işaretlenir.
"""

import html
import json
import math
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import gradio as gr
import requests
from dotenv import load_dotenv
from openai import OpenAI

try:  # yalnızca HF Spaces ZeroGPU çalışma ortamında var, lokalde yok
    import spaces
except ImportError:
    spaces = None

load_dotenv()

MODEL = "deepseek-ai/DeepSeek-V4-Flash:fireworks-ai"
BASE_URL = "https://router.huggingface.co/v1"
USER_AGENT = "les5-deprem-asistani/1.0 (egitim odevi)"
MAX_TURNS = 6

# Public Space'te token sahibinin faturasını korumak için sınırlar.
MAX_HISTORY_MESSAGES = 20
MAX_MESSAGE_CHARS = 2000

# Araç sınırları. Hem kodda kısıtlamak hem şemada modele bildirmek için tek kaynak:
# şema açıklaması koddan üretilmezse model varsayılanı sınır sanıp yanlış bilgi veriyor.
MAX_DAYS = 365
MAX_LIMIT = 50

# ---------------------------------------------------------------- rate limit

_last_call: dict[str, float] = {}
_throttle_lock = threading.Lock()

# Nominatim kullanım politikası: saniyede en fazla 1 istek. USGS cömert ama nazik olalım.
_MIN_INTERVAL = {"nominatim.openstreetmap.org": 1.0, "earthquake.usgs.gov": 0.2}


def _throttle(host: str) -> None:
    """Host başına asgari istek aralığını uygular.

    Gradio istekleri thread havuzunda çalıştırdığı için kilit şart; kilitsiz halde iki
    eşzamanlı kullanıcı Nominatim'in 1 istek/sn kuralını birlikte aşıp IP yasağı yiyebilir.
    """
    with _throttle_lock:
        wait = _MIN_INTERVAL.get(host, 0.0) - (time.monotonic() - _last_call.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


# --------------------------------------------------------------------- tools


@lru_cache(maxsize=256)
def geocode_place(place: str) -> dict:
    """Yer adını koordinata ve sınırlayıcı kutuya (bbox) çevirir."""
    _throttle("nominatim.openstreetmap.org")
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        r.raise_for_status()
        hits = r.json()
    except Exception as exc:  # ağ hatası modeli çökertmesin, görsün ve toparlasın
        return {"error": f"Nominatim isteği başarısız: {exc}"}

    if not hits:
        return {"error": f"'{place}' için sonuç bulunamadı."}

    h = hits[0]
    s, n, w, e = (float(v) for v in h["boundingbox"])  # güney, kuzey, batı, doğu
    return {
        "name": h["display_name"],
        "lat": float(h["lat"]),
        "lon": float(h["lon"]),
        "min_lat": s,
        "max_lat": n,
        "min_lon": w,
        "max_lon": e,
    }


@lru_cache(maxsize=128)
def search_earthquakes(
    min_magnitude: float = 4.0,
    days: int = 30,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    limit: int = 10,
    order: str = "magnitude",
) -> dict:
    """USGS deprem kataloğunda arama yapar. Koordinat sınırları verilmezse tüm dünya."""
    # Argümanlar LLM'den geliyor, yani güvenilmeyen girdi: aralığa sıkıştır.
    days = max(1, min(int(days), MAX_DAYS))
    params = {
        "format": "geojson",
        "starttime": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d"),
        "minmagnitude": max(0.0, min(float(min_magnitude), 10.0)),
        "limit": max(1, min(int(limit), MAX_LIMIT)),
        "orderby": "magnitude" if order == "magnitude" else "time",
    }
    bbox = {
        "minlatitude": _clamp(min_lat, 90),
        "maxlatitude": _clamp(max_lat, 90),
        "minlongitude": _clamp(min_lon, 180),
        "maxlongitude": _clamp(max_lon, 180),
    }
    params.update({k: v for k, v in bbox.items() if v is not None})

    _throttle("earthquake.usgs.gov")
    try:
        r = requests.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query", params=params, timeout=20
        )
        r.raise_for_status()
        features = r.json()["features"]
        quakes = [_simplify(f) for f in features]  # ayrıştırma da try içinde olmalı
    except Exception as exc:
        return {"error": f"USGS isteği başarısız: {exc}"}

    return {"count": len(quakes), "earthquakes": quakes}


def _clamp(value: float | None, limit: float) -> float | None:
    return None if value is None else max(-limit, min(float(value), limit))


def _simplify(feature: dict) -> dict:
    """USGS GeoJSON kaydını sadeleştirir. Eksik alanlara toleranslı."""
    coords = (feature.get("geometry") or {}).get("coordinates") or [None, None, None]
    lon, lat, depth = (list(coords) + [None, None, None])[:3]
    p = feature.get("properties") or {}
    ts = p.get("time")
    return {
        "magnitude": p.get("mag"),
        "place": p.get("place") or "bilinmeyen konum",
        "lat": lat,
        "lon": lon,
        "depth_km": depth,
        "time_utc": (
            datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")
            if ts
            else "bilinmiyor"
        ),
        "url": p.get("url") or "",
    }


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """İki koordinat arasındaki büyük daire mesafesi (haversine)."""
    for name, value, limit in (
        ("lat1", lat1, 90), ("lat2", lat2, 90), ("lon1", lon1, 180), ("lon2", lon2, 180)
    ):
        if not -limit <= float(value) <= limit:
            return {"error": f"{name}={value} geçerli aralık dışında (±{limit})."}
    r_lat1, r_lat2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(dlon / 2) ** 2
    return {"distance_km": round(2 * 6371.0088 * math.asin(math.sqrt(a)), 1)}


TOOL_FUNCS = {
    "geocode_place": geocode_place,
    "search_earthquakes": search_earthquakes,
    "distance_km": distance_km,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "geocode_place",
            "description": (
                "Bir yer adını (şehir, ülke, deniz, bölge) enlem/boylam koordinatına ve "
                "sınırlayıcı kutusuna çevirir. Belirli bir bölgede deprem aramadan önce "
                "veya iki nokta arası mesafe hesaplamadan önce kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place": {
                        "type": "string",
                        "description": "Yer adı, ör. 'İzmir', 'Ege Denizi', 'Japonya'",
                    }
                },
                "required": ["place"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_earthquakes",
            "description": (
                "USGS deprem kataloğunda arama yapar. Bölge sınırlaması için önce "
                "geocode_place çağır ve dönen min_lat/max_lat/min_lon/max_lon değerlerini buraya ver. "
                f"Sınır verilmezse tüm dünyada arar. Katalog en fazla {MAX_DAYS} gün geriye "
                "gidebilir; daha eski depremler (ör. 1999 Gölcük) bu araçla sorgulanamaz."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_magnitude": {
                        "type": "number",
                        "description": "En düşük büyüklük. Varsayılan 4.0, geçerli aralık 0-10",
                    },
                    "days": {
                        "type": "integer",
                        "description": (
                            f"Kaç gün geriye bakılacak. Varsayılan 30, en fazla {MAX_DAYS}. "
                            f"Örnek: 'son 3 ay' için 90, 'son 1 yıl' için {MAX_DAYS}"
                        ),
                    },
                    "min_lat": {"type": "number", "description": "Güney sınırı (geocode_place'ten)"},
                    "max_lat": {"type": "number", "description": "Kuzey sınırı (geocode_place'ten)"},
                    "min_lon": {"type": "number", "description": "Batı sınırı (geocode_place'ten)"},
                    "max_lon": {"type": "number", "description": "Doğu sınırı (geocode_place'ten)"},
                    "limit": {
                        "type": "integer",
                        "description": f"En fazla kaç kayıt. Varsayılan 10, üst sınır {MAX_LIMIT}",
                    },
                    "order": {
                        "type": "string",
                        "enum": ["magnitude", "time"],
                        "description": "Sıralama: büyüklüğe veya zamana göre",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "distance_km",
            "description": (
                "İki koordinat arasındaki kuş uçuşu mesafeyi kilometre olarak hesaplar. "
                "Mesafe sorularında kendin hesaplama, bu aracı kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lat1": {"type": "number"},
                    "lon1": {"type": "number"},
                    "lat2": {"type": "number"},
                    "lon2": {"type": "number"},
                },
                "required": ["lat1", "lon1", "lat2", "lon2"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Sen bir deprem bilgi asistanısın. Kullanıcının sorularını YALNIZCA sana verilen araçlardan "
    "gelen verilere dayanarak yanıtla; hafızandan deprem verisi uydurma.\n"
    "- Bir bölgeyle ilgili soruda önce geocode_place ile bölgenin sınırlarını al, sonra "
    "search_earthquakes'e ver.\n"
    "- Mesafe sorularında aritmetiği kendin yapma, distance_km aracını çağır.\n"
    "- Bağımsız çağrıları aynı turda birlikte yapabilirsin.\n"
    "- Nihai yanıtta büyüklük, yer, tarih ve derinliği belirt. Türkçe ve kısa yaz."
)

# ----------------------------------------------------------------------- map

_MAP_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
 integrity="sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H"
 crossorigin="anonymous"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
 integrity="sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH"
 crossorigin="anonymous"></script>
<style>html,body,#map{height:100%;margin:0}</style></head>
<body><div id="map"></div><script>
var quakes = __QUAKES__;
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function safeUrl(u) { return /^https:\/\//i.test(String(u || '')) ? String(u) : ''; }
var map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:18, attribution:'&copy; OpenStreetMap katkıcıları'}).addTo(map);
var pts = [];
quakes.forEach(function(q) {
  var m = Number(q.magnitude) || 0;
  var lat = Number(q.lat), lon = Number(q.lon);
  if (!isFinite(lat) || !isFinite(lon)) { return; }
  var url = safeUrl(q.url);
  var popup = '<b>M ' + esc(m) + '</b><br>' + esc(q.place) + '<br>' + esc(q.time_utc) +
    ' UTC<br>Derinlik: ' + esc(q.depth_km) + ' km' +
    (url ? '<br><a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">USGS kaydı</a>' : '');
  L.circleMarker([lat, lon], {
    radius: 4 + m * 2.5, color: m >= 6 ? '#b00020' : m >= 5 ? '#e8590c' : '#f59f00',
    fillOpacity: 0.55, weight: 2
  }).addTo(map).bindPopup(popup);
  pts.push([lat, lon]);
});
if (pts.length === 1) { map.setView(pts[0], 7); }
else if (pts.length) { map.fitBounds(pts, {padding:[40,40]}); }
else { map.setView([39, 35], 4); }
</script></body></html>"""

_EMPTY_MAP = (
    "<div style='height:520px;display:flex;align-items:center;justify-content:center;"
    "border:1px dashed #999;border-radius:8px;color:#888'>Harita: henüz deprem verisi yok</div>"
)


def _js_payload(data: list[dict]) -> str:
    """Veriyi <script> içine gömmeye uygun JSON'a çevirir.

    json.dumps `<`, `>` ve `&` kaçırmaz; veri içindeki `</script>` dizisi script bloğunu
    kapatıp kalanı HTML olarak çalıştırır. srcdoc iframe'i ana sayfanın origin'ini miras
    aldığı için bu doğrudan XSS anlamına gelir. U+2028/2029 de JS'te satır sonu sayılır.
    """
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def render_map(quakes: list[dict]) -> str:
    if not quakes:
        return _EMPTY_MAP
    doc = _MAP_TEMPLATE.replace("__QUAKES__", _js_payload(quakes))
    return (
        f'<iframe srcdoc="{html.escape(doc, quote=True)}" '
        'style="width:100%;height:520px;border:0;border-radius:8px"></iframe>'
    )


# --------------------------------------------------------------- agent loop


def _client() -> OpenAI:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise gr.Error("HF_TOKEN tanımlı değil. .env dosyasına ekleyin veya Space secret olarak girin.")
    return OpenAI(base_url=BASE_URL, api_key=token)


def _call_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCS.get(name)
    if fn is None:
        return {"error": f"Bilinmeyen araç: {name}"}
    try:
        return fn(**args)
    except Exception as exc:  # araç hatası arayüzü çökertmesin, modele geri dönsün
        return {"error": f"{type(exc).__name__}: {exc}"}


def _history_to_messages(history: list) -> list[dict]:
    """Gradio sohbet geçmişini LLM mesajlarına çevirir.

    Üç tuzak var: metadata `None` gelebilir (araç kutularını ayıklarken), `content` metin
    parçalarından oluşan bir listeye dönüşebilir ve `role` istemciden geldiği için
    'system' olarak kurgulanabilir.
    """
    messages = []
    for m in history:
        if (m.get("metadata") or {}).get("title"):
            continue  # araç kutuları modele geri gönderilmez
        if m.get("role") not in ("user", "assistant"):
            continue  # istemci kaynaklı 'system' enjeksiyonunu ele
        content = m.get("content")
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        content = str(content or "").strip()
        if content:
            messages.append({"role": m["role"], "content": content[:MAX_MESSAGE_CHARS]})
    return messages[-MAX_HISTORY_MESSAGES:]


def _fmt_call(name: str, args: dict) -> str:
    return f"{name}(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"


def respond(user_message: str, history: list):
    """Ajan döngüsü: her araç çağrısını ve sonucunu sohbete açık kutu olarak yazar."""
    user_message = (user_message or "").strip()[:MAX_MESSAGE_CHARS]
    if not user_message:
        yield history, gr.skip(), ""
        return

    history = list(history) + [{"role": "user", "content": user_message}]
    yield history, gr.skip(), ""

    client = _client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history_to_messages(history)

    quakes: list[dict] = []

    for turn in range(1, MAX_TURNS + 1):
        reply = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
        ).choices[0].message

        if not reply.tool_calls:
            history.append({"role": "assistant", "content": reply.content or "(boş yanıt)"})
            yield history, render_map(quakes), ""
            return

        messages.append(
            {
                "role": "assistant",
                "content": reply.content or "",
                "tool_calls": [tc.model_dump(include={"id", "type", "function"}) for tc in reply.tool_calls],
            }
        )

        for tc in reply.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            label = _fmt_call(tc.function.name, args)

            history.append(
                {
                    "role": "assistant",
                    "content": "",
                    "metadata": {"title": f"🔧 [Tur {turn}] {label}", "status": "pending"},
                }
            )
            yield history, gr.skip(), ""

            started = time.monotonic()
            result = _call_tool(tc.function.name, args)
            if tc.function.name == "search_earthquakes":
                quakes.extend(result.get("earthquakes", []))

            history[-1]["content"] = (
                "```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```"
            )
            history[-1]["metadata"] = {
                "title": f"🔧 [Tur {turn}] {label}",
                "status": "done",
                "duration": round(time.monotonic() - started, 2),
            }
            yield history, render_map(quakes), ""

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    history.append(
        {"role": "assistant", "content": f"Araç çağrısı sınırına ({MAX_TURNS} tur) ulaşıldı."}
    )
    yield history, render_map(quakes), ""


# ------------------------------------------------------------------------ ui

EXAMPLES = [
    "Son 3 ayda Ege Denizi'nde 4.5+ büyüklüğünde deprem oldu mu? En büyüğü İzmir'e kaç km uzaktaydı?",
    "Bu hafta dünyada kaydedilen en büyük deprem nerede oldu?",
    "Japonya'da son 30 günde 5 ve üzeri kaç deprem oldu, en derini hangisi?",
    "Kaliforniya'daki son büyük deprem, San Francisco'ya mı Los Angeles'a mı daha yakındı?",
]

with gr.Blocks(title="Deprem Asistanı: Tool Calling") as demo:
    gr.Markdown(
        "# 🌍 Deprem Asistanı: Tool Calling Demo\n"
        "USGS deprem kataloğu + OpenStreetMap Nominatim. Model hangi aracı hangi argümanlarla "
        "çağırdığını ve dönen ham JSON'u aşağıda açıkça gösterir; bulunan depremler haritada işaretlenir."
    )
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=520, label="Sohbet ve araç adımları", resizable=True)
            msg = gr.Textbox(
                placeholder="Ör: Son 3 ayda Ege Denizi'nde 4.5+ deprem oldu mu?",
                label="Soru",
                submit_btn=True,
            )
            gr.Examples(EXAMPLES, inputs=msg, label="Örnek sorular")
            clear = gr.Button("🗑️ Temizle", variant="secondary")
        with gr.Column(scale=2):
            map_html = gr.HTML(_EMPTY_MAP, label="Harita (OpenStreetMap)")

    msg.submit(respond, [msg, chatbot], [chatbot, map_html, msg])
    clear.click(lambda: ([], _EMPTY_MAP, ""), outputs=[chatbot, map_html, msg])

    if spaces is not None:
        # ZeroGPU açılışta Gradio'ya bağlı en az bir @spaces.GPU fonksiyonu arar; bulamazsa
        # "No @spaces.GPU function detected during startup" ile hiç açılmaz. Bu uygulamanın
        # GPU'ya ihtiyacı yok, çünkü model uzaktaki HF Inference Router'da çalışıyor. Bu yüzden
        # taramayı geçmek için görünmez bir no-op bağlıyoruz: gerçek sohbet akışı GPU istemez,
        # dolayısıyla ziyaretçilerin günlük ZeroGPU kotasından hiçbir şey harcanmaz.
        @spaces.GPU(duration=1)
        def _zerogpu_startup_probe() -> str:
            """ZeroGPU açılış taraması için no-op. Gerçek iş akışı CPU'da çalışır."""
            return ""

        gr.Button(visible=False).click(_zerogpu_startup_probe, outputs=[])

if __name__ == "__main__":
    demo.launch()
