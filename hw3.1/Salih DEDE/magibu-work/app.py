# Ders5 — Tool Calling / Function Calling Demosu
#
# Tek soru, üç panel:
#   A. Güçlü model  + araçlar açık   -> doğru ve güncel cevap
#   B. Güçlü model  + araçlar kapalı -> güncel veriyi bilemez
#   C. Zayıf model  + araçlar açık   -> araç çağırmayı dener ama bozuk üretir
#
# A/B karşılaştırması tool calling'in kattığını gösterir; A/C karşılaştırması
# model kapasitesinin (araç olsa bile) belirleyici olduğunu gösterir.
#
# Çalıştırma: python3 app.py  (OPENROUTER_API_KEY .env veya ortam değişkeninden okunur)

import json
import os
import queue
import threading
import time

import gradio as gr
import httpx
from openai import OpenAI

# Bu uygulama gerçek GPU işi yapmıyor (sadece OpenRouter API + CPU üzerinde küçük
# hesaplar), ama hesabın ücretsiz Hugging Face Spaces hakkı yalnızca ZeroGPU
# donanımında geçerli. ZeroGPU çalışma zamanı, en az bir @spaces.GPU fonksiyonu
# görmeden Space'i başlatmayı reddediyor; bu yüzden zararsız bir dummy fonksiyon
# tanımlıyoruz. Yerelde `spaces` paketi kurulu değilse sessizce no-op'a düşer.
try:
    import spaces
    _gpu_dekoratoru = spaces.GPU
except ImportError:
    def _gpu_dekoratoru(fn):
        return fn


@_gpu_dekoratoru
def _zero_gpu_kontrolu():
    """ZeroGPU çalışma zamanının aradığı işaret fonksiyon; gerçek iş yapmaz."""
    return True


# --------------------------------------------------------------------------------------
# Ortam
# --------------------------------------------------------------------------------------

def _env_yukle(yol=".env"):
    if not os.path.exists(yol):
        return
    with open(yol, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, _, v = satir.partition("=")
            k, v = k.strip(), v.strip().strip("'\"")
            if v and not os.environ.get(k):
                os.environ[k] = v


_env_yukle()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

MODEL_GUCLU = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:nitro").strip()
# Küçük bir açık model: tool endpoint'i destekliyor (404 vermiyor) ama çok adımlı
# zincirlerde gerçek bir tool_calls üretmek yerine düz metin içine sahte
# <arac_adi>{...}</arac_adi> etiketleri ve UYDURMA sayılar yazıyor — ölçülmüş,
# tekrarlanabilir bir başarısızlık modu.
MODEL_ZAYIF = "meta-llama/llama-3.1-8b-instruct"

_istemci = None


def istemci():
    global _istemci
    if _istemci is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY tanımlı değil. Yerelde .env dosyasına, "
                "HF Spaces'te Settings > Secrets kısmına ekleyin."
            )
        _istemci = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    return _istemci


# --------------------------------------------------------------------------------------
# Araçlar (3 adet: 2 canlı API + 1 zincirleme hesap)
# --------------------------------------------------------------------------------------

HAVA_KODLARI = {
    0: "açık", 1: "az bulutlu", 2: "parçalı bulutlu", 3: "kapalı",
    45: "puslu", 51: "hafif çisenti", 61: "hafif yağmur", 63: "yağmur",
    65: "şiddetli yağmur", 71: "kar", 80: "sağanak", 95: "gök gürültülü fırtına",
}


def hava_durumu(sehir):
    """Bir şehrin anlık hava durumunu döner (Open-Meteo, anahtarsız)."""
    try:
        geo = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": sehir, "count": 1, "language": "tr"}, timeout=15,
        ).json()
        sonuclar = geo.get("results") or []
        if not sonuclar:
            return {"hata": f"'{sehir}' için konum bulunamadı."}
        konum = sonuclar[0]

        veri = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": konum["latitude"], "longitude": konum["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            }, timeout=15,
        ).json()
        anlik = veri.get("current", {})

        return {
            "sehir": f"{konum['name']}, {konum.get('country', '')}".strip(", "),
            "sicaklik_c": anlik.get("temperature_2m"),
            "nem_yuzde": anlik.get("relative_humidity_2m"),
            "ruzgar_kmh": anlik.get("wind_speed_10m"),
            "durum": HAVA_KODLARI.get(anlik.get("weather_code"), "bilinmiyor"),
            "kaynak": "Open-Meteo",
        }
    except Exception as e:
        return {"hata": f"Hava durumu alınamadı: {e}"}


def doviz_cevir(miktar, kaynak_birim, hedef_birim):
    """Güncel ECB kuruyla para birimi çevirir (Frankfurter, anahtarsız)."""
    try:
        kaynak_birim, hedef_birim = kaynak_birim.strip().upper(), hedef_birim.strip().upper()
        miktar = float(miktar)
        if kaynak_birim == hedef_birim:
            return {"miktar": miktar, "sonuc": miktar, "kaynak_birim": kaynak_birim, "hedef_birim": hedef_birim}

        veri = httpx.get(
            "https://api.frankfurter.dev/v1/latest",
            params={"base": kaynak_birim, "symbols": hedef_birim, "amount": miktar}, timeout=15,
        ).json()
        oranlar = veri.get("rates", {})
        if hedef_birim not in oranlar:
            return {"hata": f"{kaynak_birim} -> {hedef_birim} kuru bulunamadı."}

        return {
            "miktar": miktar, "kaynak_birim": kaynak_birim, "hedef_birim": hedef_birim,
            "sonuc": round(oranlar[hedef_birim], 4), "kur_tarihi": veri.get("date"),
            "kaynak": "Frankfurter / ECB",
        }
    except Exception as e:
        return {"hata": f"Döviz çevrilemedi: {e}"}


