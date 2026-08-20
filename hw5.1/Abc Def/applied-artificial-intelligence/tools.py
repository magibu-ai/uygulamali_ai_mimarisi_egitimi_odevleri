"""Modelin cagirabilecegi 4 arac.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele
geri beslenir. Hicbiri hata firlatmaz — hata olursa Turkce bir aciklama doner,
boylece sohbet dongusu cokmez.

TOOL_SCHEMAS listesi ise modele "elinde su araclar var" demenin JSON halidir.
"""

import requests

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
POLLEN_NAME_MAPPING = {
    "alder_pollen": "Kızılağaç Poleni",
    "birch_pollen": "Huş Poleni",
    "grass_pollen": "Çim Poleni",
    "mugwort_pollen": "Pelin Poleni",
    "olive_pollen": "Zeytin Poleni",
    "ragweed_pollen": "Kanaryaotu Poleni"
}

def get_alder_pollen_level(value):
    if value >= 50:
        return "Yüksek"
    elif value >= 11:
        return "Orta"
    return "Düşük"

def get_birch_pollen_level(value):
    if value >= 81:
        return "Yüksek"
    elif value >= 11:
        return "Orta"
    return "Düşük"

def get_grass_pollen_level(value):
    if value >= 20:
        return "Yüksek"
    elif value >= 5:
        return "Orta"
    return "Düşük"

def get_mugwort_pollen_level(value):
    if value >= 15:
        return "Yüksek"
    elif value >= 6:
        return "Orta"
    return "Düşük"

def get_olive_pollen_level(value):
    if value >= 51:
        return "Yüksek"
    elif value >= 15:
        return "Orta"
    return "Düşük"

def get_ragweed_pollen_level(value):
    if value >= 11:
        return "Yüksek"
    elif value >= 6:
        return "Orta"
    return "Düşük"

POLLEN_LEVEL_MAPPING = {
    "alder_pollen": get_alder_pollen_level,
    "birch_pollen": get_birch_pollen_level,
    "grass_pollen": get_grass_pollen_level,
    "mugwort_pollen": get_mugwort_pollen_level,
    "olive_pollen": get_olive_pollen_level,
    "ragweed_pollen": get_ragweed_pollen_level
}


def get_pollen_status(city: str) -> str:
    """Bir sehrin guncel polen durumunu Open-Meteo'dan getirir. API anahtari gerekmez."""
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
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": POLLEN_NAME_MAPPING.keys(),
                "timezone": "auto",
            },
            timeout=TIMEOUT,
        ).json()
        now = data["current"]

        return (
            ", ".join([f"{POLLEN_NAME_MAPPING[pollen_name]}: {POLLEN_LEVEL_MAPPING[pollen_name](now[pollen_name] * 10)} seviye." for pollen_name in POLLEN_NAME_MAPPING.keys() if pollen_name in now])
        )
    except (requests.RequestException, KeyError) as exc:
        print(f"Polen durumu alınamadı: {exc}")
        return "Polen durumu alınamadı"


TOOLS = {
    "get_pollen_status": get_pollen_status
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_pollen_status",
            "description": "Bir sehrin guncel polen durumunu getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Sehir adi, ornegin 'Istanbul'"},
                },
                "required": ["city"],
            },
        },
    }
]
