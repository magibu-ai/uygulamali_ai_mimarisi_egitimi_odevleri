import httpx

import db

WIKI_BASLIKLARI = {"User-Agent": "magibu-ders6-thy-asistan/1.0 (egitim odevi; iletisim: salih12dede@gmail.com)"}


def wikipedia_arastir(sorgu, dil="tr"):
    """Wikipedia'da arayip en alakali maddenin ozetini doner (anahtarsiz)."""
    try:
        dil = (dil or "tr").strip().lower()
        arama = httpx.get(
            f"https://{dil}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": sorgu, "srlimit": 1, "format": "json"},
            headers=WIKI_BASLIKLARI, timeout=15,
        ).json()
        bulunanlar = arama.get("query", {}).get("search", [])
        if not bulunanlar:
            return {"hata": f"'{sorgu}' icin Wikipedia'da sonuc bulunamadi."}
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

        return {"baslik": baslik, "ozet": metin or "Ozet bulunamadi.", "kaynak": f"Wikipedia ({dil})"}
    except Exception as e:
        return {"hata": f"Wikipedia sorgusu basarisiz: {e}"}


def sehir_saat(sehir):
    """Turkiye'nin guncel yerel tarih/saatini doner (timeapi.io). Tum TR tek saat diliminde."""
    try:
        eslesen = next((s for s in db.SEHIRLER if s.lower() == sehir.strip().lower()), None)
        if eslesen is None and sehir.strip().lower() != db.KALKIS_SEHRI.lower():
            return {"hata": f"'{sehir}' TR havalimani listesinde yok."}

        veri = httpx.get(
            "https://timeapi.io/api/time/current/zone",
            params={"timeZone": db.SAAT_DILIMI}, timeout=15,
        ).json()
        return {
            "sehir": eslesen or db.KALKIS_SEHRI, "saat_dilimi": db.SAAT_DILIMI,
            "yerel_tarih_saat": veri.get("dateTime"), "gun": veri.get("dayOfWeek"),
            "kaynak": "timeapi.io",
        }
    except Exception as e:
        return {"hata": f"Saat bilgisi alinamadi: {e}"}


def ucus_ara(sehir):
    """Bir sehre giden musait THY ucuslarini SQLite katalogundan doner."""
    try:
        sonuclar = db.ucus_ara(sehir)
        if not sonuclar:
            return {"hata": f"'{sehir}' icin musait ucus bulunamadi."}
        return {"sehir": sehir, "ucuslar": sonuclar}
    except Exception as e:
        return {"hata": f"Ucus aramasi basarisiz: {e}"}


def doviz_cevir(miktar, kaynak_birim, hedef_birim):
    """Guncel ECB kuruyla para birimi cevirir (Frankfurter, anahtarsiz)."""
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
            return {"hata": f"{kaynak_birim} -> {hedef_birim} kuru bulunamadi."}
        return {
            "miktar": miktar, "kaynak_birim": kaynak_birim, "hedef_birim": hedef_birim,
            "sonuc": round(oranlar[hedef_birim], 4), "kur_tarihi": veri.get("date"),
            "kaynak": "Frankfurter / ECB",
        }
    except Exception as e:
        return {"hata": f"Doviz cevrilemedi: {e}"}


def _try_karsiligi(fiyat_try, para_birimi):
    """Bilet fiyati (TRY) kullanicinin bakiye para birimine cevrilir. Ayni birimse cevrim yapilmaz."""
    if para_birimi == "TRY":
        return fiyat_try, None
    donusum = doviz_cevir(fiyat_try, "TRY", para_birimi)
    if "hata" in donusum:
        return None, donusum
    return donusum["sonuc"], donusum


def bakiye_sorgula(durum):
    """Oturuma ait guncel THY cuzdan bakiyesini kullanicinin sectigi para biriminde doner."""
    return {
        "bakiye": durum["bakiye"], "para_birimi": durum["para_birimi"],
        "alinan_bilet_sayisi": len(durum["biletler"]),
    }


