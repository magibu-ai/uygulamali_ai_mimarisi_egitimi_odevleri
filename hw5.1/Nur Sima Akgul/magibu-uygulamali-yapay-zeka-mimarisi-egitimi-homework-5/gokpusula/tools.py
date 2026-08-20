import re
import math
import requests
import ephem
from datetime import datetime

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

WMO_TR = {
    0: "Açık", 1: "Çoğunlukla açık", 2: "Parçalı bulutlu", 3: "Kapalı",
    45: "Sisli", 48: "Yoğun kırağılı sis",
    51: "Hafif çiseleme", 53: "Orta çiseleme", 55: "Yoğun çiseleme",
    56: "Hafif dondurucu çiseleme", 57: "Yoğun dondurucu çiseleme",
    61: "Hafif yağmur", 63: "Orta yağmur", 65: "Şiddetli yağmur",
    66: "Hafif dondurucu yağmur", 67: "Şiddetli dondurucu yağmur",
    71: "Hafif kar", 73: "Orta kar", 75: "Şiddetli kar", 77: "Kar taneleri",
    80: "Hafif sağanak", 81: "Orta sağanak", 82: "Şiddetli sağanak",
    85: "Hafif kar sağanağı", 86: "Şiddetli kar sağanağı",
    95: "Gök gürültülü fırtına", 96: "Dolu ile hafif fırtına", 99: "Dolu ile şiddetli fırtına",
}


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def _geocode(city):
    """Open-Meteo geocoding ile (lat, lon, display_name) döndürür; bulunamazsa None."""
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "tr"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        data = resp.json()
        if not data.get("results"):
            return None
        r = data["results"][0]
        return r["latitude"], r["longitude"], r.get("name", city)
    except Exception:
        return None


def _wikipedia_search(query):
    try:
        resp = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 3,
                "utf8": 1,
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        data = resp.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            return "Arama sonucu bulunamadı."
        snippets = []
        for r in results:
            title = r["title"]
            snippet = re.sub(r"<[^>]+>", "", r["snippet"])
            snippets.append(f"• {title}: {snippet}")
        return "Wikipedia arama sonuçları:\n" + "\n".join(snippets)
    except Exception as e:
        return f"Arama başarısız: {e}"


def _az_to_direction(az_deg):
    dirs = ["Kuzey", "Kuzeydoğu", "Doğu", "Güneydoğu", "Güney", "Güneybatı", "Batı", "Kuzeybatı"]
    return dirs[int((az_deg + 22.5) / 45) % 8]


# ─── internet_search ──────────────────────────────────────────────────────────

def internet_search(query, max_results=5):
    """
    DuckDuckGo lite arama; güncel gök olayları: meteor yağmuru, tutulma
    tarihleri, ISS geçişi vb. için kullan.
    """
    try:
        resp = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query, "kl": "tr-tr"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        snippets = re.findall(
            r'class=["\']result-snippet["\'][^>]*>\s*(.*?)\s*</td>',
            resp.text,
            re.DOTALL | re.IGNORECASE,
        )
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets]
        clean = [s for s in clean if s][:max_results]
        if clean:
            return f"Arama sonuçları ({query}):\n\n" + "\n\n".join(clean)
    except Exception:
        pass
    return _wikipedia_search(query)


# ─── goksel_gorunurluk ────────────────────────────────────────────────────────

