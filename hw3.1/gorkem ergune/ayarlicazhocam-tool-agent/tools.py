"""
ayarlicazhocam-tool-agent — Araç (tool) implementasyonları.

Buradaki fonksiyonlar modelin çağırabileceği gerçek işlevlerdir. Gerçek HTTP
isteklerini DAİMA bu Python kodu yapar; model yalnızca hangi fonksiyonu hangi
argümanlarla çağıracağını söyler. Argümanlar çalıştırılmadan önce doğrulanır.

Kullanılan public API: Open-Meteo (API key gerektirmez)
  - Geocoding : https://geocoding-api.open-meteo.com/v1/search
  - Forecast  : https://api.open-meteo.com/v1/forecast
"""

from __future__ import annotations

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT = 15  # saniye

# Open-Meteo WMO hava durumu kodları -> kısa Türkçe açıklama
WEATHER_CODES = {
    0: "açık",
    1: "genelde açık",
    2: "parçalı bulutlu",
    3: "kapalı",
    45: "sisli",
    48: "kırağılı sis",
    51: "hafif çiseleme",
    53: "orta çiseleme",
    55: "yoğun çiseleme",
    61: "hafif yağmur",
    63: "orta yağmur",
    65: "kuvvetli yağmur",
    71: "hafif kar",
    73: "orta kar",
    75: "yoğun kar",
    77: "kar taneleri",
    80: "hafif sağanak",
    81: "orta sağanak",
    82: "şiddetli sağanak",
    85: "hafif kar sağanağı",
    86: "yoğun kar sağanağı",
    95: "gök gürültülü fırtına",
    96: "dolulu fırtına (hafif)",
    99: "dolulu fırtına (şiddetli)",
}


class ToolError(Exception):
    """Araç çalıştırma / doğrulama hatası (kullanıcıya gösterilebilir)."""


# --------------------------------------------------------------------------- #
# Araç 1: get_weather
# --------------------------------------------------------------------------- #
def get_weather(city: str) -> dict:
    """Bir şehrin güncel hava durumunu Open-Meteo'dan getirir.

    Adımlar:
      1) Geocoding endpoint'i ile şehir adını enlem/boylama çevirir.
      2) Forecast endpoint'inden güncel sıcaklık, nem, rüzgâr ve durumu alır.

    Sıcaklık Celsius (°C) olarak döner.
    """
    # --- Argüman doğrulama ---
    if not isinstance(city, str) or not city.strip():
        raise ToolError("get_weather: 'city' boş olmayan bir metin olmalı.")
    city = city.strip()

    # --- 1) Geocoding ---
    geo = requests.get(
        GEOCODING_URL,
        params={"name": city, "count": 1, "language": "tr", "format": "json"},
        timeout=HTTP_TIMEOUT,
    )
    geo.raise_for_status()
    results = geo.json().get("results") or []
    if not results:
        raise ToolError(f"'{city}' için konum bulunamadı. Şehir adını kontrol et.")

    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    resolved = loc.get("name", city)
    country = loc.get("country", "")

    # --- 2) Forecast ---
    fc = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        },
        timeout=HTTP_TIMEOUT,
    )
    fc.raise_for_status()
    current = fc.json().get("current", {})

    code = current.get("weather_code")
    return {
        "city": resolved,
        "country": country,
        "latitude": lat,
        "longitude": lon,
        "temperature_c": current.get("temperature_2m"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "condition": WEATHER_CODES.get(code, f"kod {code}"),
    }


# --------------------------------------------------------------------------- #
# Araç 2: convert_temperature
# --------------------------------------------------------------------------- #
def convert_temperature(value: float, to_unit: str) -> dict:
    """Sıcaklık birimi çevirir (saf Python, API gerektirmez).

    Sözleşme (ödev şemasıyla uyumlu): fonksiyon 'value' ve hedef birim 'to_unit'
    alır. Kaynak birim, hedefin tersidir:
      - to_unit == "F"  ->  value Celsius kabul edilir,  C -> F
      - to_unit == "C"  ->  value Fahrenheit kabul edilir, F -> C
    """
    # --- Argüman doğrulama ---
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ToolError("convert_temperature: 'value' sayısal olmalı.")

    if not isinstance(to_unit, str):
        raise ToolError("convert_temperature: 'to_unit' 'C' veya 'F' olmalı.")
    to_unit = to_unit.strip().upper()
    if to_unit not in ("C", "F"):
        raise ToolError("convert_temperature: 'to_unit' yalnızca 'C' veya 'F' olabilir.")

    if to_unit == "F":
        converted = value * 9 / 5 + 32
        from_unit = "C"
    else:  # "C"
        converted = (value - 32) * 5 / 9
        from_unit = "F"

    return {
        "input_value": round(value, 2),
        "from_unit": from_unit,
        "to_unit": to_unit,
        "converted_value": round(converted, 2),
    }


# --------------------------------------------------------------------------- #
# Dispatch tablosu — modelin ürettiği function_call adını gerçek fonksiyona bağlar
# --------------------------------------------------------------------------- #
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "convert_temperature": convert_temperature,
}


def dispatch(name: str, args: dict) -> dict:
    """Model tarafından istenen aracı doğrulayıp çalıştırır, JSON-uyumlu dict döner."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        raise ToolError(f"Bilinmeyen araç: {name}")
    args = args or {}
    return fn(**args)


if __name__ == "__main__":
    # Hızlı offline duman testi (API key gerektirmez)
    import json

    print(json.dumps(get_weather("Ankara"), ensure_ascii=False, indent=2))
    print(json.dumps(convert_temperature(20, "F"), ensure_ascii=False, indent=2))
