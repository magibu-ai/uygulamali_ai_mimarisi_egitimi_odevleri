"""
Araç tanımları (tool calling).

Her araç iki parçadan oluşur:
  - OpenAI uyumlu JSON şeması (modele ne sunduğumuz),
  - saf Python fonksiyonu (gerçekte ne çalıştığı).

İkisi `@tool` dekoratörüyle tek yerde bağlanır; böylece yeni araç eklemek için
tek bir fonksiyon yazmak yeterli. `TOOL_SCHEMAS` ve `TOOL_FUNCS` otomatik dolar,
sistem istemindeki araç listesi de buradan üretilir.

Araçlar her zaman string döner. Hata durumunda exception fırlatmak yerine
"HATA: ..." metni döndürürler; model bunu okuyup kendini toparlayabilsin diye.
"""

from __future__ import annotations

import ast
import json
import operator
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

import requests

from config import (
    DEFAULT_CITY,
    FETCH_MAX_CHARS,
    HTTP_TIMEOUT,
    MEMORY_DB,
    PYTHON_TIMEOUT,
    SEARCH_MAX_RESULTS,
    SEARCH_REGION,
)

TOOL_SCHEMAS: list[dict] = []
TOOL_FUNCS: dict = {}


def tool(name: str, description: str, parameters: dict):
    """Fonksiyonu araç olarak kaydeder ve JSON şemasını üretir."""

    def decorator(func):
        TOOL_SCHEMAS.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )
        TOOL_FUNCS[name] = func
        return func

    return decorator


def tool_summaries() -> str:
    """Sistem istemine gömülecek `- ad: açıklama` listesi."""
    return "\n".join(
        f"- `{s['function']['name']}`: {s['function']['description']}" for s in TOOL_SCHEMAS
    )


# ---------------------------------------------------------------------------
# 1. İnternet araması — DuckDuckGo (API anahtarı gerektirmez)
# ---------------------------------------------------------------------------
@tool(
    name="web_search",
    description=(
        "İnternette arama yapar. Güncel bilgi, haber, fiyat, 'en son' veya 2025 sonrası "
        "olaylar için kullan. Sorguyu kullanıcının cümlesi değil, kısa anahtar kelime "
        "öbeği olarak ver."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Anahtar kelimelere indirgenmiş arama sorgusu. Örn: 'BIST 100 kapanış bugün'",
            },
            "max_results": {
                "type": "integer",
                "description": f"Döndürülecek sonuç sayısı (varsayılan {SEARCH_MAX_RESULTS}).",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int | None = None) -> str:
    try:
        from ddgs import DDGS
    except ImportError:  # paket adı eski sürümlerde farklıydı
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            return "HATA: arama paketi kurulu değil. `pip install ddgs` çalıştır."

    n = max_results or SEARCH_MAX_RESULTS
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, region=SEARCH_REGION, max_results=n))
    except Exception as exc:
        return f"HATA: arama başarısız ({exc})."

    if not hits:
        return f"'{query}' için sonuç bulunamadı. Sorguyu sadeleştirip tekrar dene."

    lines = []
    for i, hit in enumerate(hits, 1):
        title = hit.get("title", "")
        body = (hit.get("body") or "").strip().replace("\n", " ")
        href = hit.get("href", "")
        lines.append(f"{i}. {title}\n   {body[:350]}\n   URL: {href}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Sayfa içeriği çekme — arama özetleri yetmediğinde
# ---------------------------------------------------------------------------
@tool(
    name="fetch_url",
    description=(
        "Verilen URL'nin metin içeriğini indirir. web_search sonuçlarındaki özet yetersiz "
        "kaldığında en alakalı bağlantıyı açmak için kullan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Tam URL (http/https ile başlamalı)."},
        },
        "required": ["url"],
    },
)
def fetch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "HATA: URL http:// veya https:// ile başlamalı."
    try:
        resp = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; YerelAsistan/1.0)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return f"HATA: sayfa indirilemedi ({exc})."

    html = resp.text
    # Script/style bloklarını at, etiketleri temizle, boşlukları sıkıştır.
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return "HATA: sayfada okunabilir metin yok (muhtemelen JavaScript ile üretiliyor)."
    if len(text) > FETCH_MAX_CHARS:
        text = text[:FETCH_MAX_CHARS] + f"\n\n[... {len(text) - FETCH_MAX_CHARS} karakter kırpıldı]"
    return text


