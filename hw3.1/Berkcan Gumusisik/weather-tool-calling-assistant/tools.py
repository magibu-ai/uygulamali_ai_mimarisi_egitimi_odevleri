"""Open-Meteo backed tools and JSON schemas for the SkyBrief agent."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

WMO_CODES = {
    0: "açık gökyüzü",
    1: "çoğunlukla açık",
    2: "parçalı bulutlu",
    3: "kapalı",
    45: "sisli",
    48: "kırağılı sis",
    51: "hafif çiseleme",
    53: "orta çiseleme",
    55: "yoğun çiseleme",
    61: "hafif yağmur",
    63: "orta yağmur",
    65: "şiddetli yağmur",
    71: "hafif kar",
    73: "orta kar",
    75: "yoğun kar",
    80: "sağanak",
    81: "güçlü sağanak",
    82: "çok şiddetli sağanak",
    95: "gök gürültülü fırtına",
    96: "dolu ile fırtına",
    99: "şiddetli dolu ile fırtına",
}


def _get_json(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
    request = Request(f"{url}?{query}", headers={"User-Agent": "SkyBrief/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_location(place_name: str) -> dict[str, Any]:
    """Resolve a place name to geographic coordinates via Open-Meteo Geocoding."""
    data = _get_json(
        GEOCODING_URL,
        {"name": place_name, "count": 1, "language": "tr", "format": "json"},
    )
    results = data.get("results") or []
    if not results:
        return {"error": f"'{place_name}' için konum bulunamadı."}

    hit = results[0]
    return {
        "name": hit.get("name"),
        "country": hit.get("country"),
        "admin1": hit.get("admin1"),
        "latitude": hit.get("latitude"),
        "longitude": hit.get("longitude"),
        "timezone": hit.get("timezone"),
    }


def get_atmosphere_snapshot(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch live atmospheric conditions for a coordinate pair."""
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "precipitation",
                    "weather_code",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "uv_index",
                ]
            ),
            "timezone": "auto",
        },
    )
    current = data.get("current") or {}
    code = current.get("weather_code")
    return {
        "observed_at": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "wind_kmh": current.get("wind_speed_10m"),
        "wind_gusts_kmh": current.get("wind_gusts_10m"),
        "uv_index": current.get("uv_index"),
        "condition": WMO_CODES.get(code, f"kod {code}"),
        "weather_code": code,
        "timezone": data.get("timezone"),
    }


def get_horizon_forecast(latitude: float, longitude: float, days: int = 3) -> dict[str, Any]:
    """Fetch a short multi-day forecast summary."""
    days = max(1, min(int(days), 7))
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                    "uv_index_max",
                ]
            ),
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    daily = data.get("daily") or {}
    days_out = []
    dates = daily.get("time") or []
    for i, date in enumerate(dates):
        code = (daily.get("weather_code") or [None])[i]
        days_out.append(
            {
                "date": date,
                "condition": WMO_CODES.get(code, f"kod {code}"),
                "temp_max_c": (daily.get("temperature_2m_max") or [None])[i],
                "temp_min_c": (daily.get("temperature_2m_min") or [None])[i],
                "precip_mm": (daily.get("precipitation_sum") or [None])[i],
                "precip_probability_pct": (daily.get("precipitation_probability_max") or [None])[i],
                "wind_max_kmh": (daily.get("wind_speed_10m_max") or [None])[i],
                "uv_index_max": (daily.get("uv_index_max") or [None])[i],
            }
        )
    return {"timezone": data.get("timezone"), "days": days_out}