def bilet_al(ucus_id, durum):
    """Secilen ucus icin bilet keser: TRY fiyati bakiye para birimine cevirir, dusurur, PNR uretir."""
    ucus_id = int(ucus_id)
    ucus = db.ucus_getir(ucus_id)
    if ucus is None:
        return {"hata": f"'{ucus_id}' numarali bir ucus yok."}

    tutar, donusum = _try_karsiligi(ucus["fiyat_try"], durum["para_birimi"])
    if tutar is None:
        return donusum
    if tutar > durum["bakiye"]:
        return {
            "hata": f"Bakiye yetersiz. Bilet {tutar:.2f} {durum['para_birimi']} "
                    f"({ucus['fiyat_try']} TRY), bakiye {durum['bakiye']:.2f} {durum['para_birimi']}."
        }

    sonuc = db.bilet_yaz(ucus_id)
    if sonuc is None:
        return {"hata": f"'{ucus_id}' numarali bir ucus yok."}
    if sonuc.get("dolu"):
        return {"hata": "Bu ucusta bos koltuk kalmadi."}

    durum["bakiye"] = round(durum["bakiye"] - tutar, 2)
    durum["biletler"].append({"pnr": sonuc["pnr"], "ucus": sonuc["ucus"], "odenen": tutar})
    return {
        "pnr": sonuc["pnr"], "ucus": sonuc["ucus"],
        "odenen_try": sonuc["ucus"]["fiyat_try"],
        "odenen": tutar, "para_birimi": durum["para_birimi"],
        "kur_bilgisi": donusum, "kalan_bakiye": durum["bakiye"],
    }


# Durum (oturum) gerektirmeyen araclar
ARAC_FONKSIYONLARI = {
    "wikipedia_arastir": wikipedia_arastir,
    "sehir_saat": sehir_saat,
    "ucus_ara": ucus_ara,
    "doviz_cevir": doviz_cevir,
}

# Durum (oturuma ait bakiye/biletler) gerektiren araclar
DURUM_GEREKTIREN_ARACLAR = {
    "bakiye_sorgula": bakiye_sorgula,
    "bilet_al": bilet_al,
}

ARAC_SEMALARI = [
    {
        "type": "function",
        "function": {
            "name": "wikipedia_arastir",
            "description": "Bir yer/eser/kavram hakkinda Wikipedia ozeti getirir. Kullanici bir mekan/sehir soylediginde once bunu cagir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Aranacak konu, orn: Eyfel Kulesi"},
                    "dil": {"type": "string", "description": "Wikipedia dil kodu: tr veya en. Varsayilan tr."},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sehir_saat",
            "description": "Bir sehrin guncel yerel tarih/saatini doner.",
            "parameters": {
                "type": "object",
                "properties": {"sehir": {"type": "string", "description": "Sehir adi, orn: Paris"}},
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ucus_ara",
            "description": "Belirtilen sehre giden musait THY ucuslarini, sefer no/tarih/saat/fiyat ile doner.",
            "parameters": {
                "type": "object",
                "properties": {"sehir": {"type": "string", "description": "Varis sehri, orn: Paris"}},
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doviz_cevir",
            "description": "Guncel kurla bir para biriminden digerine cevirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "miktar": {"type": "number"},
                    "kaynak_birim": {"type": "string", "description": "orn: TRY"},
                    "hedef_birim": {"type": "string", "description": "orn: EUR"},
                },
                "required": ["miktar", "kaynak_birim", "hedef_birim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bakiye_sorgula",
            "description": "Kullanicinin guncel THY cuzdan bakiyesini, kendi sectigi para biriminde doner.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bilet_al",
            "description": (
                "ucus_ara sonucundaki bir ucusun id'siyle bilet keser. Bilet fiyati TRY'dir; "
                "bakiye baska bir para birimindeyse otomatik cevrilip oradan duser. PNR uretir."
            ),
            "parameters": {
                "type": "object",
                "properties": {"ucus_id": {"type": "integer", "description": "ucus_ara sonucundaki 'id' alani"}},
                "required": ["ucus_id"],
            },
        },
    },
]


def araci_calistir(ad, argumanlar, durum):
    argumanlar = argumanlar or {}
    if ad in DURUM_GEREKTIREN_ARACLAR:
        try:
            return DURUM_GEREKTIREN_ARACLAR[ad](durum=durum, **argumanlar)
        except TypeError as e:
            return {"hata": f"'{ad}' hatali argumanlarla cagrildi: {e}"}
    fonksiyon = ARAC_FONKSIYONLARI.get(ad)
    if fonksiyon is None:
        return {"hata": f"'{ad}' adinda bir arac yok."}
    try:
        return fonksiyon(**argumanlar)
    except TypeError as e:
        return {"hata": f"'{ad}' hatali argumanlarla cagrildi: {e}"}
