"""Modelin cagirabilecegi 6 arac.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele geri
beslenir. Hicbiri hata firlatmaz — hata olursa Turkce bir aciklama doner, boylece
sohbet dongusu cokmez.

Tasarim karari — neden "tur_planla" tek seferde her seyi yapiyor?
    8B'lik yerel bir model, ust uste 4 arac cagirip aralarindaki sayilari dogru
    tasimakta zorlanir (rotadan cikan 1162 m tirmanisi efor aracina gecirmeyi
    unutur). Bu yuzden ana senaryo tek bir aracta zincirlendi: model sadece
    kullanicinin soyledigi seyi (nereden, nereye, hangi bisiklet) aktarir,
    sayisal zincirleme Python tarafinda kalir. Diger araclar ise kullanici
    kendi mesafesini verdiginde ya da tek bir bilgi istediginde kullanilir.
"""

import html
import json
import os
import re
import sqlite3
from datetime import date, timedelta

import requests

import rota

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turlar.db")

PUSULA = ["kuzey", "kuzeydogu", "dogu", "guneydogu", "guney", "guneybati", "bati", "kuzeybati"]


def _pusula(derece: float) -> str:
    return PUSULA[round(derece / 45) % 8]


def _tarih(gun_sonra: int) -> str:
    return (date.today() + timedelta(days=max(0, gun_sonra))).isoformat()


# ------------------------------------------------------- 1) ana senaryo araci

def tur_planla(
    baslangic: str,
    bitis: str,
    bisiklet_tipi: str = "trekking",
    kondisyon: str = "orta",
    surucu_kg: float = 75.0,
    gun_sonra: int = 0,
    kamp: bool = False,
) -> str:
    """Iki nokta arasindaki bisiklet turunu ucdan uca planlar.

    Zincir: yer bulma -> BRouter rotasi -> hava/ruzgar -> ruzgar bileseni ->
    fizik tabanli efor -> ekipman listesi. Hepsi tek arac cagrisinda.
    """
    try:
        r = rota.rota_getir(baslangic, bitis, bisiklet_tipi)
        h = rota.hava_getir(r["baslangic"]["lat"], r["baslangic"]["lon"], gun_sonra)
    except rota.RotaHatasi as exc:
        return f"Plan yapilamadi: {exc}"

    karsi = rota.ruzgar_bileseni(h["ruzgar_kmh"], h["ruzgar_yon_derece"], r["yon_derece"])
    ortalama_rakim = ((r["min_rakim_m"] or 0) + (r["max_rakim_m"] or 0)) / 2

    # Bikepacking yuku (cadir, tulum, ocak, su, yiyecek) tipik olarak ~12 kg.
    # Bu agirlik hem tirmanis enerjisini hem yuvarlanma direncini artirir, o yuzden
    # ekipman listesine not dusmek yetmez, fizik hesabina da girmesi gerekir.
    yuk_kg = 12.0 if kamp else 0.0

    e = rota.efor_hesapla(
        mesafe_km=r["mesafe_km"],
        tirmanis_m=r["tirmanis_m"],
        surucu_kg=surucu_kg + yuk_kg,
        bisiklet=bisiklet_tipi,
        kondisyon=kondisyon,
        karsi_ruzgar_kmh=karsi,
        sicaklik_c=(h["sicaklik_max"] + h["sicaklik_min"]) / 2,
        ortalama_rakim_m=ortalama_rakim,
    )
    ekipman = rota.ekipman_listesi(
        sicaklik_c=h["sicaklik_max"],
        yagis_ihtimali=h["yagis_ihtimali"],
        mesafe_km=r["mesafe_km"],
        sure_saat=e["sure_saat"],
        kamp=kamp,
    )

    ruzgar_metin = (
        f"{abs(karsi)} km/s ARKADAN (yardimci)" if karsi < -1
        else f"{karsi} km/s KARSIDAN (zorlayici)" if karsi > 1
        else "yandan/etkisiz"
    )

    return (
        f"ROTA: {r['baslangic']['ad']} -> {r['bitis']['ad']} ({r['profil']} profili)\n"
        f"- mesafe: {r['mesafe_km']} km, toplam tirmanis: {r['tirmanis_m']} m "
        f"(rakim {r['min_rakim_m']}-{r['max_rakim_m']} m)\n"
        f"- gidis yonu: {_pusula(r['yon_derece'])}\n"
        f"\nHAVA ({h['tarih']}): {h['durum']}, {h['sicaklik_min']}-{h['sicaklik_max']} C, "
        f"yagis ihtimali %{h['yagis_ihtimali']}\n"
        f"- ruzgar: {h['ruzgar_kmh']} km/s {_pusula(h['ruzgar_yon_derece'])}den -> rotada {ruzgar_metin}\n"
        f"- gun dogumu {h['gun_dogumu']}, gun batimi {h['gun_batimi']}\n"
        f"\nEFOR ({kondisyon} kondisyon, {surucu_kg} kg surucu"
        + (f" + {yuk_kg:.0f} kg kamp yuku" if yuk_kg else "")
        + f", {e['pedal_gucu_w']} W tempo):\n"
        f"- tahmini sure: {e['sure_metin']} (mola haric), ortalama {e['ortalama_hiz_kmh']} km/s\n"
        f"- zorluk: {e['zorluk'].upper()} | eforun %{e['tirmanis_payi_yuzde']}'i tirmanisa gidiyor\n"
        f"- yakit: {e['kalori_kcal']} kcal, {e['su_litre']} L su, {e['karbonhidrat_g']} g karbonhidrat\n"
        f"\nEKIPMAN:\n"
        f"- zorunlu: {', '.join(ekipman['zorunlu'])}\n"
        f"- giyim: {', '.join(ekipman['giyim'])}\n"
        f"- beslenme: {', '.join(ekipman['beslenme'])}\n"
        + ("- UYARI: " + " ".join(ekipman["uyarilar"]) if ekipman["uyarilar"] else "")
    )


