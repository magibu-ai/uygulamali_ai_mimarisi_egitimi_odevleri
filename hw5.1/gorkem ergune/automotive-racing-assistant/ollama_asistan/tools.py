"""Modelin cagirabilecegi 4 arac.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele
geri beslenir. Hicbiri normal kullanici hatasi icin istisna FIRLATMAZ — bilinmeyen
bilesen/konu ya da dis API hatasi olursa Turkce bir aciklama doner, boylece
sohbet dongusu cokmez.

TOOL_SCHEMAS listesi ise modele "elinde su araclar var" demenin JSON halidir.
"""

import datetime
import html
import re

import requests

import race_data

# Guncel-bilgi aramalarinda modelin sorguya dogru yili koymasi icin (Faz 3'te bazen
# "2023" gibi eski bir yil uydurdugu gozlendi). Sabit degil, calisma aninda gelir.
CURRENT_YEAR = datetime.date.today().year

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# WMO hava durumu kodlarindan Turkce aciklamaya (Open-Meteo bu kodlari kullanir).
WMO_TR = {
    0: "acik", 1: "az bulutlu", 2: "parcali bulutlu", 3: "cok bulutlu",
    45: "sisli", 48: "kirragi sisi", 51: "hafif ciseleme", 53: "ciseleme",
    55: "yogun ciseleme", 61: "hafif yagmur", 63: "yagmurlu", 65: "kuvvetli yagmur",
    71: "hafif kar", 73: "kar yagisli", 75: "yogun kar", 77: "kar taneli",
    80: "saganak", 81: "kuvvetli saganak", 82: "siddetli saganak",
    85: "kar saganagi", 86: "yogun kar saganagi",
    95: "gok gurultulu firtina", 96: "dolulu firtina", 99: "siddetli dolulu firtina",
}


def internet_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo'nun sade (lite) arayuzunde arama yapar. API anahtari gerekmez."""
    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        # DDG'nin HTML'inde href, class'tan once gelir ve class tek tirnaklidir:
        #   <a rel="nofollow" href="https://..." class='result-link'>Baslik</a>
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
            return f"'{query}' icin internet sonuclari:\n" + "\n".join(results)
    except requests.RequestException:
        pass  # asagidaki Wikipedia yedegine dus

    return _wikipedia_search(query, max_results)


def _wikipedia_search(query: str, max_results: int) -> str:
    """Yedek arama: Turkce Wikipedia API'si."""
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
            return f"'{query}' icin sonuc bulunamadi."
        lines = []
        for i, item in enumerate(items, start=1):
            snippet = html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
            slug = item["title"].replace(" ", "_")
            lines.append(f"{i}. {item['title']}\n   {snippet}\n   https://tr.wikipedia.org/wiki/{slug}")
        return f"'{query}' icin Wikipedia sonuclari:\n" + "\n".join(lines)
    except requests.RequestException as exc:
        return f"Arama yapilamadi: {exc}"


def get_weather(city: str) -> str:
    """Bir sehrin guncel hava durumunu Open-Meteo'dan getirir. API anahtari gerekmez."""
    if not city or not city.strip():
        return "Hava durumu icin bir sehir adi belirtmelisiniz."
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "tr"},
            timeout=TIMEOUT,
        ).json()
        places = geo.get("results")
        if not places:
            return f"'{city}' adinda bir sehir bulunamadi."
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
            f"ruzgar {now['wind_speed_10m']} km/s. (Olcum: {now['time']})"
        )
    except (requests.RequestException, KeyError) as exc:
        return f"Hava durumu alinamadi: {exc}"