def sicaklik_cevir(deger, kaynak_birim, hedef_birim):
    """C/F/K arası sıcaklık çevirir (yerel hesap, API'ye gitmez)."""
    try:
        k, h = kaynak_birim.strip().lower()[0], hedef_birim.strip().lower()[0]
        deger = float(deger)
        celsius = {"c": deger, "f": (deger - 32) / 1.8, "k": deger - 273.15}.get(k)
        if celsius is None or h not in "cfk":
            return {"hata": f"'{kaynak_birim}' -> '{hedef_birim}' desteklenmiyor. Sadece C/F/K."}
        sonuc = {"c": celsius, "f": celsius * 1.8 + 32, "k": celsius + 273.15}[h]
        return {
            "girdi": deger, "kaynak_birim": kaynak_birim, "hedef_birim": hedef_birim,
            "sonuc": round(sonuc, 2), "kaynak": "yerel hesap",
        }
    except Exception as e:
        return {"hata": f"Sıcaklık çevrilemedi: {e}"}


KRIPTO_TAKMA_ADLARI = {
    "btc": "bitcoin", "bitcoin": "bitcoin", "eth": "ethereum", "ethereum": "ethereum",
    "sol": "solana", "solana": "solana", "doge": "dogecoin", "dogecoin": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
}


def kripto_fiyat(kripto, para_birimi="usd"):
    """Bir kripto paranın güncel fiyatını döner (CoinGecko, anahtarsız)."""
    try:
        kimlik = KRIPTO_TAKMA_ADLARI.get(kripto.strip().lower(), kripto.strip().lower())
        para_birimi = para_birimi.strip().lower()

        veri = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": kimlik, "vs_currencies": para_birimi, "include_24hr_change": "true"},
            timeout=15,
        ).json()
        if kimlik not in veri:
            return {"hata": f"'{kripto}' CoinGecko'da bulunamadı."}

        kayit = veri[kimlik]
        degisim = kayit.get(f"{para_birimi}_24h_change")
        return {
            "kripto": kimlik, "para_birimi": para_birimi.upper(), "fiyat": kayit.get(para_birimi),
            "degisim_24s_yuzde": round(degisim, 2) if degisim is not None else None,
            "kaynak": "CoinGecko",
        }
    except Exception as e:
        return {"hata": f"Kripto fiyatı alınamadı: {e}"}


WIKI_BASLIKLARI = {"User-Agent": "magibu-ders5-tool-calling/1.0 (egitim odevi; iletisim: salih12dede@gmail.com)"}


def wikipedia_ara(sorgu, dil="tr"):
    """Wikipedia'da arayıp en alakalı maddenin özetini döner (anahtarsız)."""
    try:
        dil = dil.strip().lower() or "tr"
        arama = httpx.get(
            f"https://{dil}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": sorgu, "srlimit": 1, "format": "json"},
            headers=WIKI_BASLIKLARI, timeout=15,
        ).json()
        bulunanlar = arama.get("query", {}).get("search", [])
        if not bulunanlar:
            return {"hata": f"'{sorgu}' için Wikipedia'da sonuç bulunamadı."}
        baslik = bulunanlar[0]["title"]

        ozet = httpx.get(
            f"https://{dil}.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
                    "titles": baslik, "format": "json", "redirects": 1},
            headers=WIKI_BASLIKLARI, timeout=15,
        ).json()
        sayfalar = ozet.get("query", {}).get("pages", {})
        metin = next(iter(sayfalar.values()), {}).get("extract", "").strip()
        if len(metin) > 800:
            metin = metin[:800].rsplit(" ", 1)[0] + "..."

        return {"baslik": baslik, "ozet": metin or "Özet bulunamadı.", "kaynak": f"Wikipedia ({dil})"}
    except Exception as e:
        return {"hata": f"Wikipedia sorgusu başarısız: {e}"}