def goksel_gorunurluk(sehir, tarih=""):
    """
    Belirtilen şehir için gökyüzü görünürlük raporu: ay evresi, ay doğuş/batış,
    astronomik karanlık başlangıcı ve görünür gezegenler (ephem ile hesaplanır).
    """
    try:
        geo = _geocode(sehir)
        if geo is None:
            return f"'{sehir}' şehri bulunamadı. Lütfen farklı bir şehir adı deneyin."
        lat, lon, display_name = geo

        # Gözlem tarihi
        if tarih:
            try:
                dt = datetime.strptime(tarih, "%Y-%m-%d")
            except ValueError:
                dt = datetime.now()
        else:
            dt = datetime.now()

        # Gözlem saati: yerel 21:00 = UTC 18:00 (Türkiye UTC+3)
        utc_obs_str = f"{dt.year}/{dt.month}/{dt.day} 18:00:00"

        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = ephem.Date(utc_obs_str)

        lines = [
            f"=== {display_name} Gökyüzü Raporu ===",
            f"Tarih / Saat: {dt.strftime('%Y-%m-%d')} 21:00 yerel (UTC+3)\n",
        ]

        # ── Ay evresi ──
        moon = ephem.Moon(obs)
        illum = moon.phase  # 0–100

        next_new = ephem.next_new_moon(obs.date)
        next_full = ephem.next_full_moon(obs.date)
        waning = next_new < next_full  # azalan mı?

        if illum < 2:
            phase_name = "Yeni Ay"
        elif illum > 98:
            phase_name = "Dolunay"
        elif 48 <= illum <= 52:
            phase_name = "Son Dördün" if waning else "İlk Dördün"
        elif not waning and illum < 48:
            phase_name = "Büyüyen Hilal"
        elif not waning and illum > 52:
            phase_name = "Şişkin Ay (büyüyen)"
        elif waning and illum > 52:
            phase_name = "Şişkin Ay (azalan)"
        else:
            phase_name = "Azalan Hilal"

        lines.append(f"🌙 Ay Evresi  : {phase_name} (%{illum:.0f} aydınlanma)")
        if illum > 80:
            lines.append(
                "   ⚠️  Ay parlak, sönük cisimleri yıkar; Ay batışını beklemek daha iyi."
            )

        # ── Ay doğuş / batış ──
        obs.date = ephem.Date(f"{dt.year}/{dt.month}/{dt.day} 00:00:00")
        try:
            rise = obs.next_rising(ephem.Moon())
            rise_local = ephem.Date(rise + 3.0 / 24.0).datetime().strftime("%H:%M")
            lines.append(f"   Ay Doğuşu : {rise_local} (yerel)")
        except ephem.AlwaysUpError:
            lines.append("   Ay bu gece hiç batmıyor.")
        except ephem.NeverUpError:
            lines.append("   Ay bu gece hiç doğmuyor.")

        obs.date = ephem.Date(f"{dt.year}/{dt.month}/{dt.day} 00:00:00")
        try:
            setting = obs.next_setting(ephem.Moon())
            set_local = ephem.Date(setting + 3.0 / 24.0).datetime().strftime("%H:%M")
            lines.append(f"   Ay Batışı  : {set_local} (yerel)")
        except ephem.AlwaysUpError:
            lines.append("   Ay bu gece hiç batmıyor.")
        except ephem.NeverUpError:
            lines.append("   Ay bu gece hiç doğmuyor.")

        # ── Astronomik alacakaranlık sonu (gerçek karanlık) ──
        obs.horizon = "-18"
        obs.date = ephem.Date(f"{dt.year}/{dt.month}/{dt.day} 15:00:00")
        try:
            dark = obs.next_setting(ephem.Sun(), use_center=True)
            dark_local = ephem.Date(dark + 3.0 / 24.0).datetime().strftime("%H:%M")
            lines.append(f"\n🌑 Karanlık Başlangıcı: {dark_local} (yerel)")
        except Exception:
            lines.append("\n🌑 Karanlık başlangıcı hesaplanamadı.")
        obs.horizon = "0"

        # ── Görünür gezegenler ──
        obs.date = ephem.Date(utc_obs_str)
        planet_map = {
            "Merkür": ephem.Mercury,
            "Venüs": ephem.Venus,
            "Mars": ephem.Mars,
            "Jüpiter": ephem.Jupiter,
            "Satürn": ephem.Saturn,
        }
        lines.append("\n🔭 Görünür Gezegenler (ufkun >10° üzerinde):")
        visible = []
        for name, Cls in planet_map.items():
            p = Cls(obs)
            alt_deg = math.degrees(float(p.alt))
            az_deg = math.degrees(float(p.az))
            if alt_deg > 10:
                direction = _az_to_direction(az_deg)
                visible.append(f"   {name}: ufkun ~{alt_deg:.0f}° üzerinde, {direction}")
        if visible:
            lines.extend(visible)
        else:
            lines.append("   Bu saatte görünür parlak gezegen yok.")

        lines.append(
            "\n💡 Gözlem İpucu: Ufkun 30°+ üzerindeki cisimler en net görünür. "
            "Işık kirliliğinden uzak, karanlık bir alana gidin."
        )
        return "\n".join(lines)

    except Exception as e:
        return f"Gökyüzü bilgisi hesaplanırken hata oluştu: {e}"


# ─── gozlem_kosullari ─────────────────────────────────────────────────────────

