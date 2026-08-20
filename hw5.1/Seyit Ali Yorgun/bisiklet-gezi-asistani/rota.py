"""Bisiklet turu icin cekirdek hesaplar: yer bulma, rota, fizik modeli.

Buradaki hicbir fonksiyon LLM'e guvenmez; hepsi ya gercek bir API'den veri ceker
ya da deterministik bir formul calistirir. Modelin isi bu sonuclari yorumlamak,
uretmek degil.

Kullanilan ucretsiz servisler (hicbiri API anahtari istemez):
    Open-Meteo Geocoding : yer adi -> enlem/boylam
    Nominatim (OSM)      : yedek yer bulucu ("Kas, Antalya" gibi bilesik adresler)
    BRouter              : bisiklet profilinde rota + gercek tirmanis metresi
    Open-Meteo Forecast  : saatlik hava, ruzgar hizi ve YONU
"""

import math

import requests

TIMEOUT = 45
HEADERS = {"User-Agent": "bisiklet-gezi-asistani/1.0 (egitim odevi)"}

G = 9.80665  # yercekimi ivmesi (m/s^2)

# Zemin tipine gore yuvarlanma direnci katsayisi (Crr).
# Degerler gercek yol kosullari icindir: catlakli asfalt, tam sisirilmemis lastik,
# yuklu heybe. Laboratuvar rulo testi degerlerinden (0.003-0.004) bilerek yuksek.
ZEMIN = {
    "asfalt": 0.006,
    "karisik": 0.010,
    "toprak": 0.016,
}

# Surus pozisyonuna gore surtunme alani CdA (m^2) ve tipik bisiklet agirligi (kg).
BISIKLET = {
    "sehir": {"cda": 0.48, "kg": 14.0, "zemin": "asfalt"},
    "trekking": {"cda": 0.42, "kg": 13.0, "zemin": "karisik"},
    "gravel": {"cda": 0.36, "kg": 10.0, "zemin": "karisik"},
    "yol": {"cda": 0.32, "kg": 8.5, "zemin": "asfalt"},
    "dag": {"cda": 0.50, "kg": 13.5, "zemin": "toprak"},
}

# Kondisyon seviyesine gore surdurulebilir pedal gucu (Watt).
# Uzun turda kimse FTP'sinde pedal cevirmez; bunlar 3-6 saatlik tempo degerleridir.
# 75 kg bir surucu icin sirasiyla ~1.0 / 1.5 / 2.1 / 2.7 W/kg.
KONDISYON = {
    "baslangic": 75,
    "orta": 110,
    "iyi": 155,
    "ileri": 200,
}

# BRouter bisiklet profilleri (kullanicinin bisiklet tipine esleniyor).
BROUTER_PROFIL = {
    "sehir": "trekking",
    "trekking": "trekking",
    "gravel": "gravel",
    "yol": "fastbike",
    "dag": "mtb",
}

WMO_TR = {
    0: "acik", 1: "az bulutlu", 2: "parcali bulutlu", 3: "cok bulutlu",
    45: "sisli", 48: "kirragi sisi", 51: "hafif ciseleme", 53: "ciseleme",
    55: "yogun ciseleme", 61: "hafif yagmur", 63: "yagmurlu", 65: "kuvvetli yagmur",
    71: "hafif kar", 73: "kar yagisli", 75: "yogun kar", 77: "kar taneli",
    80: "saganak", 81: "kuvvetli saganak", 82: "siddetli saganak",
    85: "kar saganagi", 86: "yogun kar saganagi",
    95: "gok gurultulu firtina", 96: "dolulu firtina", 99: "siddetli dolulu firtina",
}


class RotaHatasi(Exception):
    """Disaridaki bir servis cevap vermedigi ya da yer bulunamadigi durum."""


# ----------------------------------------------------------------- yer bulma

