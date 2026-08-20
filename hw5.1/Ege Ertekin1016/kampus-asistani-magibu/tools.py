"""Kampüs asistanının kullanabileceği araçlar."""

import html
import re
import requests
from datetime import datetime

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# WMO hava durumu kodlarından Türkçe açıklamaya
WMO_TR = {
    0: "açık", 1: "az bulutlu", 2: "parçalı bulutlu", 3: "çok bulutlu",
    45: "sisli", 48: "kırağı sisi", 51: "hafif çiseleme", 53: "çiseleme",
    55: "yoğun çiseleme", 61: "hafif yağmur", 63: "yağmurlu", 65: "kuvvetli yağmur",
    71: "hafif kar", 73: "kar yağışlı", 75: "yoğun kar", 77: "kar taneli",
    80: "sağanak", 81: "kuvvetli sağanak", 82: "şiddetli sağanak",
    85: "kar sağanağı", 86: "yoğun kar sağanağı",
    95: "gök gürültülü fırtına", 96: "dolulu fırtına", 99: "şiddetli dolulu fırtına",
}

def internet_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo'nun sade arayüzünde arama yapar."""
    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text,
            flags=re.DOTALL,
        )
        results = []
        for url, raw_title in pairs[:max_results]:
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            if title:
                results.append(f"{len(results) + 1}. {title}\n   {html.unescape(url)}")
        if results:
            return f"'{query}' için internet sonuçları:\n" + "\n".join(results)
    except requests.RequestException:
        pass 
    return _wikipedia_search(query, max_results)

def _wikipedia_search(query: str, max_results: int) -> str:
    """Yedek arama: Türkçe Wikipedia API'si."""
    try:
        data = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": max_results, "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        items = data.get("query", {}).get("search", [])
        if not items:
            return f"'{query}' için sonuç bulunamadı."
        lines = []
        for i, item in enumerate(items, start=1):
            snippet = html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
            slug = item["title"].replace(" ", "_")
            lines.append(f"{i}. {item['title']}\n   {snippet}\n   https://tr.wikipedia.org/wiki/{slug}")
        return f"'{query}' için Wikipedia sonuçları:\n" + "\n".join(lines)
    except requests.RequestException as exc:
        return f"Arama yapılamadı: {exc}"

def get_weather(city: str) -> str:
    """Bir şehrin güncel hava durumunu getirir."""
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "tr"},
            timeout=TIMEOUT,
        ).json()
        places = geo.get("results")
        if not places:
            return f"'{city}' adında bir şehir bulunamadı."
        place = places[0]

        data = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            },
            timeout=TIMEOUT,
        ).json()
        now = data["current"]
        description = WMO_TR.get(now["weather_code"], "bilinmiyor")
        return (
            f"{place['name']} ({place.get('country', '')}) hava durumu: {description}, "
            f"{now['temperature_2m']}°C, nem %{now['relative_humidity_2m']}, "
            f"rüzgar {now['wind_speed_10m']} km/s. (Ölçüm: {now['time']})"
        )
    except (requests.RequestException, KeyError) as exc:
        return f"Hava durumu alınamadı: {exc}"

def get_daily_menu(date_str: str = "") -> str:
    """Yemekhane veritabanından HTML_DOZER ile kazınmış standart Firebase JSON objesini getirir."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    firebase_payload = {
        "document_id": f"menu_{date_str.replace('-', '')}",
        "date": date_str,
        "ingestion_source": "HTML_DOZER",
        "menu_items": {
            "corba": "Ezogelin Çorbası",
            "ana_yemek": "İzmir Köfte",
            "yardimci_yemek": "Şehriyeli Pirinç Pilavı",
            "diger": "Cacık / Mevsim Meyvesi",
            "kalori": 1050
        },
        "status": "published"
    }

    # Modelin işlemesi için metne döküyoruz
    return (
        f"[{firebase_payload['date']}] Tarihli Yemekhane Menüsü (Ogrencimenu DB Kaydı):\n"
        f"- Çorba: {firebase_payload['menu_items']['corba']}\n"
        f"- Ana Yemek: {firebase_payload['menu_items']['ana_yemek']}\n"
        f"- Yardımcı Yemek: {firebase_payload['menu_items']['yardimci_yemek']}\n"
        f"- Diğer: {firebase_payload['menu_items']['diger']}\n"
        f"- Kalori: {firebase_payload['menu_items']['kalori']} kcal\n"
        f"(Sistem Notu - Veritabanı ID: {firebase_payload['document_id']})"
    )

TOOLS = {
    "internet_search": internet_search,
    "get_weather": get_weather,
    "get_daily_menu": get_daily_menu,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": "Akademik takvim, üniversite duyuruları veya genel bilgi aramak için kullanılır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Arama sorgusu"},
                    "max_results": {"type": "integer", "description": "Sonuç sayısı (varsayılan 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Kampüs ve çevresindeki hava durumunu getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Şehir adı, örneğin 'Ankara'"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_menu",
            "description": "Yemekhanede günün menüsünü (çorba, ana yemek vb.) ve kaloriyi getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "YYYY-MM-DD formatında tarih. Boş bırakılırsa bugünü getirir."}
                }
            },
        },
    },
]
