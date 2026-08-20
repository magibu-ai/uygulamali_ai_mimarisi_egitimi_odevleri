"""Modelin cagirabilecegi araclar.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele geri
beslenir. Hicbiri hata firlatmaz — hata olursa Turkce bir aciklama doner, boylece
sohbet dongusu cokmez.

TOOL_SCHEMAS listesi modele "elinde su araclar var" demenin JSON halidir.

    ders_ara        senaryoya ozel  -> ders kitabi RAG'i (topraklanmis cevap)
    internet_ara    genel           -> DuckDuckGo, yedegi Wikipedia
    calisma_plani   senaryoya ozel  -> konuyu gunlere bolen calisma programi
    hesapla         yardimci        -> fizik/kimya islemleri icin guvenli hesap
"""

from __future__ import annotations

import ast
import html
import operator
import re

import requests

import ders_rag

TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


# --- 1) Senaryoya ozel: ders kitabi aramasi ----------------------------------


def ders_ara(soru: str, ders: str | None = None) -> str:
    """Ders sorusunu YALNIZCA indekslenmis ders kitaplarina dayanarak cevaplar.

    Cevap burada bitmis haldedir; chat.py'deki model bunu aynen aktarmalidir.
    """
    if ders:
        ders = ders.strip().lower()
        if ders not in {"fizik", "kimya", "tarih"}:
            ders = None

    sonuc = ders_rag.cevapla(soru, ders=ders)
    if not sonuc["topraklandi"]:
        return (
            f"{sonuc['cevap']}\n"
            f"(en yuksek benzerlik {sonuc['en_yuksek_skor']}, esik {ders_rag.ESIK})"
        )

    kaynaklar = "\n".join(
        f"- {k['ders']} kitabi, parca {k['parca_no']} (benzerlik {k['benzerlik']})"
        for k in sonuc["kaynaklar"]
    )
    return f"{sonuc['cevap']}\n\nKaynaklar:\n{kaynaklar}"


# --- 2) Internet aramasi ------------------------------------------------------


def internet_ara(sorgu: str, adet: int = 5) -> str:
    """DuckDuckGo'nun sade arayuzunde arama yapar. API anahtari gerekmez."""
    try:
        yanit = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": sorgu},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        ciftler = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            yanit.text,
            flags=re.DOTALL,
        )
        sonuclar = []
        for url, ham_baslik in ciftler[:adet]:
            baslik = html.unescape(re.sub(r"<[^>]+>", "", ham_baslik)).strip()
            if baslik:
                sonuclar.append(f"{len(sonuclar) + 1}. {baslik}\n   {html.unescape(url)}")
        if sonuclar:
            return f"'{sorgu}' icin internet sonuclari:\n" + "\n".join(sonuclar)
    except requests.RequestException:
        pass  # asagidaki Wikipedia yedegine dus

    return _wikipedia_ara(sorgu, adet)


def _wikipedia_ara(sorgu: str, adet: int) -> str:
    """Yedek arama: Turkce Wikipedia API'si."""
    try:
        veri = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": sorgu,
                "srlimit": adet,
                "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        ogeler = veri.get("query", {}).get("search", [])
        if not ogeler:
            return f"'{sorgu}' icin sonuc bulunamadi."
        satirlar = []
        for i, oge in enumerate(ogeler, start=1):
            ozet = html.unescape(re.sub(r"<[^>]+>", "", oge.get("snippet", "")))
            baglanti = oge["title"].replace(" ", "_")
            satirlar.append(
                f"{i}. {oge['title']}\n   {ozet}\n   https://tr.wikipedia.org/wiki/{baglanti}"
            )
        return f"'{sorgu}' icin Wikipedia sonuclari:\n" + "\n".join(satirlar)
    except requests.RequestException as hata:
        return f"Arama yapilamadi: {hata}"


# --- 3) Senaryoya ozel: calisma plani ----------------------------------------