def yer_bul(ad: str, ulke: str = "TR") -> dict:
    """Yer adini enlem/boylama cevirir. Once Open-Meteo, olmazsa Nominatim.

    Iki kademeli olmasinin sebebi: Open-Meteo sadece yerlesim adlarini bilir,
    Nominatim ise "Kas, Antalya" ya da "Sariyer sahil yolu" gibi bilesik
    ifadeleri de cozer ama daha yavas ve rate-limit'lidir.
    """
    ad = ad.strip()
    try:
        data = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ad, "count": 1, "language": "tr", "countryCode": ulke},
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        sonuc = (data.get("results") or [None])[0]
        if sonuc:
            return {
                "ad": sonuc["name"],
                "lat": float(sonuc["latitude"]),
                "lon": float(sonuc["longitude"]),
                "il": sonuc.get("admin1", ""),
            }
    except (requests.RequestException, ValueError, KeyError):
        pass

    try:
        data = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": ad, "format": "json", "limit": 1, "countrycodes": ulke.lower()},
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
    except (requests.RequestException, ValueError) as exc:
        raise RotaHatasi(f"Yer arama servisine ulasilamadi: {exc}") from exc

    if not data:
        raise RotaHatasi(f"'{ad}' bulunamadi. Daha acik yazin, ornegin 'Kas, Antalya'.")
    ilk = data[0]
    return {
        "ad": ilk["display_name"].split(",")[0],
        "lat": float(ilk["lat"]),
        "lon": float(ilk["lon"]),
        "il": ilk["display_name"].split(",")[1].strip() if "," in ilk["display_name"] else "",
    }