# ------------------------------------------------------ 2) tekil efor hesabi

def efor_hesapla(
    mesafe_km: float,
    tirmanis_m: float = 0,
    surucu_kg: float = 75.0,
    bisiklet_tipi: str = "trekking",
    kondisyon: str = "orta",
    karsi_ruzgar_kmh: float = 0.0,
    sicaklik_c: float = 20.0,
) -> str:
    """Kullanici mesafeyi kendi verdiginde sure/kalori/su hesabi yapar."""
    try:
        e = rota.efor_hesapla(
            mesafe_km=float(mesafe_km),
            tirmanis_m=float(tirmanis_m or 0),
            surucu_kg=float(surucu_kg),
            bisiklet=bisiklet_tipi,
            kondisyon=kondisyon,
            karsi_ruzgar_kmh=float(karsi_ruzgar_kmh or 0),
            sicaklik_c=float(sicaklik_c),
        )
    except (ValueError, TypeError) as exc:
        return f"Hesap yapilamadi: {exc}"

    # Ciktiya "ne YOK" bilgisini de koyuyoruz: model bu araci cagirdiginda
    # ciktida olmayan hava ve ekipman bilgisini uydurmaya egilimliydi.
    return (
        "[KURAL: Bu cikti hava, ruzgar ve ekipman bilgisi ICERMEZ; cevabinda "
        "hava durumu ya da ekipman yazma.]\n"
        f"{mesafe_km} km / {tirmanis_m} m tirmanis, {bisiklet_tipi} bisiklet, "
        f"{kondisyon} kondisyon ({e['pedal_gucu_w']} W):\n"
        f"- sure: {e['sure_metin']} (mola haric), ortalama {e['ortalama_hiz_kmh']} km/s\n"
        f"- zorluk: {e['zorluk']} | tirmanisin efordaki payi %{e['tirmanis_payi_yuzde']}\n"
        f"- {e['kalori_kcal']} kcal, {e['su_litre']} L su, {e['karbonhidrat_g']} g karbonhidrat"
    )


# ----------------------------------------------------------- 3) hava durumu

def hava_durumu(yer: str, gun_sonra: int = 0) -> str:
    """Bir yerin belirli gundeki bisiklet acisindan onemli hava ozetini verir."""
    try:
        y = rota.yer_bul(yer)
        h = rota.hava_getir(y["lat"], y["lon"], int(gun_sonra))
    except (rota.RotaHatasi, ValueError) as exc:
        return f"Hava durumu alinamadi: {exc}"

    return (
        f"{y['ad']} {h['tarih']}: {h['durum']}, {h['sicaklik_min']}-{h['sicaklik_max']} C, "
        f"yagis ihtimali %{h['yagis_ihtimali']}, ruzgar {h['ruzgar_kmh']} km/s "
        f"{_pusula(h['ruzgar_yon_derece'])}den (gunduz ortalamasi). "
        f"Gun dogumu {h['gun_dogumu']}, gun batimi {h['gun_batimi']}."
    )