def son_depremler(min_buyukluk=4.5, son_kac_gun=1):
    """Dünya genelinde son depremleri büyüklüğe göre listeler (USGS, anahtarsız)."""
    try:
        import datetime as dt

        veri = httpx.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={
                "format": "geojson", "minmagnitude": float(min_buyukluk),
                "starttime": f"now-{max(1, min(int(son_kac_gun), 30))}days",
                "orderby": "magnitude", "limit": 5,
            }, timeout=15,
        ).json()

        depremler = []
        for oge in veri.get("features", []):
            ozellik = oge.get("properties", {})
            zaman_ms = ozellik.get("time")
            depremler.append({
                "buyukluk": ozellik.get("mag"), "yer": ozellik.get("place"),
                "zaman_utc": (
                    dt.datetime.fromtimestamp(zaman_ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
                    if zaman_ms else None
                ),
            })
        return {"kriter": f"son {son_kac_gun} gün, büyüklük >= {min_buyukluk}",
                "toplam": len(depremler), "depremler": depremler, "kaynak": "USGS"}
    except Exception as e:
        return {"hata": f"Deprem verisi alınamadı: {e}"}


ARAC_FONKSIYONLARI = {
    "hava_durumu": hava_durumu,
    "doviz_cevir": doviz_cevir,
    "sicaklik_cevir": sicaklik_cevir,
    "kripto_fiyat": kripto_fiyat,
    "wikipedia_ara": wikipedia_ara,
    "son_depremler": son_depremler,
}

ARAC_UST_VERI = {
    "hava_durumu":   {"etiket": "WX",   "saglayici": "Open-Meteo",
                       "aciklama": "Bir şehrin anlık sıcaklık, nem, rüzgar ve hava durumunu getirir."},
    "doviz_cevir":   {"etiket": "FX",   "saglayici": "Frankfurter / ECB",
                       "aciklama": "Güncel kurla iki para birimi arasında çevrim yapar."},
    "sicaklik_cevir":{"etiket": "TEMP", "saglayici": "yerel hesap",
                       "aciklama": "Sıcaklığı Celsius, Fahrenheit ve Kelvin arasında çevirir."},
    "kripto_fiyat":  {"etiket": "BTC",  "saglayici": "CoinGecko",
                       "aciklama": "Bir kripto paranın güncel fiyatını ve 24 saatlik değişimini getirir."},
    "wikipedia_ara": {"etiket": "WIKI", "saglayici": "Wikipedia",
                       "aciklama": "Wikipedia'da arayıp en alakalı maddenin özetini getirir."},
    "son_depremler": {"etiket": "EQ",   "saglayici": "USGS",
                       "aciklama": "Son depremleri büyüklüğe göre sıralı listeler."},
}

ARAC_SEMALARI = [
    {
        "type": "function",
        "function": {
            "name": "hava_durumu",
            "description": "Bir şehrin anlık sıcaklık (Celsius), nem, rüzgar ve hava durumunu verir.",
            "parameters": {
                "type": "object",
                "properties": {"sehir": {"type": "string", "description": "Şehir adı, örn: Ankara"}},
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doviz_cevir",
            "description": "Güncel kurla bir para biriminden diğerine çevirir. Örn: 250 EUR kaç TL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "miktar": {"type": "number", "description": "Çevrilecek miktar"},
                    "kaynak_birim": {"type": "string", "description": "Kaynak para birimi kodu, örn: USD"},
                    "hedef_birim": {"type": "string", "description": "Hedef para birimi kodu, örn: TRY"},
                },
                "required": ["miktar", "kaynak_birim", "hedef_birim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sicaklik_cevir",
            "description": (
                "Sıcaklığı Celsius/Fahrenheit/Kelvin arasında çevirir. "
                "hava_durumu her zaman Celsius döner; kullanıcı başka birim istiyorsa "
                "dönen değeri bu araca ikinci adım olarak ver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "deger": {"type": "number", "description": "Çevrilecek sıcaklık değeri"},
                    "kaynak_birim": {"type": "string", "description": "C, F veya K"},
                    "hedef_birim": {"type": "string", "description": "C, F veya K"},
                },
                "required": ["deger", "kaynak_birim", "hedef_birim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kripto_fiyat",
            "description": "Bir kripto paranın güncel fiyatını ve 24 saatlik yüzde değişimini döner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kripto": {"type": "string", "description": "Kripto adı/sembolü, örn: bitcoin, ETH"},
                    "para_birimi": {"type": "string", "description": "Fiyatın gösterileceği para birimi, örn: usd. Varsayılan usd."},
                },
                "required": ["kripto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia_ara",
            "description": "Wikipedia'da arama yapıp en alakalı maddenin özetini döner. Kişi, yer veya kavram sorularında kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Aranacak konu"},
                    "dil": {"type": "string", "description": "Wikipedia dil kodu: tr veya en. Varsayılan tr."},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "son_depremler",
            "description": "USGS kataloğundan son depremleri büyüklüğe göre sıralı listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_buyukluk": {"type": "number", "description": "Minimum deprem büyüklüğü. Varsayılan 4.5."},
                    "son_kac_gun": {"type": "integer", "description": "Kaç günlük geçmişe bakılacağı (1-30). Varsayılan 1."},
                },
                "required": [],
            },
        },
    },
]


def araci_calistir(ad, argumanlar):
    fonksiyon = ARAC_FONKSIYONLARI.get(ad)
    if fonksiyon is None:
        return {"hata": f"'{ad}' adında bir araç yok."}
    try:
        return fonksiyon(**(argumanlar or {}))
    except TypeError as e:
        return {"hata": f"'{ad}' hatalı argümanlarla çağrıldı: {e}"}


# --------------------------------------------------------------------------------------
# Ajan döngüsü — generator, her adımda olay üretir
# --------------------------------------------------------------------------------------

SISTEM_PROMPTU = (
    "Türkçe konuşan bir asistansın. Hava durumu, döviz kuru, kripto fiyatı, deprem "
    "ve ansiklopedik bilgi gibi GÜNCEL/OLGUSAL sorularda tahmin yürütme; elindeki "
    "araçları çağır. Bir soru birim çevrimi de gerektiriyorsa (örn. Fahrenheit) önce "
    "veriyi al, sonra çevirme aracını ayrı bir adımda çağır. Araç hata döndürürse "
    "kullanıcıya dürüstçe söyle, veri uydurma. Araç gerektirmeyen sorularda araç "
    "çağırmadan doğrudan yanıtla."
)

TOOLSUZ_PROMPTU = (
    "Türkçe konuşan bir asistansın. Hiçbir dış araca/internete erişimin yok. Güncel "
    "hava durumu, döviz kuru, kripto fiyatı, deprem gibi anlık bilgi istenirse bunu "
    "bilemeyeceğini açıkça söyle; uydurma sayı verme."
)

MAKS_TUR = 4
MAKS_DENEME = 2


def _hata_kisalt(e):
    """Sağlayıcı hatalarının uzun ham JSON'ını UI'da okunabilir tek satıra indirger."""
    metin = str(e)
    for ayrac in ('"message":', "'message':"):
        if ayrac in metin:
            parca = metin.split(ayrac, 1)[1].strip().strip("'\"")
            return parca.split('", "code"')[0].split("', 'code'")[0][:180]
    return metin[:180]