def check_part_status(component: str = "") -> str:
    """Bir arac bileseninin DEMO durumunu race_data'dan getirir.

    Bilinen bilesenler: fren balatalari, fren diskleri, lastikler, motor yagi, aku.
    Bilinmeyen bir bilesen icin istisna firlatmaz; acik bir aciklama doner. Argumanin
    hic verilmemesi (varsayilan bos deger) de guvenli sekilde ele alinir.
    """
    if not component or not component.strip():
        return "Hangi arac bilesenini kontrol edecegimi belirtmelisiniz."

    key = component.strip().lower()
    resolved = race_data.COMPONENT_ALIASES.get(key)
    if resolved is None and key in race_data.COMPONENTS:
        resolved = key
    if resolved is None:
        known = ", ".join(c["name"] for c in race_data.COMPONENTS.values())
        return (
            f"'{component}' adinda bir bilesen demo verisinde bulunmuyor. "
            f"Bilinen bilesenler: {known}."
        )

    part = race_data.COMPONENTS[resolved]
    lines = [
        f"Bilesen: {part['name']}",
        f"Durum: {part['status']}",
        f"Son muayene: {part['last_inspection']}",
    ]
    if part.get("remaining"):
        lines.append(f"Kalan/Olcum: {part['remaining']}")
    if part.get("warning"):
        lines.append(f"Uyari: {part['warning']}")
    else:
        lines.append("Uyari: yok")
    lines.append(race_data.DATA_DISCLAIMER)
    return "\n".join(lines)


def get_race_regulations(topic: str = "") -> str:
    """Bir yaris yonetmeligi konusunun DEMO ozetini race_data'dan getirir.

    Bilinen konular: frenler, lastikler, guvenlik, elektrik, surucu, teknik muayene.
    Bilinmeyen bir konu icin istisna firlatmaz; bilginin mevcut olmadigini soyler.
    Argumanin hic verilmemesi (varsayilan bos deger) de guvenli sekilde ele alinir.
    """
    if not topic or not topic.strip():
        return "Hangi yonetmelik konusunu sorduğunuzu belirtmelisiniz."

    key = topic.strip().lower()
    resolved = race_data.REGULATION_ALIASES.get(key)
    if resolved is None and key in race_data.REGULATIONS:
        resolved = key
    if resolved is None:
        known = ", ".join(r["topic"] for r in race_data.REGULATIONS.values())
        return (
            f"'{topic}' konusu demo yonetmelik verisinde mevcut degil. "
            f"Bilinen konular: {known}."
        )

    reg = race_data.REGULATIONS[resolved]
    return f"Yonetmelik konusu: {reg['topic']}\n{reg['summary']}\n{race_data.DATA_DISCLAIMER}"


TOOLS = {
    "internet_search": internet_search,
    "get_weather": get_weather,
    "check_part_status": check_part_status,
    "get_race_regulations": get_race_regulations,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": (
                "Guncel/harici bilgi icin internette arama yapar: haberler, guncel olaylar, "
                "genel bilgi ya da kullanici acikca web aramasi istediginde. Ic araclarin "
                "(hava, bilesen, yonetmelik) karsiladigi sorular icin KULLANMA."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Arama sorgusu. Guncel/son bilgi isteniyorsa yil olarak "
                            f"{CURRENT_YEAR} kullan; kullanicinin verdigi yili degistirme."
                        ),
                    },
                    "max_results": {"type": "integer", "description": "Sonuc sayisi (varsayilan 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Bir sehrin GUNCEL hava durumunu (sicaklik, nem, ruzgar) canli olarak getirir. "
                "Yaris/antrenman hava durumu ve hava kaynakli hazirlik sorulari icin kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Sehir adi, ornegin 'Istanbul'"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_part_status",
            "description": (
                "Bir arac bileseninin DEMO durumunu getirir: durum, son muayene, kalan omur/olcum "
                "ve uyarilar. Bilesen durumu, bakim, muayene ya da kalan omur sorulari icin kullan. "
                "Gecerli bilesenler: fren balatalari, fren diskleri, lastikler, motor yagi, aku."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "description": "Bilesen adi, ornegin 'fren balatalari' veya 'lastikler'",
                    },
                },
                "required": ["component"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_race_regulations",
            "description": (
                "Bir yaris yonetmeligi konusunun DEMO ozetini getirir. Yaris ya da teknik "
                "yonetmelik sorulari icin kullan. Gecerli konular: frenler, lastikler, guvenlik, "
                "elektrik, surucu, teknik muayene."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Yonetmelik konusu, ornegin 'guvenlik' veya 'frenler'",
                    },
                },
                "required": ["topic"],
            },
        },
    },
]
