import os
import math
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

ULKELER = ["at", "be", "ch", "de", "es", "fr", "gb", "it", "nl", "pl"]

PARA_BIRIMI = {
    "at": "EUR", "be": "EUR", "ch": "CHF", "de": "EUR", "es": "EUR",
    "fr": "EUR", "gb": "GBP", "it": "EUR", "nl": "EUR", "pl": "PLN",
}

ULKE_ADI = {
    "at": "Avusturya", "be": "Belçika", "ch": "İsviçre", "de": "Almanya",
    "es": "İspanya", "fr": "Fransa", "gb": "Birleşik Krallık", "it": "İtalya",
    "nl": "Hollanda", "pl": "Polonya",
}

def _ulke_verisi(meslek, ulke, kategori):
    url = f"https://api.adzuna.com/v1/api/jobs/{ulke}/search/1"
    ilan_sayisi = None
    ortalama_maas = None
    istek = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what_phrase": meslek,
        "results_per_page": 1,
    }
    if kategori:
        istek["category"] = kategori
    try:
        cevap = requests.get(url, params=istek, timeout=10)
        cevap.raise_for_status()
        veri = cevap.json()
        ilan_sayisi = veri.get("count")
        ortalama_maas = veri.get("mean")
    except (requests.RequestException, ValueError):
        pass
    return {
        "ulke": ulke,
        "ilan_sayisi": ilan_sayisi,
        "ortalama_maas": ortalama_maas,
        "para_birimi": PARA_BIRIMI.get(ulke, ""),
    }

def meslek_talebi_adzuna(meslek, ulkeler=None, kategori=None):
    if ulkeler is None:
        ulkeler = ULKELER
    with ThreadPoolExecutor(max_workers=5) as calisan:
        return list(calisan.map(lambda u: _ulke_verisi(meslek, u, kategori), ulkeler))

TABAN_ILAN = 10
TAVAN_ILAN = 47502  # havuzdaki en yuksek 10-ulke talebi (proje yoneticisi) ile kalibre edildi
MIN_BASARILI_ULKE = 7  # bu sayidan az ulke basarili olursa guvenilir skor uretilmez
_ONBELLEK = {}
_ONBELLEK_SURESI = 6 * 3600  # basarili sonuclar 6 saat onbellekte tutulur

def skor_bandi(skor):
    if skor >= 75:
        return "Cok yuksek"
    if skor >= 50:
        return "Yuksek"
    if skor >= 25:
        return "Orta"
    return "Dusuk"

def gelecek_skoru(meslek, kategori=None, gosterilecek_ulke=None):
    anahtar = (meslek, kategori)
    simdi = time.time()
    if anahtar in _ONBELLEK:
        zaman, onbellek_sonuc = _ONBELLEK[anahtar]
        if simdi - zaman < _ONBELLEK_SURESI:
            return onbellek_sonuc

    ulke_detay = meslek_talebi_adzuna(meslek, kategori=kategori)
    gecerli = [u for u in ulke_detay if u["ilan_sayisi"] is not None]
    eksik = [ULKE_ADI.get(u["ulke"], u["ulke"]) for u in ulke_detay if u["ilan_sayisi"] is None]
    basari = len(gecerli)
    toplam = len(ulke_detay)

    if basari < MIN_BASARILI_ULKE:
        return {
            "meslek": meslek,
            "hata": f"Yeterli ulke verisi alinamadi ({basari}/{toplam}); guvenilir bir skor uretilmedi.",
            "basari_ulke": basari,
            "toplam_ulke": toplam,
        }

    toplam_ilan = sum(u["ilan_sayisi"] for u in gecerli)
    oran = (math.log(1 + toplam_ilan) - math.log(1 + TABAN_ILAN)) / (math.log(1 + TAVAN_ILAN) - math.log(1 + TABAN_ILAN))
    skor = max(0, min(100, round(oran * 100)))

    sirali = sorted(gecerli, key=lambda u: u["ilan_sayisi"], reverse=True)
    if gosterilecek_ulke:
        sirali = sirali[:gosterilecek_ulke]
    ulke_dagilimi = [
        {**u, "ulke": ULKE_ADI.get(u["ulke"], u["ulke"])}
        for u in sirali
    ]

    sonuc = {
        "meslek": meslek,
        "gelecek_skoru": skor,
        "band": skor_bandi(skor),
        "toplam_ilan": toplam_ilan,
        "basari_ulke": basari,
        "toplam_ulke": toplam,
        "eksik_ulkeler": eksik,
        "veri_guveni": "yuksek" if basari == toplam else "orta",
        "ulke_dagilimi": ulke_dagilimi,
        "aciklama": "Skor, Adzuna'daki 10 Avrupa ulkesinde bu meslek icin acik ilan sayisina dayanir; talep gostergesidir, kesin gelecek tahmini degildir.",
    }
    _ONBELLEK[anahtar] = (simdi, sonuc)
    return sonuc

if __name__ == "__main__":
    print(gelecek_skoru("software developer"))