def _arguman_coz(cagri):
    try:
        cozulen = json.loads(cagri.function.arguments or "{}")
        return cozulen if isinstance(cozulen, dict) else {}
    except json.JSONDecodeError:
        return {"_cozulemeyen": cagri.function.arguments}


def ajan_calistir(soru, model, araclar_acik):
    """Tool-calling döngüsünü çalıştırır; olayları generator olarak üretir."""
    mesajlar = [
        {"role": "system", "content": SISTEM_PROMPTU if araclar_acik else TOOLSUZ_PROMPTU},
        {"role": "user", "content": soru},
    ]
    semalar = ARAC_SEMALARI if araclar_acik else []

    for tur in range(1, MAKS_TUR + 1):
        yield {"tip": "tur", "tur": tur}

        mesaj, hata = None, None
        for deneme in range(1, MAKS_DENEME + 1):
            try:
                istek = {"model": model, "messages": mesajlar, "temperature": 0.2 if deneme == 1 else 0.6}
                if semalar:
                    istek["tools"] = semalar
                    istek["tool_choice"] = "auto"
                yanit = istemci().chat.completions.create(**istek)
            except Exception as e:
                hata = _hata_kisalt(e)
                yield {"tip": "deneme_hata", "deneme": deneme, "detay": hata}
                continue

            secenekler = getattr(yanit, "choices", None) or []
            if not secenekler:
                hata = str(getattr(yanit, "error", None) or "model boş yanıt döndü")
                yield {"tip": "deneme_hata", "deneme": deneme, "detay": hata}
                continue

            aday = secenekler[0]
            var_arac = bool(getattr(aday.message, "tool_calls", None))
            var_icerik = bool((aday.message.content or "").strip())
            if var_arac or var_icerik:
                mesaj = aday.message
                hata = None
                break

            hata = f"finish_reason={aday.finish_reason}, native={getattr(aday, 'native_finish_reason', None)}"
            yield {"tip": "deneme_hata", "deneme": deneme, "detay": hata}

        if mesaj is None:
            yield {"tip": "hata", "mesaj": f"Model geçerli bir yanıt üretemedi ({hata})."}
            return

        arac_cagrilari = list(getattr(mesaj, "tool_calls", None) or [])
        if not arac_cagrilari:
            yield {"tip": "final", "metin": (mesaj.content or "").strip() or "(boş yanıt)", "tur": tur}
            return

        mesajlar.append({
            "role": "assistant",
            "content": mesaj.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in arac_cagrilari
            ],
        })

        for cagri in arac_cagrilari:
            argumanlar = _arguman_coz(cagri)
            yield {"tip": "arac_basladi", "id": cagri.id, "arac": cagri.function.name, "argumanlar": argumanlar}

            baslangic = time.time()
            sonuc = araci_calistir(cagri.function.name, argumanlar)
            sure = time.time() - baslangic

            yield {
                "tip": "arac_bitti", "id": cagri.id, "arac": cagri.function.name,
                "argumanlar": argumanlar, "sonuc": sonuc, "sure": sure,
                "basarili": not (isinstance(sonuc, dict) and "hata" in sonuc),
            }
            mesajlar.append({
                "role": "tool", "tool_call_id": cagri.id, "name": cagri.function.name,
                "content": json.dumps(sonuc, ensure_ascii=False),
            })

    yield {"tip": "hata", "mesaj": f"{MAKS_TUR} tur sonunda nihai cevaba ulaşılamadı."}


# --------------------------------------------------------------------------------------
# Arayüz — 3 panel, aynı soruya paralel canlı akış
# --------------------------------------------------------------------------------------

PANEL_AYARLARI = [
    {"anahtar": "A", "baslik": "Güçlü model", "mod": "araçlar açık", "model": MODEL_GUCLU, "araclar": True},
    {"anahtar": "B", "baslik": "Güçlü model", "mod": "araçlar kapalı", "model": MODEL_GUCLU, "araclar": False},
    {"anahtar": "C", "baslik": "Küçük model", "mod": "araçlar açık", "model": MODEL_ZAYIF, "araclar": True},
]

# --------------------------------------------------------------------------------------
# Tasarım tokenleri — sade, tek aileden 3 renk:
#   1) vurgu   — marka/etkileşim rengi (bağlantı, aktif pil, gönder düğmesi, tooltip)
#   2) basarili — araç çağrısı başarılı
#   3) tehlike  — araç/model hatası (yeniden deneme uyarıları da bu tona düşer)
#   Geri kalan her şey Gradio'nun kendi nötr tema değişkenlerinden gelir; böylece
#   açık/koyu tema otomatik uyum sağlar. Vurgu rengi teknik/ölçüm hissi için sıcak
#   bir bakır tonu — jenerik indigo/mor değil.
# --------------------------------------------------------------------------------------