# ------------------------------------------------------------- 4) ekipman

def ekipman_listesi(
    sicaklik_c: float,
    yagis_ihtimali: int = 0,
    mesafe_km: float = 40,
    sure_saat: float = 2,
    gece_surusu: bool = False,
    kamp: bool = False,
) -> str:
    """Verilen kosullar icin kural tabanli ekipman listesi."""
    try:
        k = rota.ekipman_listesi(
            sicaklik_c=float(sicaklik_c),
            yagis_ihtimali=int(yagis_ihtimali or 0),
            mesafe_km=float(mesafe_km),
            sure_saat=float(sure_saat),
            gece_surusu=bool(gece_surusu),
            kamp=bool(kamp),
        )
    except (ValueError, TypeError) as exc:
        return f"Liste olusturulamadi: {exc}"

    metin = (
        f"{sicaklik_c} C / yagis %{yagis_ihtimali} / {mesafe_km} km icin ekipman:\n"
        f"- zorunlu: {', '.join(k['zorunlu'])}\n"
        f"- giyim: {', '.join(k['giyim'])}\n"
        f"- beslenme: {', '.join(k['beslenme'])}"
    )
    if k["uyarilar"]:
        metin += "\n- uyarilar: " + " ".join(k["uyarilar"])
    return metin


# --------------------------------------------------------- 5) tur defteri

def _baglanti() -> sqlite3.Connection:
    baglanti = sqlite3.connect(DB_YOLU)
    baglanti.execute(
        """CREATE TABLE IF NOT EXISTS turlar (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ad TEXT NOT NULL,
               baslangic TEXT,
               bitis TEXT,
               tarih TEXT,
               mesafe_km REAL,
               tirmanis_m INTEGER,
               notlar TEXT
           )"""
    )
    return baglanti


def tur_kaydet(
    ad: str,
    baslangic: str = "",
    bitis: str = "",
    gun_sonra: int = 0,
    mesafe_km: float = 0,
    tirmanis_m: int = 0,
    notlar: str = "",
) -> str:
    """Planlanan turu yerel tur defterine (SQLite) yazar."""
    try:
        with _baglanti() as baglanti:
            imlec = baglanti.execute(
                "INSERT INTO turlar (ad, baslangic, bitis, tarih, mesafe_km, tirmanis_m, notlar)"
                " VALUES (?,?,?,?,?,?,?)",
                (ad, baslangic, bitis, _tarih(int(gun_sonra)), float(mesafe_km or 0),
                 int(tirmanis_m or 0), notlar),
            )
        return (
            f"Tur defterine kaydedildi (#{imlec.lastrowid}): '{ad}', {_tarih(int(gun_sonra))}, "
            f"{baslangic} -> {bitis}, {mesafe_km} km."
        )
    except (sqlite3.Error, ValueError) as exc:
        return f"Kayit yapilamadi: {exc}"


def turlarim(limit: int = 10) -> str:
    """Tur defterindeki kayitlari ve toplam istatistigi dondurur."""
    try:
        with _baglanti() as baglanti:
            satirlar = baglanti.execute(
                "SELECT id, ad, tarih, baslangic, bitis, mesafe_km, tirmanis_m, notlar"
                " FROM turlar ORDER BY tarih DESC, id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            toplam = baglanti.execute(
                "SELECT COUNT(*), COALESCE(SUM(mesafe_km),0), COALESCE(SUM(tirmanis_m),0) FROM turlar"
            ).fetchone()
    except (sqlite3.Error, ValueError) as exc:
        return f"Kayitlar okunamadi: {exc}"

    if not satirlar:
        return "Tur defteri bos. Henuz kayitli tur yok."

    liste = "\n".join(
        f"#{i} {tarih} | {ad} | {bas} -> {bit} | {mesafe} km / {tirmanis} m"
        + (f" | not: {notlar}" if notlar else "")
        for i, ad, tarih, bas, bit, mesafe, tirmanis, notlar in satirlar
    )
    return f"{liste}\n\nToplam: {toplam[0]} tur, {round(toplam[1], 1)} km, {toplam[2]} m tirmanis."


# ------------------------------------------------------- 6) internet arama