# ---------------------------------------------------------------------------
# 3. Hesap makinesi — AST tabanlı, eval kullanmaz
# ---------------------------------------------------------------------------
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    """Sadece sayı ve aritmetik operatör içeren AST düğümlerini değerlendirir."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("sadece sayısal sabitler kabul edilir")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("izin verilmeyen ifade")


@tool(
    name="calculator",
    description=(
        "Aritmetik ifade hesaplar (+ - * / // % ** ve parantez). Dört işlem, yüzde ve "
        "birim çevrimi gibi hesapları kafadan yapma, bunu kullan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Python sözdiziminde aritmetik ifade. Örn: '(1250 * 1.20) / 3'",
            },
        },
        "required": ["expression"],
    },
)
def calculator(expression: str) -> str:
    expr = expression.replace("^", "**").replace(",", ".").strip()
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
    except ZeroDivisionError:
        return "HATA: sıfıra bölme."
    except Exception as exc:
        return f"HATA: ifade değerlendirilemedi ({exc}). Sadece sayı ve + - * / // % ** kullan."

    # Kayan nokta artefaktlarını temizle: 410.00000000000006 -> 410
    if isinstance(result, float):
        result = round(result, 10)
        if result.is_integer():
            result = int(result)
    return f"{expression} = {result}"


# ---------------------------------------------------------------------------
# 4. Tarih / saat — modelin bilemeyeceği tek şey
# ---------------------------------------------------------------------------
_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


@tool(
    name="current_datetime",
    description=(
        "Tarih ve saat işlemleri. Parametresiz çağrılırsa şu anı verir. offset_days ile "
        "gün ekler/çıkarır. until_date verilirse o tarihe kaç gün kaldığını HESAPLAR. "
        "'bugün', 'yarın', 'kaç gün kaldı' gibi ifadelerde tarihi veya gün farkını asla "
        "kendin hesaplama, bunu çağır."
    ),
    parameters={
        "type": "object",
        "properties": {
            "offset_days": {
                "type": "integer",
                "description": "Bugüne eklenecek gün sayısı. Yarın için 1, dün için -1. Varsayılan 0.",
            },
            "until_date": {
                "type": "string",
                "description": (
                    "Kaç gün kaldığı hesaplanacak hedef tarih, YYYY-AA-GG biçiminde. "
                    "Örn: 2027 yılbaşı için '2027-01-01'."
                ),
            },
        },
    },
)
def current_datetime(offset_days: int = 0, until_date: str | None = None) -> str:
    now = datetime.now() + timedelta(days=offset_days or 0)
    simdi = (
        f"{now.strftime('%d.%m.%Y')} {_GUNLER[now.weekday()]}, saat {now.strftime('%H:%M')} "
        f"(yerel saat)"
    )
    if not until_date:
        return simdi

    try:
        hedef = datetime.strptime(until_date.strip(), "%Y-%m-%d")
    except ValueError:
        return f"HATA: '{until_date}' okunamadı. Tarihi YYYY-AA-GG biçiminde ver (örn: 2027-01-01)."

    fark = (hedef.date() - now.date()).days
    if fark > 0:
        return f"{simdi}. {hedef.strftime('%d.%m.%Y')} tarihine {fark} gün var."
    if fark < 0:
        return f"{simdi}. {hedef.strftime('%d.%m.%Y')} tarihinin üzerinden {abs(fark)} gün geçti."
    return f"{simdi}. {hedef.strftime('%d.%m.%Y')} bugün."


# ---------------------------------------------------------------------------
# 5. Hava durumu — Open-Meteo (anahtarsız)
# ---------------------------------------------------------------------------
_WMO = {
    0: "açık", 1: "az bulutlu", 2: "parçalı bulutlu", 3: "çok bulutlu",
    45: "sisli", 48: "kırağılı sis", 51: "hafif çisenti", 53: "çisenti",
    55: "yoğun çisenti", 61: "hafif yağmur", 63: "yağmurlu", 65: "kuvvetli yağmur",
    71: "hafif kar", 73: "kar yağışlı", 75: "yoğun kar", 77: "kar taneli",
    80: "hafif sağanak", 81: "sağanak", 82: "şiddetli sağanak",
    95: "gök gürültülü fırtına", 96: "dolulu fırtına", 99: "şiddetli dolulu fırtına",
}


@tool(
    name="get_weather",
    description=(
        "Bir şehrin güncel hava durumunu ve 3 günlük tahminini verir. Hava sorularında "
        "web_search yerine bunu kullan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": f"Şehir adı. Belirtilmezse {DEFAULT_CITY} kullanılır.",
            },
        },
    },
)
def get_weather(city: str | None = None) -> str:
    city = (city or DEFAULT_CITY).strip()
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "tr", "format": "json"},
            timeout=HTTP_TIMEOUT,
        ).json()
    except Exception as exc:
        return f"HATA: konum servisi yanıt vermedi ({exc})."

    results = geo.get("results")
    if not results:
        return f"HATA: '{city}' bulunamadı. Şehir adını farklı yazmayı dene."

    place = results[0]
    lat, lon = place["latitude"], place["longitude"]
    label = f"{place['name']}, {place.get('country', '')}".strip(", ")

    try:
        data = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 3,
            },
            timeout=HTTP_TIMEOUT,
        ).json()
    except Exception as exc:
        return f"HATA: hava servisi yanıt vermedi ({exc})."

    cur = data["current"]
    lines = [
        f"{label} — şu an: {cur['temperature_2m']}°C, "
        f"{_WMO.get(cur['weather_code'], 'bilinmeyen')}, "
        f"nem %{cur['relative_humidity_2m']}, rüzgâr {cur['wind_speed_10m']} km/s",
        "Tahmin:",
    ]
    daily = data["daily"]
    for i, day in enumerate(daily["time"]):
        d = datetime.strptime(day, "%Y-%m-%d")
        lines.append(
            f"  {d.strftime('%d.%m')} {_GUNLER[d.weekday()]}: "
            f"{daily['temperature_2m_min'][i]}–{daily['temperature_2m_max'][i]}°C, "
            f"{_WMO.get(daily['weather_code'][i], 'bilinmeyen')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Döviz çevirici — Frankfurter (anahtarsız, ECB verisi)
# ---------------------------------------------------------------------------
@tool(
    name="currency_convert",
    description=(
        "Güncel veya geçmiş tarihli döviz kuruyla para birimi çevirir. Kur sorularında "
        "web_search yerine bunu kullan."
    ),
    parameters={
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Çevrilecek miktar. Varsayılan 1."},
            "from_currency": {"type": "string", "description": "Kaynak para birimi kodu. Örn: USD"},
            "to_currency": {"type": "string", "description": "Hedef para birimi kodu. Örn: TRY"},
            "date": {
                "type": "string",
                "description": "Geçmiş kur için YYYY-AA-GG. Boş bırakılırsa en güncel kur.",
            },
        },
        "required": ["from_currency", "to_currency"],
    },
)
def currency_convert(
    from_currency: str, to_currency: str, amount: float = 1.0, date: str | None = None
) -> str:
    src = from_currency.strip().upper()
    dst = to_currency.strip().upper()
    endpoint = f"https://api.frankfurter.app/{date}" if date else "https://api.frankfurter.app/latest"
    try:
        data = requests.get(
            endpoint, params={"amount": amount, "from": src, "to": dst}, timeout=HTTP_TIMEOUT
        ).json()
    except Exception as exc:
        return f"HATA: kur servisi yanıt vermedi ({exc})."

    rates = data.get("rates") or {}
    if dst not in rates:
        return (
            f"HATA: {src}->{dst} çevrimi yapılamadı. Kod yanlış olabilir "
            f"(desteklenenler ECB kurlarıdır; TRY, USD, EUR, GBP, JPY vb.)."
        )
    return f"{amount} {src} = {rates[dst]:.4f} {dst} (kur tarihi: {data.get('date')}, kaynak: ECB/Frankfurter)"


# ---------------------------------------------------------------------------
# 7. Python çalıştırma — ayrı süreç, zaman aşımlı
# ---------------------------------------------------------------------------
_YASAK = ("shutil.rmtree", "os.remove", "os.rmdir", "os.system", "subprocess", "socket")


@tool(
    name="run_python",
    description=(
        "Verilen Python kodunu ayrı bir süreçte çalıştırır ve stdout çıktısını döndürür. "
        "Veri işleme, algoritma denemesi veya karmaşık hesap için kullan. Sonucu mutlaka "
        "print() ile yazdır."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Çalıştırılacak Python kodu. Sonuç print() ile yazdırılmalı.",
            },
        },
        "required": ["code"],
    },
)
def run_python(code: str) -> str:
    for kalip in _YASAK:
        if kalip in code:
            return f"HATA: güvenlik nedeniyle '{kalip}' içeren kod çalıştırılmaz."

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name

    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=PYTHON_TIMEOUT,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return f"HATA: kod {PYTHON_TIMEOUT} saniyede bitmedi, durduruldu."
    finally:
        os.unlink(path)

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return f"HATA: kod {proc.returncode} koduyla bitti.\n{err[:1500]}"
    if not out:
        return "Kod çalıştı ama hiçbir çıktı üretmedi. Sonucu print() ile yazdırmayı unutma."
    return out[:3000]


# ---------------------------------------------------------------------------
# 8-9. Kalıcı hafıza — SQLite (bu asistanın ayırt edici aracı)
# ---------------------------------------------------------------------------
def _db():
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            topic    TEXT NOT NULL,
            content  TEXT NOT NULL,
            created  TEXT NOT NULL
        )
        """
    )
    return conn