CSS = """
:root, .gradio-container {
  --vurgu: #a35a1d; --vurgu-zayif: rgba(163,90,29,.10);
  --basarili: #187a3c; --tehlike: #c22626;
  --basarili-zemin: rgba(24,122,60,.10); --tehlike-zemin: rgba(194,38,38,.10);
  --font-metin: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-veri: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Menlo, Consolas, monospace;
}
.dark, .dark .gradio-container {
  --vurgu: #d99a52; --vurgu-zayif: rgba(217,154,82,.16);
  --basarili: #4ade80; --tehlike: #f87171;
  --basarili-zemin: rgba(74,222,128,.12); --tehlike-zemin: rgba(248,113,113,.12);
}

.gecit-baslik { display:flex; align-items:baseline; gap:10px; margin: 0; }
.gecit-baslik h1 { font-family: var(--font-metin); font-size: 1.22em; font-weight: 700; margin: 0; text-wrap: balance; }
.gecit-tez { font-family: var(--font-metin); font-size: 0.84em; opacity: .68; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; line-height: 1.4; margin: 3px 0 12px; }

.eyebrow { font-family: var(--font-metin); font-size: 0.68em; font-weight: 600; letter-spacing: .07em;
           text-transform: uppercase; opacity: .5; margin: 0 0 6px; }
.arac-kayit { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px; }
.arac-etiket { position: relative; display: flex; align-items: center; gap: 7px;
               border: 1px solid var(--border-color-primary); border-radius: 7px; padding: 6px 10px;
               font-family: var(--font-metin); cursor: default; overflow: hidden; }
.arac-etiket .rozet { font-family: var(--font-veri); font-size: 0.68em; font-weight: 700; color: var(--vurgu);
                       background: var(--vurgu-zayif); border-radius: 4px; padding: 2px 6px; letter-spacing: .02em;
                       flex-shrink: 0; }
.arac-etiket .ad { font-weight: 600; font-size: 0.82em; flex-shrink: 0; }
.arac-etiket .aciklama { font-size: 0.78em; opacity: .55; line-height: 1.3;
                          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.arac-etiket .ipucu {
  position: absolute; left: 12px; bottom: calc(100% + 8px);
  width: max-content; max-width: 240px; background: var(--body-text-color); color: var(--background-fill-primary);
  padding: 7px 10px; border-radius: 7px; font-size: 0.82em; line-height: 1.4; text-align: left;
  opacity: 0; pointer-events: none; transition: opacity .12s ease, transform .12s ease; z-index: 30;
  transform: translateY(4px); box-shadow: 0 6px 18px rgba(0,0,0,.18);
}
.arac-etiket .ipucu b { display: block; margin-bottom: 2px; }
.arac-etiket:hover .ipucu { opacity: .96; transform: translateY(0); }
@media (max-width: 900px) { .arac-kayit { grid-template-columns: repeat(2, 1fr); } }

.panel-kutu { border: 1px solid var(--border-color-primary); border-radius: 10px;
              padding: 12px 14px;
              /* HF Space'in üst menüsü iframe'in kullanabildiği yüksekliği azaltır.
                 Paneli doğrudan vh'nin yarısı yapmak composer'ı ekranın altına
                 itiyordu. Başlık, araçlar, örnekler ve composer için 540px ayır;
                 büyük ekranlarda da panelin gereksiz yere uzamasını engelle. */
              height: clamp(250px, calc(100vh - 540px), 460px);
              height: clamp(250px, calc(100dvh - 540px), 460px);
              min-height: 0;
              display: flex; flex-direction: column; font-family: var(--font-metin); overflow: hidden; }
.panel-ust { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;
             padding-bottom: 8px; margin-bottom: 2px; border-bottom: 1px solid var(--border-color-primary);
             flex-shrink: 0; }
.panel-ad { font-weight: 700; font-size: 0.92em; }
.panel-model { font-family: var(--font-veri); font-size: 0.7em; opacity: .6; margin-top: 1px; }
.pil { font-size: 0.64em; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
       border-radius: 999px; padding: 2px 8px; white-space: nowrap; }
.pil.acik { background: var(--vurgu-zayif); color: var(--vurgu); }
.pil.kapali { background: var(--background-fill-secondary); opacity: .6; }

.panel-govde { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding-top: 6px; scroll-behavior: smooth; }
.panel-bos { opacity: .4; font-size: 0.8em; padding-top: 4px; }
.panel-alt-bilgi { font-size: 0.68em; opacity: .5; margin-top: 4px; padding-top: 4px; flex-shrink: 0;
                    border-top: 1px solid var(--border-color-primary); font-variant-numeric: tabular-nums; }

.tur-etiketi { font-size: 0.72em; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
               opacity: .45; margin: 14px 0 6px; }
.tur-etiketi:first-child { margin-top: 0; }

.arac-kart { border: 1px solid var(--border-color-primary); border-radius: 8px; padding: 10px 11px; margin-bottom: 8px; }
.arac-kart.tamam { border-color: color-mix(in srgb, var(--basarili) 35%, var(--border-color-primary)); }
.arac-kart.hata { border-color: color-mix(in srgb, var(--tehlike) 35%, var(--border-color-primary)); }
.arac-kart-ust { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.arac-kart-ad { display: flex; align-items: center; gap: 7px; font-size: 0.86em; }
.arac-kart-ad .rozet { font-family: var(--font-veri); font-size: 0.7em; font-weight: 700; color: var(--vurgu);
                        background: var(--vurgu-zayif); border-radius: 4px; padding: 1px 5px; }
.arac-kart-ad .saglayici { opacity: .55; font-size: 0.85em; }
.durum-pil { font-size: 0.66em; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
             border-radius: 5px; padding: 2px 7px; font-variant-numeric: tabular-nums; }
.durum-pil.calisiyor { background: var(--background-fill-secondary); opacity: .7; }
.durum-pil.tamam { background: var(--basarili-zemin); color: var(--basarili); }
.durum-pil.hata { background: var(--tehlike-zemin); color: var(--tehlike); }
.veri-blok { margin-top: 8px; }
.veri-etiket { font-size: 0.66em; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
               opacity: .45; margin-bottom: 3px; }
.veri-satirlar { font-family: var(--font-veri); font-size: 0.78em; background: var(--background-fill-secondary);
                  border-radius: 6px; padding: 7px 9px; line-height: 1.55; word-break: break-word;
                  font-variant-numeric: tabular-nums; }
.veri-satirlar .anahtar { opacity: .55; }
.veri-satirlar .hata-satir { color: var(--tehlike); }
.kaynak-notu { font-size: 0.72em; opacity: .5; margin-top: 4px; font-family: var(--font-metin); }

.deneme-satir { font-size: 0.78em; background: var(--background-fill-secondary);
                border-radius: 6px; padding: 5px 9px; margin-bottom: 8px; font-family: var(--font-metin); }
.deneme-satir b { color: var(--tehlike); }
.deneme-satir .veri-satirlar { margin-top: 4px; background: transparent; padding: 0; opacity: .75; }

.sonuc-blok { padding-top: 10px; }
.sonuc-kutu { border-radius: 8px; padding: 11px 12px; font-size: 0.9em; line-height: 1.55;
              white-space: pre-wrap; background: var(--vurgu-zayif); border: 1px solid var(--vurgu-zayif); }
.hata-kutu { border-radius: 8px; padding: 11px 12px; font-size: 0.86em; line-height: 1.5;
             background: var(--tehlike-zemin); color: var(--tehlike); }

.ornek-baslik { font-family: var(--font-metin); font-size: 0.68em; font-weight: 600; letter-spacing: .07em;
                text-transform: uppercase; opacity: .5; margin: 2px 0 6px; }
#ornek-sorular { display: grid !important; grid-template-columns: repeat(6, 1fr); gap: 6px; flex-wrap: unset; }
#ornek-sorular > * { min-width: 0; }
#ornek-sorular button {
  font-size: 0.74em !important; white-space: normal !important; text-align: left !important;
  justify-content: flex-start !important; line-height: 1.25 !important; min-height: 40px;
  padding: 7px 9px !important; height: auto !important;
}
@media (max-width: 1100px) { #ornek-sorular { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px) { #ornek-sorular { grid-template-columns: repeat(2, 1fr); } }

/* Paneller sabit yükseklikte iç kaydırmalı olduğu için toplam sayfa yüksekliği
   sorulara göre değişmiyor; composer bu nedenle normal akışta, sayfanın en altında
   sade bir çubuk olarak durabiliyor (fixed/sticky konumlandırma Gradio'nun kendi
   transform'lu sarmalayıcısıyla çakışıp bozuk konumlanmaya yol açıyordu). */
#composer-disi { border-top: 1px solid var(--border-color-primary); margin-top: 10px; padding-top: 8px; }
#composer { gap: 8px; }

/* Gradio'nun bloklar arası varsayılan dikey boşluğunu sıkılaştırır. */
.gradio-container .block { margin-bottom: 0 !important; }
.gradio-container > .main, .gradio-container .contain { gap: 6px !important; padding-top: 8px !important; }

/* Hugging Face Spaces uygulamayı scrolling="no" olan, kendi yüksekliğini üst
   sayfanın flex düzeninden alan (viewport'a göre sabit) bir iframe içine
   gömüyor. Taşan içerik iframe seviyesinde KIRPILIYOR, kaydırılamıyor. Çözüm:
   sayfamızı bu sabit yüksekliğe (100vh) tam oturtup composer'ı sabit tutmak,
   geri kalan içeriği (başlık+araçlar+paneller+örnekler) kendi iç scroll'una
   sahip bir bölgeye almak — composer'ın görünürlüğü artık iframe'in tam
   piksel yüksekliğine bağlı olmuyor. */
html, body { height: 100%; margin: 0; overflow: hidden; }
body { display: flex !important; flex-direction: column !important; }
gradio-app { flex: 1 1 auto !important; min-height: 0 !important;
             display: flex !important; flex-direction: column !important; overflow: hidden !important; }
.gradio-container { flex: 1 1 auto !important; min-height: 0 !important; width: 100% !important;
                     max-width: 1400px; margin: 0 auto !important;
                     display: flex !important; flex-direction: column !important; overflow: hidden !important; }
.gradio-container > .main { flex: 1 1 auto !important; min-height: 0 !important;
                             display: flex !important; flex-direction: column !important; overflow: hidden !important; }
.main .contain { flex: 1 1 auto !important; min-height: 0 !important;
                 display: flex !important; flex-direction: column !important; overflow: hidden !important; }
#icerik-govdesi { flex: 1 1 auto !important; min-height: 0 !important; overflow-y: auto !important; }
#composer-disi { flex-shrink: 0 !important; }
"""