# Arama ciktisinin basina konan uyari. Ayni kural sistem isteminde de var ama
# olculen davranis su: model, sistem istemindeki kurali unutup sonuclarda gecmeyen
# tesis adlari uyduruyordu (ornegin Izmir'deki bir kampi Antalya listesine koydu).
# Talimati arac ciktisinin icine koymak, kurali modelin son okudugu metne tasiyor.
ARAMA_UYARISI = (
    "[KURAL: Asagidaki basliklarda ve ozetlerde GECMEYEN hicbir tesis adi, sehir, "
    "fiyat veya ozellik yazma. Yorum yapma, sadece bu sonuclari link ile aktar.]\n"
)


def internet_arama(sorgu: str, max_sonuc: int = 5) -> str:
    """Guncel bilgi icin DuckDuckGo aramasi. API anahtari gerektirmez.

    Once ddgs kutuphanesi denenir (ozet metin de doner), kurulu degilse ya da
    hata verirse DuckDuckGo'nun 'lite' HTML arayuzune dusulur.
    """
    try:
        from ddgs import DDGS

        sonuclar = DDGS().text(sorgu, region="tr-tr", max_results=int(max_sonuc))
        satirlar = [
            f"{i}. {s.get('title', '').strip()}\n   {(s.get('body') or '')[:200].strip()}\n   {s.get('href', '')}"
            for i, s in enumerate(sonuclar, start=1)
        ]
        if satirlar:
            return ARAMA_UYARISI + f"'{sorgu}' icin sonuclar:\n" + "\n".join(satirlar)
    except Exception:  # kutuphane yok ya da servis kizdi: yedege dus
        pass

    return _ddg_lite(sorgu, int(max_sonuc))


def _ddg_lite(sorgu: str, max_sonuc: int) -> str:
    """Yedek arama: DuckDuckGo lite sayfasindan baslik + link cikarir."""
    try:
        cevap = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": sorgu},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        ciftler = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            cevap.text,
            flags=re.DOTALL,
        )
        satirlar = []
        for url, ham_baslik in ciftler[:max_sonuc]:
            baslik = html.unescape(re.sub(r"<[^>]+>", "", ham_baslik)).strip()
            if baslik:
                satirlar.append(f"{len(satirlar) + 1}. {baslik}\n   {html.unescape(url)}")
        if satirlar:
            return ARAMA_UYARISI + f"'{sorgu}' icin sonuclar:\n" + "\n".join(satirlar)
        return f"'{sorgu}' icin sonuc bulunamadi."
    except requests.RequestException as exc:
        return f"Arama yapilamadi: {exc}"


TOOLS = {
    "tur_planla": tur_planla,
    "efor_hesapla": efor_hesapla,
    "hava_durumu": hava_durumu,
    "ekipman_listesi": ekipman_listesi,
    "tur_kaydet": tur_kaydet,
    "turlarim": turlarim,
    "internet_arama": internet_arama,
}