def calisma_plani(konu: str, gun: int = 5, ders: str | None = None) -> str:
    """Bir konuyu ders kitabindaki parcalara dayanarak gunlere boler.

    Plan uydurulmaz: once ders kitabinda o konuyla ilgili parcalar aranir,
    bulunanlar gun sayisina bolunur. Kitapta karsiligi yoksa plan uretilmez.
    """
    try:
        gun = max(1, min(int(gun), 14))
    except (TypeError, ValueError):
        gun = 5

    if ders:
        ders = ders.strip().lower()
        if ders not in {"fizik", "kimya", "tarih"}:
            ders = None

    bulunanlar = [b for b in ders_rag.ara(konu, k=gun * 2, ders=ders) if b["benzerlik"] >= ders_rag.ESIK]
    if not bulunanlar:
        return (
            f"'{konu}' konusu ders kitaplarinda bulunamadi, bu konu icin plan olusturulamiyor."
        )

    satirlar = [f"'{konu}' icin {gun} gunluk calisma plani (kaynak: ders kitaplari):"]
    for i in range(gun):
        gunun_parcalari = bulunanlar[i::gun]
        if not gunun_parcalari:
            continue
        basliklar = []
        for b in gunun_parcalari[:2]:
            ozet = " ".join(b["metin"].split()[:14])
            basliklar.append(f"{b['ders']}: {ozet}...")
        satirlar.append(f"{i + 1}. gun -> " + " | ".join(basliklar))
    return "\n".join(satirlar)


# --- 4) Guvenli hesap makinesi ------------------------------------------------

_ISLEMLER = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _degerlendir(dugum):
    """Ifade agacini yalnizca izin verilen dugumlerle hesaplar.

    eval() kullanilmiyor: model uretilen metni dogrudan calistirmak, modele
    kod yurutme yetkisi vermek demektir. Burada sadece dort islem ve us alma
    dugumleri kabul edilir, geri kalan her sey reddedilir.
    """
    if isinstance(dugum, ast.Constant) and isinstance(dugum.value, (int, float)):
        return dugum.value
    if isinstance(dugum, ast.BinOp) and type(dugum.op) in _ISLEMLER:
        return _ISLEMLER[type(dugum.op)](_degerlendir(dugum.left), _degerlendir(dugum.right))
    if isinstance(dugum, ast.UnaryOp) and type(dugum.op) in _ISLEMLER:
        return _ISLEMLER[type(dugum.op)](_degerlendir(dugum.operand))
    raise ValueError("izin verilmeyen islem")


def hesapla(ifade: str) -> str:
    """Sayisal bir ifadeyi guvenli sekilde hesaplar. Ornek: '(9.8 * 2) / 4'."""
    try:
        agac = ast.parse(ifade, mode="eval")
        sonuc = _degerlendir(agac.body)
        return f"{ifade} = {sonuc}"
    except ZeroDivisionError:
        return "Sifira bolme hatasi."
    except Exception:
        return f"'{ifade}' hesaplanamadi. Yalnizca sayilar ve + - * / ** % kullanilabilir."


# --- Modele acilan arayuz -----------------------------------------------------

TOOLS = {
    "ders_ara": ders_ara,
    "internet_ara": internet_ara,
    "calisma_plani": calisma_plani,
    "hesapla": hesapla,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "ders_ara",
            "description": (
                "FIZIK, KIMYA veya TARIH ile ilgili TUM sorular icin bu araci kullan. "
                "Cevabi ders kitaplari veritabanindan uretir. Donen metni AYNEN kullaniciya "
                "aktar, uzerine kendi bilgini EKLEME. Once her zaman bu araci dene."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "soru": {"type": "string", "description": "Ogrencinin sorusu"},
                    "ders": {
                        "type": "string",
                        "description": "Aramayi tek derse sinirlar",
                        "enum": ["fizik", "kimya", "tarih"],
                    },
                },
                "required": ["soru"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "internet_ara",
            "description": (
                "Guncel olaylar, haberler veya ders kitaplarinda BULUNMAYAN genel bilgi icin "
                "internette arama yapar. Fizik/kimya/tarih sorularinda once ders_ara denenmeli; "
                "bu arac yalnizca ders_ara 'Bilmiyorum' dondurdugunde kullanilir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu"},
                    "adet": {"type": "integer", "description": "Sonuc sayisi (varsayilan 5)"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calisma_plani",
            "description": (
                "Bir konuyu ders kitabindaki icerige dayanarak gunlere bolen calisma programi "
                "olusturur. Ogrenci 'plan yap', 'kac gunde calisayim' gibi bir sey istediginde kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "konu": {"type": "string", "description": "Calisilacak konu"},
                    "gun": {"type": "integer", "description": "Kac gunluk plan (1-14, varsayilan 5)"},
                    "ders": {
                        "type": "string",
                        "description": "Plani tek derse sinirlar",
                        "enum": ["fizik", "kimya", "tarih"],
                    },
                },
                "required": ["konu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hesapla",
            "description": (
                "Sayisal bir ifadeyi hesaplar. Fizik ve kimya problemlerindeki islemler icin kullan. "
                "Ornek ifade: '(9.8 * 2) / 4'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ifade": {"type": "string", "description": "Hesaplanacak matematiksel ifade"},
                },
                "required": ["ifade"],
            },
        },
    },
]