AUTO_KAYDIR_JS = """
<script>
(function () {
  // Panel içeriği her güncellemede yeniden çizildiği için DOM elemanı sıfırdan
  // oluşuyor ve kaydırma konumu kayboluyor. Kullanıcı yukarı kaydırıp geçmişi
  // okumak isterse "takip modu" kapanır ve otomatik kaydırma o panele dokunmaz;
  // kullanıcı tekrar en alta inerse takip modu kendiliğinden açılır.
  var takipEt = {};

  function altaYakinMi(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  }

  function elemanBul(hedef) {
    return hedef && hedef.closest ? hedef.closest(".panel-govde") : null;
  }

  ["wheel", "touchmove"].forEach(function (tur) {
    document.addEventListener(tur, function (e) {
      var el = elemanBul(e.target);
      if (!el) return;
      takipEt[el.id] = altaYakinMi(el);
    }, { passive: true });
  });

  setInterval(function () {
    document.querySelectorAll(".panel-govde").forEach(function (el) {
      if (takipEt[el.id] === false) return;
      el.scrollTop = el.scrollHeight;
    });
  }, 350);
})();
</script>
"""


def _kacir(metin):
    return str(metin).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _deger_yaz(v):
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            return f"[{len(v)} kayıt]"
        return ", ".join(str(x) for x in v) if v else "—"
    return str(v)


