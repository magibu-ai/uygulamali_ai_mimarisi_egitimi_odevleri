import requests

from datetime import datetime, timedelta, timezone
def get_coordinates(city: str) -> dict:
    """Bir şehir adını enlem ve boylam koordinatlarına çevirir (Open-Meteo geocoding)."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city,       # aradığımız şehir
        "count": 1,         # sadece en iyi 1 sonuç
        "language": "tr",   # Türkçe isimler
        "format": "json",
    }

    # 1) API'ye isteği at, cevabı JSON olarak çöz
    yanit = requests.get(url, params=params, timeout=10)
    veri = yanit.json()

    # 2) Savunmacı kod: results yoksa/boşsa hata döndür
    sonuclar = veri.get("results") or []
    if not sonuclar:
        return {"hata": f"'{city}' icin konum bulunamadi."}

    # 3) İlk sonucu al, SADECE ihtiyacımız olan 3 alanı çıkar
    ilk = sonuclar[0]
    return {
        "sehir": ilk["name"],
        "lat": ilk["latitude"],
        "lon": ilk["longitude"],
    }
def get_earthquakes_near(lat: float, lon: float, radius_km: float = 300,
                         min_magnitude: float = 4.0, days: int = 7) -> dict:
    """Verilen konumun (enlem/boylam) cevresinde, son 'days' gunde, en az
    'min_magnitude' buyuklugundeki depremleri getirir (USGS)."""
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    # "Bugunden N gun once" tarihini hesapla (USGS starttime icin)
    baslangic = datetime.now(timezone.utc) - timedelta(days=days)

    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": radius_km,
        "minmagnitude": min_magnitude,
        "starttime": baslangic.strftime("%Y-%m-%d"),
        "orderby": "time",
        "limit": 20,               # modeli bogmamak icin en fazla 20 deprem
    }

    yanit = requests.get(url, params=params, timeout=10)
    veri = yanit.json()

    depremler = veri.get("features") or []
    if not depremler:
        return {"deprem_sayisi": 0, "depremler": []}

    sonuc = []
    for d in depremler:
        ozellik = d["properties"]
        koordinat = d["geometry"]["coordinates"]   # [boylam, enlem, derinlik]

        # epoch milisaniye -> okunur tarih (1000'e bol: ms -> saniye)
        zaman = datetime.fromtimestamp(ozellik["time"] / 1000, tz=timezone.utc)

        sonuc.append({
            "buyukluk": ozellik["mag"],
            "yer": ozellik["place"],
            "derinlik_km": koordinat[2],           # 3. eleman = derinlik
            "zaman": zaman.strftime("%Y-%m-%d %H:%M UTC"),
        })

    return {"deprem_sayisi": len(sonuc), "depremler": sonuc}
def get_recent_earthquakes(min_magnitude: float = 5.0, hours: int = 24) -> dict:
    """Dunya genelinde son 'hours' saatte, en az 'min_magnitude'
    buyuklugundeki depremleri getirir (USGS)."""
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    # Saat hassasiyeti icin tam tarih-saat (sadece tarih degil)
    baslangic = datetime.now(timezone.utc) - timedelta(hours=hours)

    params = {
        "format": "geojson",
        "minmagnitude": min_magnitude,
        "starttime": baslangic.strftime("%Y-%m-%dT%H:%M:%S"),
        "orderby": "time",
        "limit": 20,
    }

    yanit = requests.get(url, params=params, timeout=10)
    veri = yanit.json()

    depremler = veri.get("features") or []
    if not depremler:
        return {"deprem_sayisi": 0, "depremler": []}

    sonuc = []
    for d in depremler:
        ozellik = d["properties"]
        koordinat = d["geometry"]["coordinates"]
        zaman = datetime.fromtimestamp(ozellik["time"] / 1000, tz=timezone.utc)
        sonuc.append({
            "buyukluk": ozellik["mag"],
            "yer": ozellik["place"],
            "derinlik_km": koordinat[2],
            "zaman": zaman.strftime("%Y-%m-%d %H:%M UTC"),
        })

    return {"deprem_sayisi": len(sonuc), "depremler": sonuc}
# --- Modele verilecek menü (JSON şemaları) ---
ARAC_SEMALARI = [
    {
        "type": "function",
        "function": {
            "name": "get_coordinates",
            "description": "Bir şehir adını enlem ve boylam koordinatlarına çevirir. "
                           "Konuma bağlı deprem sorgularından önce kullanılır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string",
                             "description": "Şehrin adı, örn. 'İstanbul'"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_earthquakes_near",
            "description": "Bir konumun (enlem/boylam) çevresinde, son 'days' günde, "
                           "en az 'min_magnitude' büyüklüğündeki depremleri getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Merkez enlem"},
                    "lon": {"type": "number", "description": "Merkez boylam"},
                    "radius_km": {"type": "number", "description": "Yarıçap (km), varsayılan 300"},
                    "min_magnitude": {"type": "number", "description": "En düşük büyüklük, varsayılan 4.0"},
                    "days": {"type": "integer", "description": "Kaç gün geriye, varsayılan 7"},
                },
                "required": ["lat", "lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_earthquakes",
            "description": "Dünya genelinde son 'hours' saatte, en az 'min_magnitude' "
                           "büyüklüğündeki depremleri getirir. Konum gerekmez.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_magnitude": {"type": "number", "description": "En düşük büyüklük, varsayılan 5.0"},
                    "hours": {"type": "integer", "description": "Kaç saat geriye, varsayılan 24"},
                },
                "required": [],
            },
        },
    },
]

# --- Çalıştırma rehberi (isim -> fonksiyon) ---
ARAC_REHBERI = {
    "get_coordinates": get_coordinates,
    "get_earthquakes_near": get_earthquakes_near,
    "get_recent_earthquakes": get_recent_earthquakes,
}
if __name__ == "__main__":
    konum = get_coordinates("Malatya")
    print("Konum:", konum)

    sonuc = get_earthquakes_near(konum["lat"], konum["lon"],
                                 radius_km=300, min_magnitude=3, days=30)
    print("Deprem sayisi:", sonuc["deprem_sayisi"])
    for d in sonuc["depremler"]:
        print(d)
    print("--- Dunya geneli son depremler ---")
    guncel = get_recent_earthquakes(min_magnitude=4.5, hours=24)
    print("Deprem sayisi:", guncel["deprem_sayisi"])
    for d in guncel["depremler"][:5]:
        print(d)