# Ortak enum aciklamalari: modelin uydurma deger yazmasini engeller.
_BISIKLET = {
    "type": "string",
    "enum": list(rota.BISIKLET),
    "description": "Bisiklet tipi. Kullanici soylemediyse 'trekking' kullan.",
}
_KONDISYON = {
    "type": "string",
    "enum": list(rota.KONDISYON),
    "description": "Surucunun kondisyonu. Kullanici soylemediyse 'orta' kullan.",
}
_GUN = {
    "type": "integer",
    "description": "Bugunden kac gun sonra. Bugun=0, yarin=1, obur gun=2. En fazla 6.",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "tur_planla",
            "description": (
                "IKI YER ARASINDA bisiklet turu planlar. Gercek rota mesafesini, toplam "
                "tirmanis metresini, o gunun havasini ve ruzgar yonunu alir; sure, kalori, "
                "su ihtiyaci ve ekipman listesini hesaplar. Kullanici 'X'ten Y'ye gitmek "
                "istiyorum' dediginde HER ZAMAN bu araci kullan; ayri ayri hava/efor "
                "araclarini cagirma."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "baslangic": {"type": "string", "description": "Baslangic yeri, ornegin 'Kas, Antalya'"},
                    "bitis": {"type": "string", "description": "Varis yeri, ornegin 'Demre'"},
                    "bisiklet_tipi": _BISIKLET,
                    "kondisyon": _KONDISYON,
                    "surucu_kg": {"type": "number", "description": "Surucu agirligi kg. Bilinmiyorsa 75."},
                    "gun_sonra": _GUN,
                    "kamp": {"type": "boolean", "description": "Kamp/bikepacking yapilacaksa true."},
                },
                "required": ["baslangic", "bitis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "efor_hesapla",
            "description": (
                "Kullanici MESAFEYI KENDI verdiginde sure, ortalama hiz, kalori, su ve "
                "karbonhidrat ihtiyacini hesaplar. Yer adi verildiyse degil, sadece "
                "'60 km surersem' gibi sorularda kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mesafe_km": {"type": "number", "description": "Mesafe (km)"},
                    "tirmanis_m": {"type": "number", "description": "Toplam tirmanis (m). Bilinmiyorsa 0."},
                    "surucu_kg": {"type": "number", "description": "Surucu agirligi kg. Bilinmiyorsa 75."},
                    "bisiklet_tipi": _BISIKLET,
                    "kondisyon": _KONDISYON,
                    "karsi_ruzgar_kmh": {
                        "type": "number",
                        "description": (
                            "Karsi ruzgar km/s (arkadan eserse negatif). Kullanici ruzgardan "
                            "BAHSETMEDIYSE bu alani hic gonderme, deger uydurma."
                        ),
                    },
                    "sicaklik_c": {
                        "type": "number",
                        "description": (
                            "Ortalama sicaklik C. Kullanici sicaklik SOYLEMEDIYSE bu alani hic "
                            "gonderme; uydurulmus sicaklik su ihtiyacini yanlis hesaplatir."
                        ),
                    },
                },
                "required": ["mesafe_km"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hava_durumu",
            "description": (
                "Tek bir yerin hava durumunu, ruzgarini ve gun batimi saatini verir. "
                "Rota planlanacaksa bunu degil tur_planla'yi kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "yer": {"type": "string", "description": "Yer adi, ornegin 'Bursa'"},
                    "gun_sonra": _GUN,
                },
                "required": ["yer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ekipman_listesi",
            "description": (
                "Sicaklik ve yagis ihtimaline gore ne goturulmesi gerektigini listeler. "
                "Kullanici sadece 'ne goturmeliyim' diye sorduysa kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sicaklik_c": {"type": "number", "description": "Beklenen sicaklik (C)"},
                    "yagis_ihtimali": {"type": "integer", "description": "Yagis ihtimali yuzde (0-100)"},
                    "mesafe_km": {"type": "number", "description": "Planlanan mesafe (km)"},
                    "sure_saat": {"type": "number", "description": "Tahmini sure (saat)"},
                    "gece_surusu": {"type": "boolean", "description": "Karanlikta surus varsa true"},
                    "kamp": {"type": "boolean", "description": "Kamp yapilacaksa true"},
                },
                "required": ["sicaklik_c"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tur_kaydet",
            "description": (
                "Planlanan turu kullanicinin tur defterine kaydeder. SADECE kullanici "
                "acikca 'kaydet' dediginde cagir. Mesafe ve tirmanis degerlerini onceki "
                "tur_planla ciktisindan aynen al, yenisini uydurma."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ad": {"type": "string", "description": "Tura verilen kisa ad"},
                    "baslangic": {"type": "string", "description": "Baslangic yeri"},
                    "bitis": {"type": "string", "description": "Varis yeri"},
                    "gun_sonra": _GUN,
                    "mesafe_km": {"type": "number", "description": "Rota mesafesi (km)"},
                    "tirmanis_m": {"type": "integer", "description": "Toplam tirmanis (m)"},
                    "notlar": {"type": "string", "description": "Kisa not"},
                },
                "required": ["ad"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turlarim",
            "description": "Tur defterindeki kayitli turlari ve toplam km/tirmanis istatistigini listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Kac kayit gosterilecek (varsayilan 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "internet_arama",
            "description": (
                "Bisiklet etkinligi, yol durumu, kamp alani, servis, konaklama gibi "
                "DEGISKEN ve GUNCEL bilgiler icin internette arar. Mesafe, tirmanis, "
                "hava ya da kalori icin KULLANMA — onlarin kendi araclari var."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu (Turkce anahtar kelimeler)"},
                    "max_sonuc": {"type": "integer", "description": "Sonuc sayisi (varsayilan 5)"},
                },
                "required": ["sorgu"],
            },
        },
    },
]


if __name__ == "__main__":  # hizli elle test: python3 tools.py
    print(tur_planla("Kas, Antalya", "Demre", "gravel", "orta", 78, 1))
    print()
    print(internet_arama("Likya yolu bisiklet rotasi", 3))
    print()
    print(json.dumps([t["function"]["name"] for t in TOOL_SCHEMAS], ensure_ascii=False))