def get_air_quality_index(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current air-quality metrics for a coordinate pair."""
    data = _get_json(
        AIR_QUALITY_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "european_aqi,us_aqi,pm10,pm2_5,ozone,nitrogen_dioxide",
            "timezone": "auto",
        },
    )
    current = data.get("current") or {}
    european = current.get("european_aqi")
    return {
        "observed_at": current.get("time"),
        "european_aqi": european,
        "us_aqi": current.get("us_aqi"),
        "pm2_5": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "ozone": current.get("ozone"),
        "nitrogen_dioxide": current.get("nitrogen_dioxide"),
        "category": _aqi_category(european),
    }


def rank_outdoor_viability(
    temperature_c: float,
    wind_kmh: float,
    precipitation_mm: float,
    uv_index: float,
    european_aqi: float | None = None,
    activity: str = "genel",
) -> dict[str, Any]:
    """Score how suitable outdoor conditions are for a given activity."""
    score = 100.0
    notes: list[str] = []

    if temperature_c < 0:
        score -= 35
        notes.append("Donma riski yüksek.")
    elif temperature_c < 8:
        score -= 18
        notes.append("Hava serin; katmanlı giyinmek iyi olur.")
    elif temperature_c > 32:
        score -= 22
        notes.append("Sıcaklık yüksek; gölge ve su kritik.")
    elif 16 <= temperature_c <= 26:
        score += 5
        notes.append("Sıcaklık konfor bandında.")

    if wind_kmh >= 40:
        score -= 25
        notes.append("Rüzgar oldukça kuvvetli.")
    elif wind_kmh >= 25:
        score -= 12
        notes.append("Rüzgar rahatsız edici olabilir.")

    if precipitation_mm >= 2:
        score -= 30
        notes.append("Yağış belirgin.")
    elif precipitation_mm > 0:
        score -= 12
        notes.append("Hafif yağış ihtimali/varlığı var.")

    if uv_index >= 8:
        score -= 15
        notes.append("UV endeksi çok yüksek; koruma şart.")
    elif uv_index >= 6:
        score -= 8
        notes.append("UV endeksi yüksek.")

    if european_aqi is not None:
        if european_aqi >= 80:
            score -= 30
            notes.append("Hava kalitesi zayıf; açık hava aktivitesi sınırlanmalı.")
        elif european_aqi >= 50:
            score -= 15
            notes.append("Hava kalitesi orta; hassas gruplar dikkat etmeli.")
        else:
            notes.append("Hava kalitesi kabul edilebilir.")

    activity_l = (activity or "genel").lower()
    if activity_l in {"koşu", "running", "kosu"}:
        if temperature_c > 28:
            score -= 10
            notes.append("Koşu için sıcaklık biraz yüksek.")
        if european_aqi is not None and european_aqi >= 40:
            score -= 8
            notes.append("Koşu için hava kalitesi ideal değil.")
    elif activity_l in {"piknik", "picnic"}:
        if precipitation_mm > 0:
            score -= 10
            notes.append("Piknik için kuru hava tercih edilir.")
    elif activity_l in {"fotoğraf", "photography", "fotograf"}:
        if (temperature_c is not None) and wind_kmh < 20 and precipitation_mm == 0:
            notes.append("Fotoğraf için gökyüzü ve rüzgar koşulları uygun görünüyor.")

    score = max(0, min(100, round(score)))
    if score >= 80:
        verdict = "çok uygun"
    elif score >= 60:
        verdict = "uygun"
    elif score >= 40:
        verdict = "koşullu uygun"
    else:
        verdict = "uygun değil"

    return {
        "activity": activity,
        "score": score,
        "verdict": verdict,
        "notes": notes,
    }


def _aqi_category(european_aqi: float | None) -> str:
    if european_aqi is None:
        return "bilinmiyor"
    if european_aqi < 20:
        return "çok iyi"
    if european_aqi < 40:
        return "iyi"
    if european_aqi < 60:
        return "orta"
    if european_aqi < 80:
        return "kötü"
    if european_aqi < 100:
        return "çok kötü"
    return "tehlikeli"


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "resolve_location",
            "description": (
                "Bir yer adını (şehir, ilçe, ülke) enlem/boylam ve zaman dilimine çevirir. "
                "Hava verisi çekmeden önce konum çözülmelidir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place_name": {
                        "type": "string",
                        "description": "Aranacak yer adı, örn. 'İstanbul', 'Tokyo', 'Cappadocia'",
                    }
                },
                "required": ["place_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_atmosphere_snapshot",
            "description": (
                "Belirli koordinatlar için anlık sıcaklık, hissedilen sıcaklık, nem, rüzgar, "
                "UV, bulutluluk ve hava durumu özetini getirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "Enlem"},
                    "longitude": {"type": "number", "description": "Boylam"},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_horizon_forecast",
            "description": (
                "Belirli koordinatlar için 1-7 günlük kısa vadeli tahmin özeti döndürür "
                "(min/max sıcaklık, yağış, rüzgar, UV)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days": {
                        "type": "integer",
                        "description": "Kaç günlük tahmin (1-7). Varsayılan 3.",
                        "default": 3,
                    },
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_air_quality_index",
            "description": (
                "Belirli koordinatlar için Avrupa AQI, ABD AQI, PM2.5, PM10 ve ozon değerlerini getirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank_outdoor_viability",
            "description": (
                "Toplanan meteorolojik ve hava kalitesi verilerine göre açık hava aktivitesi "
                "uygunluk skorunu (0-100) ve gerekçeleri üretir. API çağırmaz; yerel hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "temperature_c": {"type": "number"},
                    "wind_kmh": {"type": "number"},
                    "precipitation_mm": {"type": "number"},
                    "uv_index": {"type": "number"},
                    "european_aqi": {"type": "number"},
                    "activity": {
                        "type": "string",
                        "description": "Aktivite türü: genel, koşu, piknik, fotoğraf",
                        "default": "genel",
                    },
                },
                "required": [
                    "temperature_c",
                    "wind_kmh",
                    "precipitation_mm",
                    "uv_index",
                ],
            },
        },
    },
]


TOOL_IMPLS: dict[str, Callable[..., dict[str, Any]]] = {
    "resolve_location": resolve_location,
    "get_atmosphere_snapshot": get_atmosphere_snapshot,
    "get_horizon_forecast": get_horizon_forecast,
    "get_air_quality_index": get_air_quality_index,
    "rank_outdoor_viability": rank_outdoor_viability,
}


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    fn = TOOL_IMPLS.get(name)
    if fn is None:
        return {"error": f"Bilinmeyen araç: {name}"}
    try:
        return fn(**arguments)
    except TypeError as exc:
        return {"error": f"Argüman hatası ({name}): {exc}"}
    except Exception as exc:  # noqa: BLE001 - surface tool failures to the agent UI
        return {"error": f"Araç çalıştırma hatası ({name}): {exc}"}