@tool(
    name="save_note",
    description=(
        "Kullanıcıyla ilgili kalıcı bir bilgiyi kaydeder (tercih, isim, hedef, alerji, "
        "üzerinde çalıştığı proje). Oturum kapansa da kalır."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Kısa konu etiketi. Örn: 'kahve tercihi', 'iş', 'sağlık'",
            },
            "content": {"type": "string", "description": "Kaydedilecek bilginin kendisi."},
        },
        "required": ["topic", "content"],
    },
)
def save_note(topic: str, content: str) -> str:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO notes (topic, content, created) VALUES (?, ?, ?)",
            (topic.strip(), content.strip(), datetime.now().isoformat(timespec="seconds")),
        )
    return f"Not kaydedildi (#{cur.lastrowid}, konu: {topic})."


@tool(
    name="recall_notes",
    description=(
        "Daha önce kaydedilmiş notları getirir. Kullanıcı kendisiyle ilgili bir şey "
        "sorduğunda ('bana ne biliyorsun', 'tercihim neydi') önce bunu çağır."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Konu veya içerikte aranacak kelime. Boş bırakılırsa tüm notlar.",
            },
        },
    },
)
def recall_notes(query: str | None = None) -> str:
    with _db() as conn:
        if query:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                "SELECT topic, content, created FROM notes "
                "WHERE topic LIKE ? OR content LIKE ? ORDER BY id DESC LIMIT 20",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT topic, content, created FROM notes ORDER BY id DESC LIMIT 20"
            ).fetchall()

    if not rows:
        return "Kayıtlı not yok." if not query else f"'{query}' ile eşleşen not yok."
    return "\n".join(f"[{c[:10]}] {t}: {v}" for t, v, c in rows)


# ---------------------------------------------------------------------------
# Yürütücü
# ---------------------------------------------------------------------------
def execute_tool(name: str, arguments: str) -> str:
    """Modelin ürettiği araç çağrısını çalıştırır ve sonucu string döndürür."""
    func = TOOL_FUNCS.get(name)
    if func is None:
        return f"HATA: '{name}' adında bir araç yok. Mevcut araçlar: {', '.join(TOOL_FUNCS)}"

    try:
        kwargs = json.loads(arguments) if arguments and arguments.strip() else {}
    except json.JSONDecodeError as exc:
        return f"HATA: argümanlar geçerli JSON değil ({exc}). Şemaya uygun JSON üret."

    if not isinstance(kwargs, dict):
        return "HATA: argümanlar bir JSON nesnesi olmalı."

    try:
        return str(func(**kwargs))
    except TypeError as exc:
        return f"HATA: argümanlar araca uymuyor ({exc})."
    except Exception as exc:  # araç içi beklenmedik hata modeli çökertmesin
        return f"HATA: araç çalışırken hata oluştu ({type(exc).__name__}: {exc})."