def yon_acisi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Iki nokta arasindaki gidis yonu (pusula derecesi, 0=kuzey)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(f2)
    y = math.cos(f1) * math.sin(f2) - math.sin(f1) * math.cos(f2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# --------------------------------------------------------------------- rota

def rota_getir(baslangic: str, bitis: str, bisiklet: str = "trekking") -> dict:
    """BRouter'dan bisiklete uygun rotayi ceker.

    BRouter'in donen 'filtered ascend' degeri onemlidir: ham GPS gurultusunu
    temizlenmis toplam tirmanis metresidir. Duz sanilan bir rotanin 800 m
    tirmanis icermesi, gezinin suresini iki katina cikarabilir.
    """
    a = yer_bul(baslangic)
    b = yer_bul(bitis)
    profil = BROUTER_PROFIL.get(bisiklet, "trekking")

    try:
        cevap = requests.get(
            "https://brouter.de/brouter",
            params={
                "lonlats": f"{a['lon']},{a['lat']}|{b['lon']},{b['lat']}",
                "profile": profil,
                "alternativeidx": 0,
                "format": "geojson",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RotaHatasi(f"Rota servisine ulasilamadi: {exc}") from exc

    if cevap.status_code != 200 or not cevap.text.lstrip().startswith("{"):
        raise RotaHatasi(f"Rota bulunamadi ({cevap.status_code}): {cevap.text[:150]}")

    ozellik = cevap.json()["features"][0]
    p = ozellik["properties"]
    koordinatlar = ozellik["geometry"]["coordinates"]
    yukseklikler = [c[2] for c in koordinatlar if len(c) > 2]

    return {
        "baslangic": a,
        "bitis": b,
        "profil": profil,
        "mesafe_km": round(int(p["track-length"]) / 1000, 1),
        "tirmanis_m": int(p["filtered ascend"]),
        "brouter_sure_dk": round(int(p["total-time"]) / 60),
        "min_rakim_m": int(min(yukseklikler)) if yukseklikler else None,
        "max_rakim_m": int(max(yukseklikler)) if yukseklikler else None,
        "yon_derece": round(yon_acisi(a["lat"], a["lon"], b["lat"], b["lon"])),
        "nokta_sayisi": len(koordinatlar),
    }


# ---------------------------------------------------------------- hava/ruzgar

def hava_getir(lat: float, lon: float, gun_ofseti: int = 0) -> dict:
    """Bir noktanin gunluk hava ozetini ve gunduz ortalama ruzgarini dondurur.

    Ruzgar YONU bisiklette sicaklik kadar onemlidir: 20 km/s karsi ruzgar,
    duz yolda %5'lik bir yokusa denk gelir. Bu yuzden hem hiz hem yon donuyor.
    """
    try:
        data = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_direction_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max,sunrise,sunset",
                "timezone": "auto",
                "forecast_days": max(1, gun_ofseti + 1),
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
    except (requests.RequestException, ValueError) as exc:
        raise RotaHatasi(f"Hava servisine ulasilamadi: {exc}") from exc

    if "daily" not in data:
        raise RotaHatasi(f"Hava verisi alinamadi: {str(data)[:150]}")

    g = data["daily"]
    i = min(gun_ofseti, len(g["time"]) - 1)

    # Gunun 08:00-18:00 arasi (tipik surus penceresi) ortalama ruzgari.
    saatlik = data["hourly"]
    dilim = slice(i * 24 + 8, i * 24 + 19)
    hizlar = saatlik["wind_speed_10m"][dilim]
    yonler = saatlik["wind_direction_10m"][dilim]
    # Yon ortalamasi acisal oldugu icin vektorel alinir (350 ile 10'un ortalamasi 180 degil 0'dir).
    if yonler:
        vx = sum(math.sin(math.radians(y)) for y in yonler) / len(yonler)
        vy = sum(math.cos(math.radians(y)) for y in yonler) / len(yonler)
        ruzgar_yon = round((math.degrees(math.atan2(vx, vy)) + 360) % 360)
    else:
        ruzgar_yon = 0

    return {
        "tarih": g["time"][i],
        "durum": WMO_TR.get(g["weather_code"][i], "bilinmiyor"),
        "sicaklik_max": g["temperature_2m_max"][i],
        "sicaklik_min": g["temperature_2m_min"][i],
        "yagis_ihtimali": g["precipitation_probability_max"][i],
        "ruzgar_kmh": round(sum(hizlar) / len(hizlar), 1) if hizlar else 0.0,
        "ruzgar_yon_derece": ruzgar_yon,
        "gun_dogumu": g["sunrise"][i][-5:],
        "gun_batimi": g["sunset"][i][-5:],
    }


def ruzgar_bileseni(ruzgar_kmh: float, ruzgar_yon: float, gidis_yonu: float) -> float:
    """Rota yonune dusen ruzgar bileseni (km/s). Pozitif = karsi ruzgar.

    Meteorolojide ruzgar yonu, ruzgarin GELDIGI yondur. Gidis yonu ile ayni ise
    tam karsidan eser.
    """
    return round(ruzgar_kmh * math.cos(math.radians(ruzgar_yon - gidis_yonu)), 1)


# ------------------------------------------------------------- efor modeli

def efor_hesapla(
    mesafe_km: float,
    tirmanis_m: float,
    surucu_kg: float = 75.0,
    bisiklet: str = "trekking",
    kondisyon: str = "orta",
    karsi_ruzgar_kmh: float = 0.0,
    sicaklik_c: float = 20.0,
    ortalama_rakim_m: float = 200.0,
) -> dict:
    """Fiziksel enerji dengesinden sure, kalori, su ve karbonhidrat ihtiyacini cikarir.

    Model: toplam mekanik is = yuvarlanma + hava direnci + tirmanis potansiyeli.

        E_yuvarlanma = Crr * m * g * D
        E_tirmanis   = m * g * h
        E_hava       = 0.5 * rho * CdA * v_bagil^2 * D

    Hava direnci hiza bagli, hiz ise sureye bagli oldugu icin denklem kendine
    gonderme yapar; sabit nokta iterasyonu ile 30 adimda cozuluyor.

    Kalori: insan kasi mekanik ise ~%24 verimle calisir, gerisi isi olur.
    """
    if mesafe_km <= 0:
        raise ValueError("mesafe_km sifirdan buyuk olmali.")

    tanim = BISIKLET.get(bisiklet, BISIKLET["trekking"])
    crr = ZEMIN[tanim["zemin"]]
    cda = tanim["cda"]
    guc = KONDISYON.get(kondisyon, KONDISYON["orta"])

    m = surucu_kg + tanim["kg"]
    d = mesafe_km * 1000.0
    # Hava yogunlugu rakimla duser (barometrik yaklasim) ve sicaklikla seyrelir.
    rho = 1.225 * math.exp(-ortalama_rakim_m / 8500.0) * (288.15 / (sicaklik_c + 273.15))
    ruzgar_ms = karsi_ruzgar_kmh / 3.6

    e_yuvarlanma = crr * m * G * d
    e_tirmanis = m * G * max(0.0, tirmanis_m)

    v = 5.5  # ilk tahmin: ~20 km/s
    for _ in range(30):
        v_bagil = v + ruzgar_ms
        # Isaret korunur: arkadan gelen kuvvetli ruzgar direnci negatife cevirebilir.
        e_hava = 0.5 * rho * cda * abs(v_bagil) * v_bagil * d
        e_toplam = max(1.0, e_yuvarlanma + e_tirmanis + e_hava)
        sure_s = e_toplam / (guc * 0.97)  # 0.97: aktarma organi verimi
        yeni_v = d / sure_s
        if abs(yeni_v - v) < 0.001:
            v = yeni_v
            break
        v = 0.5 * v + 0.5 * yeni_v  # salinimi bastirmak icin yumusatma

    v = max(v, 1.4)  # 5 km/s alt siniri: altinda insan iter, pedal cevirmez
    sure_saat = mesafe_km / (v * 3.6)
    e_mekanik = guc * 0.97 * sure_saat * 3600
    kalori = e_mekanik / 0.24 / 4184.0

    # Sivi ihtiyaci sicakla dogrusal artar; 15 C'nin altinda taban deger yeterli.
    # Ust sinir 1.2 L/saat: mide bunun uzerini zaten ememez, fazlasi ise yaramaz.
    su_lt_saat = min(1.2, 0.5 + max(0.0, sicaklik_c - 15.0) * 0.045)
    # 90 dakikayi asan eforlarda kas glikojeni tukenir, disaridan karbonhidrat sart.
    karb_g_saat = 60 if sure_saat > 1.5 else 30

    return {
        "ortalama_hiz_kmh": round(v * 3.6, 1),
        "sure_saat": round(sure_saat, 2),
        "sure_metin": f"{int(sure_saat)} sa {round((sure_saat % 1) * 60)} dk",
        "kalori_kcal": round(kalori),
        "su_litre": round(su_lt_saat * sure_saat, 1),
        "karbonhidrat_g": round(karb_g_saat * sure_saat),
        "pedal_gucu_w": guc,
        "tirmanis_payi_yuzde": round(100 * e_tirmanis / max(1.0, e_yuvarlanma + e_tirmanis), 1),
        "zorluk": _zorluk(mesafe_km, tirmanis_m, sure_saat),
    }


def _zorluk(mesafe_km: float, tirmanis_m: float, sure_saat: float) -> str:
    """Mesafe + tirmanis + sureyi tek bir etikete indirger."""
    puan = mesafe_km / 40 + tirmanis_m / 600 + sure_saat / 2.5
    if puan < 2:
        return "kolay"
    if puan < 3.5:
        return "orta"
    if puan < 5.5:
        return "zor"
    return "cok zor"


# ------------------------------------------------------------- ekipman

def ekipman_listesi(
    sicaklik_c: float,
    yagis_ihtimali: int,
    mesafe_km: float,
    sure_saat: float,
    gece_surusu: bool = False,
    kamp: bool = False,
) -> dict:
    """Kosullara gore ekipman listesi uretir. Tamamen kural tabanli, LLM'siz.

    Listeyi modele degil koda yaptirmanin sebebi: model 'kask' yazmayi unutabilir,
    kural unutmaz.
    """
    zorunlu = ["kask", "on/arka lamba", "yedek ic lastik x2", "lastik sokme aparati",
               "el pompasi", "coklu alyan seti", "kimlik + acil durum karti", "telefon + powerbank"]
    giyim = []
    uyari = []

    if sicaklik_c < 5:
        giyim += ["kislik termal tayt", "ruzgar kesen mont", "kapali eldiven", "boyunluk", "sicak corap"]
        uyari.append("Sifira yakin sicaklik: matara donabilir, termos tercih edin.")
    elif sicaklik_c < 12:
        giyim += ["uzun kollu forma", "kolluk/bacaklik", "ince eldiven", "ruzgarlik"]
    elif sicaklik_c < 22:
        giyim += ["kisa kollu forma", "ince kolluk (sabah icin)", "yarim parmak eldiven"]
    else:
        giyim += ["ince nefes alan forma", "gunes gozlugu", "gunes kremi (SPF 30+)", "kolluk (UV korumali)"]
        if sicaklik_c > 30:
            uyari.append("30 C uzeri: sicagin en yogun oldugu 12:00-16:00 arasindan kacinin.")

    if yagis_ihtimali >= 40:
        giyim += ["yagmurluk (nefes alan)", "camurluk", "su gecirmez telefon kilifi"]
        uyari.append(f"Yagis ihtimali %{yagis_ihtimali}: islak asfaltta fren mesafesi 2 katina cikar.")

    if gece_surusu:
        zorunlu += ["yuksek lumenli on far (>=400 lm)", "yedek arka lamba", "reflektif yelek"]

    if sure_saat > 3 or mesafe_km > 70:
        zorunlu += ["2. matara", "yedek dis lastik yamasi", "zincir kilidi (quick link)"]

    if kamp:
        zorunlu += ["heybe/bikepacking cantalari", "cadir + mat", "uyku tulumu", "kamp ocagi"]
        uyari.append("Yuklu bisiklet %15-20 daha yavas gider; sureyi ona gore planlayin.")

    beslenme = [
        f"{max(1, round(sure_saat))} adet enerji bari veya muz",
        "elektrolit tableti" if sicaklik_c > 22 else "tuzlu atistirmalik",
    ]

    return {
        "zorunlu": zorunlu,
        "giyim": giyim,
        "beslenme": beslenme,
        "uyarilar": uyari,
    }