def _veri_satirlari(d, haric=()):
    satirlar = []
    for k, v in d.items():
        if k in haric or v is None:
            continue
        satirlar.append(f'<span class="anahtar">{_kacir(k)}:</span> {_kacir(_deger_yaz(v))}')
    return "<br>".join(satirlar) if satirlar else "—"


def _arac_kart_render(blok):
    ust = ARAC_UST_VERI.get(blok["arac"], {"etiket": "?", "saglayici": "—"})
    durum = blok["durum"]
    durum_metni = {"calisiyor": "çalışıyor", "tamam": "tamamlandı", "hata": "hata"}[durum]
    sure_metni = f'{blok["sure"]:.2f}s' if blok.get("sure") is not None else ""

    parcalar = [
        f'<div class="arac-kart {durum}">'
        f'<div class="arac-kart-ust"><span class="arac-kart-ad">'
        f'<span class="rozet">{ust["etiket"]}</span><b>{_kacir(blok["arac"])}</b>'
        f'<span class="saglayici">{_kacir(ust["saglayici"])}</span></span>'
        f'<span class="durum-pil {durum}">{durum_metni}{" · " + sure_metni if sure_metni else ""}</span>'
        f'</div>'
        f'<div class="veri-blok"><div class="veri-etiket">girdi</div>'
        f'<div class="veri-satirlar">{_veri_satirlari(blok["argumanlar"]) if blok["argumanlar"] else "—"}</div></div>'
    ]

    if durum == "tamam":
        sonuc = blok["sonuc"] or {}
        if isinstance(sonuc, dict) and "hata" in sonuc:
            parcalar.append(
                f'<div class="veri-blok"><div class="veri-etiket">çıktı</div>'
                f'<div class="veri-satirlar hata-satir">{_kacir(sonuc["hata"])}</div></div>'
            )
        else:
            kaynak = sonuc.get("kaynak") if isinstance(sonuc, dict) else None
            parcalar.append(
                f'<div class="veri-blok"><div class="veri-etiket">çıktı</div>'
                f'<div class="veri-satirlar">{_veri_satirlari(sonuc, haric=("kaynak",))}</div>'
                + (f'<div class="kaynak-notu">kaynak: {_kacir(kaynak)}</div>' if kaynak else "")
                + '</div>'
            )
    elif durum == "hata":
        parcalar.append(
            f'<div class="veri-blok"><div class="veri-etiket">çıktı</div>'
            f'<div class="veri-satirlar hata-satir">{_kacir((blok.get("sonuc") or {}).get("hata", "bilinmeyen hata"))}</div></div>'
        )

    parcalar.append("</div>")
    return "".join(parcalar)


def _durum_baslangic():
    return {"bloklar": [], "id_indeks": {}, "final": None, "hata": None, "sure": None}


def _durum_guncelle(durum, olay):
    tip = olay["tip"]
    if tip == "tur":
        durum["bloklar"].append({"tip": "tur", "tur": olay["tur"]})
    elif tip == "arac_basladi":
        durum["id_indeks"][olay["id"]] = len(durum["bloklar"])
        durum["bloklar"].append({
            "tip": "arac", "arac": olay["arac"], "argumanlar": olay["argumanlar"],
            "durum": "calisiyor", "sonuc": None, "sure": None,
        })
    elif tip == "arac_bitti":
        i = durum["id_indeks"].get(olay["id"])
        if i is not None:
            blok = durum["bloklar"][i]
            blok.update(durum="tamam" if olay["basarili"] else "hata", sonuc=olay["sonuc"], sure=olay["sure"])
    elif tip == "deneme_hata":
        durum["bloklar"].append({"tip": "deneme_hata", "deneme": olay["deneme"], "detay": olay["detay"]})
    elif tip == "final":
        durum["final"] = olay["metin"]
    elif tip == "hata":
        durum["hata"] = olay["mesaj"]


def _panel_render(ayar, durum):
    pil_sinif = "acik" if ayar["araclar"] else "kapali"
    parcalar = [
        '<div class="panel-kutu"><div class="panel-ust">'
        f'<div><div class="panel-ad">{_kacir(ayar["baslik"])}</div>'
        f'<div class="panel-model">{_kacir(ayar["model"])}</div></div>'
        f'<span class="pil {pil_sinif}">{_kacir(ayar["mod"])}</span>'
        '</div>'
        f'<div class="panel-govde" id="panel-govde-{ayar["anahtar"]}">'
    ]

    if not durum["bloklar"] and not durum["final"] and not durum["hata"]:
        parcalar.append('<div class="panel-bos">Bir soru sorduğunuzda burada akacak.</div>')

    for blok in durum["bloklar"]:
        if blok["tip"] == "tur":
            parcalar.append(f'<div class="tur-etiketi">Tur {blok["tur"]}</div>')
        elif blok["tip"] == "arac":
            parcalar.append(_arac_kart_render(blok))
        elif blok["tip"] == "deneme_hata":
            parcalar.append(
                f'<div class="deneme-satir"><b>Deneme {blok["deneme"]}</b> geçersiz yanıt üretti'
                f'<div class="veri-satirlar">{_kacir(blok["detay"])}</div></div>'
            )

    if durum["final"] or durum["hata"]:
        parcalar.append('<div class="sonuc-blok">')
        if durum["final"]:
            parcalar.append(f'<div class="sonuc-kutu">{_kacir(durum["final"])}</div>')
        if durum["hata"]:
            parcalar.append(f'<div class="hata-kutu">{_kacir(durum["hata"])}</div>')
        parcalar.append("</div>")

    parcalar.append("</div>")  # .panel-govde kapanışı

    if durum["sure"] is not None:
        arac_sayisi = sum(1 for b in durum["bloklar"] if b["tip"] == "arac")
        parcalar.append(f'<div class="panel-alt-bilgi">{durum["sure"]:.1f}s · {arac_sayisi} araç çağrısı</div>')

    parcalar.append("</div>")  # .panel-kutu kapanışı
    return "".join(parcalar)