def gozlem_kosullari(sehir):
    """
    Gözlem için bulut oranı, sıcaklık ve rüzgar bilgisi; verdikt döndürür.
    Gözlem uygunluğuna odaklanır.
    """
    try:
        geo = _geocode(sehir)
        if geo is None:
            return f"'{sehir}' şehri bulunamadı."
        lat, lon, display_name = geo

        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "cloud_cover,temperature_2m,wind_speed_10m",
                "wind_speed_unit": "kmh",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        current = resp.json()["current"]
        cloud = current["cloud_cover"]
        temp = current["temperature_2m"]
        wind = current["wind_speed_10m"]

        if cloud < 20:
            verdict = "Mükemmel (gökyüzü açık)"
        elif cloud < 50:
            verdict = "İyi (az bulutlu)"
        elif cloud < 80:
            verdict = "Zayıf (çok bulutlu)"
        else:
            verdict = "Uygun değil (kapalı)"

        return (
            f"{display_name} gözlem koşulları:\n"
            f"  Gözlem Uygunluğu : {verdict}\n"
            f"  Bulut Oranı      : %{cloud}\n"
            f"  Sıcaklık         : {temp}°C\n"
            f"  Rüzgar           : {wind} km/h\n"
            f"  Not: Gece üşümeye karşı ekstra katman öneririz."
        )
    except Exception as e:
        return f"Gözlem koşulları alınamadı: {e}"


# ─── get_weather ──────────────────────────────────────────────────────────────

def get_weather(sehir):
    """
    Genel hava durumu (sıcaklık, nem, rüzgar, hava kodu).
    Gözlem uygunluğu için gozlem_kosullari kullan; bu araç genel amaçlıdır.
    """
    try:
        geo = _geocode(sehir)
        if geo is None:
            return f"'{sehir}' şehri bulunamadı."
        lat, lon, display_name = geo

        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "wind_speed_unit": "kmh",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        current = resp.json()["current"]
        temp = current["temperature_2m"]
        humidity = current.get("relative_humidity_2m", "?")
        wind = current["wind_speed_10m"]
        wcode = current.get("weather_code", 0)
        condition = WMO_TR.get(wcode, f"Kod {wcode}")

        return (
            f"{display_name} hava durumu:\n"
            f"  Durum    : {condition}\n"
            f"  Sıcaklık : {temp}°C\n"
            f"  Nem      : {humidity}%\n"
            f"  Rüzgar   : {wind} km/h"
        )
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"


# ─── TOOLS & TOOL_SCHEMAS ─────────────────────────────────────────────────────

TOOLS = {
    "internet_search": internet_search,
    "goksel_gorunurluk": goksel_gorunurluk,
    "gozlem_kosullari": gozlem_kosullari,
    "get_weather": get_weather,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": (
                "İnternette DuckDuckGo/Wikipedia ile arama yapar. "
                "Güncel gök olayları (meteor yağmuru, tutulma tarihleri, "
                "ISS geçişi, kuyruklu yıldız vb.) için kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Arama sorgusu (Türkçe veya İngilizce)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maksimum sonuç sayısı (varsayılan: 5)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "goksel_gorunurluk",
            "description": (
                "Belirtilen şehir için gökyüzü raporu üretir: ay evresi ve "
                "aydınlanma yüzdesi, ay doğuş/batış saatleri, astronomik karanlık "
                "başlangıcı, görünür gezegenler (yön ve yükseklik). "
                "'Bu gece ne görünür', 'ay hangi evrede', 'Jüpiter görünür mü', "
                "'gezegenler' gibi sorularda kullan. Şehir zorunludur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sehir": {
                        "type": "string",
                        "description": "Gözlem yapılacak şehir (örn. 'Sivas', 'İzmir', 'Ankara')",
                    },
                    "tarih": {
                        "type": "string",
                        "description": (
                            "Gözlem tarihi, YYYY-MM-DD formatında "
                            "(örn. '2026-08-15'). Boş bırakılırsa bu gece hesaplanır."
                        ),
                    },
                },
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gozlem_kosullari",
            "description": (
                "Gözlem uygunluğu için anlık bulut oranı, sıcaklık ve rüzgar "
                "bilgisi; verdikt (Mükemmel/İyi/Zayıf/Uygun değil) döndürür. "
                "'Hava açık mı', 'gözlem yapabilir miyim' gibi sorularda kullan. "
                "Genel hava durumu için get_weather kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sehir": {
                        "type": "string",
                        "description": "Hava koşulları sorgulanacak şehir",
                    }
                },
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Genel hava durumu bilgisi (sıcaklık, nem, rüzgar, hava kodu). "
                "Gözlem uygunluğu için gozlem_kosullari kullan; "
                "bu araç genel amaçlı hava durumudur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sehir": {
                        "type": "string",
                        "description": "Hava durumu sorgulanacak şehir adı",
                    }
                },
                "required": ["sehir"],
            },
        },
    },
]