def _panel_calistir(anahtar, soru, model, araclar_acik, kuyruk):
    baslangic = time.time()
    try:
        for olay in ajan_calistir(soru, model, araclar_acik):
            kuyruk.put((anahtar, olay, time.time() - baslangic))
    except Exception as e:
        kuyruk.put((anahtar, {"tip": "hata", "mesaj": f"Beklenmeyen hata: {e}"}, time.time() - baslangic))
    kuyruk.put((anahtar, {"tip": "bitti"}, time.time() - baslangic))


def uc_paneli_calistir(soru):
    """Panelleri render eder; son çıktı olarak soru kutusunu da yönetir.

    İlk yield'de kutu boşaltılır (kullanıcı gönderir göndermez temizlenir); sonraki
    yield'lerde kutuya dokunulmaz, böylece kullanıcı akış sürerken sıradaki soruyu
    yazmaya başlarsa üzerine yazılmaz.
    """
    soru = (soru or "").strip()
    if not soru:
        bos = [_panel_render(a, _durum_baslangic()) for a in PANEL_AYARLARI]
        yield (*bos, gr.update())
        return

    kuyruk = queue.Queue()
    durumlar = {a["anahtar"]: _durum_baslangic() for a in PANEL_AYARLARI}

    threadler = [
        threading.Thread(target=_panel_calistir, args=(a["anahtar"], soru, a["model"], a["araclar"], kuyruk), daemon=True)
        for a in PANEL_AYARLARI
    ]
    for th in threadler:
        th.start()

    bitenler = set()
    ilk_yield = True
    while len(bitenler) < len(PANEL_AYARLARI):
        anahtar, olay, gecen_sure = kuyruk.get()
        durum = durumlar[anahtar]

        if olay["tip"] == "bitti":
            bitenler.add(anahtar)
            durum["sure"] = gecen_sure
        else:
            _durum_guncelle(durum, olay)

        panel_htmlleri = tuple(_panel_render(a, durumlar[a["anahtar"]]) for a in PANEL_AYARLARI)
        yield (*panel_htmlleri, ("" if ilk_yield else gr.update()))
        ilk_yield = False


ORNEK_SORULAR = [
    "Ankara mı daha sıcak Londra mı, bu değerler Fahrenheit olarak kaç eder?",
    "İstanbul'da hava kaç derece, Kelvin olarak da söyler misin?",
    "250 Euro kaç TL eder?",
    "Bitcoin şu an kaç dolar, 24 saatte ne kadar değişti?",
    "Mimar Sinan kimdir kısaca anlatır mısın?",
    "Son 3 günde 5'ten büyük deprem oldu mu?",
]

with gr.Blocks(title="Tool Calling Karşılaştırması") as demo:
    with gr.Column(elem_id="icerik-govdesi"):
        gr.HTML(
            '<div class="gecit-baslik"><h1>Tool Calling Karşılaştırması</h1></div>'
            '<p class="gecit-tez">Aynı soru üçüne birden gider: güçlü model + araçlar, aynı model araçsız, '
            'küçük model + araçlar — fark, tool calling ve model kapasitesinin gerçek katkısını gösterir.</p>'
            '<div class="eyebrow">Kullanılabilir araçlar</div>'
            '<div class="arac-kayit">' + "".join(
                f'<div class="arac-etiket"><span class="rozet">{u["etiket"]}</span>'
                f'<span class="ad">{ad}</span>'
                f'<span class="aciklama">{u["aciklama"]}</span>'
                f'<span class="ipucu"><b>{u["saglayici"]}</b>{u["aciklama"]}</span></div>'
                for ad, u in ARAC_UST_VERI.items()
            ) + '</div>'
        )

        with gr.Row():
            paneller = [gr.HTML(_panel_render(a, _durum_baslangic())) for a in PANEL_AYARLARI]

        gr.HTML('<div class="ornek-baslik">Örnek sorular</div>')
        with gr.Row(elem_id="ornek-sorular"):
            ornek_butonlar = [gr.Button(s, size="sm") for s in ORNEK_SORULAR]

    with gr.Group(elem_id="composer-disi"):
        with gr.Row(elem_id="composer"):
            soru_kutusu = gr.Textbox(
                placeholder="Bir soru sorun — örn. Ankara mı daha sıcak Londra mı...",
                scale=6, show_label=False, container=False,
            )
            gonder = gr.Button("Gönder", variant="primary", scale=1)

    for buton, s in zip(ornek_butonlar, ORNEK_SORULAR):
        buton.click(lambda s=s: s, outputs=soru_kutusu)

    cikislar = paneller + [soru_kutusu]
    gonder.click(uc_paneli_calistir, inputs=soru_kutusu, outputs=cikislar)
    soru_kutusu.submit(uc_paneli_calistir, inputs=soru_kutusu, outputs=cikislar)


if __name__ == "__main__":
    demo.queue().launch(css=CSS, head=AUTO_KAYDIR_JS)
