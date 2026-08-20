"""Veritabanı katmanı.

Tek sorumluluğu SQLite ile konuşmak. Araç fonksiyonları (araclar.py) buradaki
işlevleri çağırır; SQL başka hiçbir dosyada geçmez.
"""

from __future__ import annotations  # Python 3.9 uyumluluğu (str | None yazımı için)

import difflib
import json
import re
import sqlite3
from pathlib import Path

VERITABANI = Path(__file__).resolve().parent.parent / "data" / "koc.db"


def normalize(metin: str) -> str:
    """Türkçe duyarlı küçük harfe çevirme.

    Python'un lower() metodu 'I' harfini 'i' yapar; Türkçede karşılığı 'ı'dır.
    Bu düzeltme olmadan "IŞIK" araması "ışık" kaydını bulamaz.
    """
    if not metin:
        return ""
    return metin.replace("İ", "i").replace("I", "ı").lower().strip()


# Türkçe karaktersiz yazımı desteklemek için: "hucre zari" -> "hücre zarı"
ASCII_HARITASI = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def asciiye_indir(metin: str) -> str:
    """Aksanları düşürür. Klavyesinde Türkçe karakter olmayan ya da hızlı yazan
    kullanıcının aramasının boşa çıkmaması için kullanılır."""
    return normalize(metin).translate(ASCII_HARITASI)


def kelime_deseni(kelime: str) -> re.Pattern:
    """Kelime BAŞINDAN eşleşen desen üretir.

    Neden alt-dize (LIKE '%tit%') değil: "tit" araması "nükleotit" ve "kromatit"
    kelimelerinin içine düşüyor ve alakasız sonuç dönüyordu. Kelime sınırı (\\b)
    bunu keser.

    Sonuna \\w* eklenir çünkü Türkçe eklemeli bir dildir: "mayoz" araması
    "mayozda", "mayozun" biçimlerini de bulmalıdır.
    """
    return re.compile(rf"\b{re.escape(normalize(kelime))}\w*", re.UNICODE)


def baglan() -> sqlite3.Connection:
    baglanti = sqlite3.connect(VERITABANI, check_same_thread=False)
    baglanti.row_factory = sqlite3.Row
    return baglanti


def semayi_kur(baglanti: sqlite3.Connection) -> None:
    baglanti.executescript(
        """
        CREATE TABLE IF NOT EXISTS terimler (
            id            INTEGER PRIMARY KEY,
            terim         TEXT NOT NULL,
            terim_norm    TEXT NOT NULL,
            tanim         TEXT NOT NULL,
            brans         TEXT,
            kitap_sayfasi TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_terim_norm ON terimler(terim_norm);

        CREATE TABLE IF NOT EXISTS sorular (
            id           INTEGER PRIMARY KEY,
            soru         TEXT NOT NULL,
            secenekler   TEXT NOT NULL,   -- JSON dizi
            dogru_cevap  INTEGER NOT NULL,-- 0..4
            bolum        TEXT
        );

        CREATE TABLE IF NOT EXISTS quiz_sonuclari (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id    TEXT NOT NULL,
            soru_id       INTEGER NOT NULL,
            verilen_cevap INTEGER NOT NULL,
            dogru_mu      INTEGER NOT NULL,
            zaman         TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (soru_id) REFERENCES sorular(id)
        );
        """
    )
    baglanti.commit()


# --------------------------------------------------------------------------
# OKUMA
# --------------------------------------------------------------------------


def terim_bul(baglanti, terim: str, limit: int = 3) -> tuple[list[dict], str]:
    """Kademeli arama. Döner: (kayıtlar, hangi kademede bulunduğu).

    Kademe bilgisi arayüzdeki şeffaflık panelinde gösterilir; kullanıcı sonucun
    birebir mi yoksa yaklaşık eşleşmeyle mi geldiğini görebilir.
    Uydurmayı engellemek için sonuç yoksa boş liste döner; asla tahmin üretmez.
    """
    aranan = normalize(terim)
    if not aranan:
        return [], "geçersiz sorgu"

    satirlar = baglanti.execute(
        "SELECT * FROM terimler WHERE terim_norm = ? LIMIT ?", (aranan, limit)
    ).fetchall()
    if satirlar:
        return [dict(s) for s in satirlar], "birebir eşleşme"

    # Aksansız birebir eşleşme: "nukleotit" -> "nükleotit"
    aranan_ascii = asciiye_indir(terim)
    tumu = baglanti.execute("SELECT * FROM terimler").fetchall()
    ascii_esleseni = [s for s in tumu if asciiye_indir(s["terim"]) == aranan_ascii]
    if ascii_esleseni:
        return [dict(s) for s in ascii_esleseni[:limit]], "Türkçe karaktersiz birebir eşleşme"

    # Son çare: kelime sınırıyla doğrulanmış alt-dize eşleşmesi.
    desen = kelime_deseni(aranan)
    adaylar = sorted(tumu, key=lambda s: len(s["terim_norm"]))
    bulunan = [dict(s) for s in adaylar if desen.search(s["terim_norm"])][:limit]
    return bulunan, ("kelime sınırı eşleşmesi" if bulunan else "eşleşme yok")


def terim_onerileri(baglanti, terim: str, limit: int = 5) -> list[str]:
    """Aranan kelimeye yakın sözlük terimlerini önerir. İki kademelidir.

    1) Alt-dize: "tit" -> "nükleotit". Kelimenin içinde geçenleri bulur.
    2) Benzerlik: "fotosentz" -> "fotosentez". Alt-dize hiçbir şey bulamadığında
       devreye girer; yazım hatalarını ve eksik/fazla harfleri yakalar.

    İkinci kademe olmadan bir harf yanlış yazan kullanıcı boş sonuçla kalıyordu.
    """
    aranan = asciiye_indir(terim)
    if not aranan or len(aranan) < 2:
        return []

    # Sözlük 1000 kayıtlık; tamamı belleğe alınıp aksansız karşılaştırılıyor.
    # Büyürse ayrı bir `terim_ascii` kolonu + indeks veya FTS5 gerekir.
    satirlar = baglanti.execute("SELECT DISTINCT terim FROM terimler").fetchall()
    asciiden_terime = {}
    for s in satirlar:
        asciiden_terime.setdefault(asciiye_indir(s["terim"]), s["terim"])

    # 1. kademe — alt-dize: "tit" -> "nükleotit", "hucre zari" -> "hücre zarı"
    icerenler = sorted(
        (a for a in asciiden_terime if aranan in a), key=len
    )
    if icerenler:
        return [asciiden_terime[a] for a in icerenler[:limit]]

    # 2. kademe — benzerlik: "fotosentz" -> "fotosentez", "mayos" -> "mayoz"
    yakinlar = difflib.get_close_matches(aranan, list(asciiden_terime), n=limit, cutoff=0.75)
    return [asciiden_terime[a] for a in yakinlar]


def soru_getir(baglanti, konu: str | None = None, adet: int = 1) -> list[dict]:
    """Soru bankasından soru çeker. dogru_cevap BİLİNÇLİ OLARAK döndürülmez.

    Konu eşleşmesi kelime sınırına göre yapılır. Soru bankası küçük (102 kayıt)
    olduğu için filtreleme Python tarafında yapılır; SQLite'ta yerleşik regex
    desteği yoktur. Bankalar büyürse FTS5 tablosuna geçilmelidir.
    """
    adet = max(1, min(int(adet or 1), 5))

    if not konu:
        satirlar = baglanti.execute(
            "SELECT * FROM sorular ORDER BY RANDOM() LIMIT ?", (adet,)
        ).fetchall()
    else:
        desen = kelime_deseni(konu)
        tumu = baglanti.execute("SELECT * FROM sorular").fetchall()
        satirlar = [s for s in tumu if desen.search(normalize(s["soru"]))][:adet]

    return [
        {
            "soru_id": s["id"],
            "soru": s["soru"],
            "secenekler": json.loads(s["secenekler"]),
        }
        for s in satirlar
    ]


def konu_onerileri(baglanti, konu: str, limit: int = 5) -> list[str]:
    """Soru bankasında GERÇEKTEN sorusu olan benzer konuları önerir.

    Sözlükte terim bulunması yetmez; o terimle ilgili soru yoksa öneri boşa
    çıkar ve kullanıcı ikinci kez hayal kırıklığına uğrar. Bu yüzden her aday
    terim, soru bankasında doğrulanır.
    """
    oneriler = []
    tumu = baglanti.execute("SELECT soru FROM sorular").fetchall()
    metinler = [normalize(s["soru"]) for s in tumu]

    for aday in terim_onerileri(baglanti, konu, limit=15):
        desen = kelime_deseni(aday)
        if any(desen.search(m) for m in metinler):
            oneriler.append(aday)
            if len(oneriler) >= limit:
                break
    return oneriler


def soru_cevabi(baglanti, soru_id: int) -> int | None:
    satir = baglanti.execute(
        "SELECT dogru_cevap FROM sorular WHERE id = ?", (soru_id,)
    ).fetchone()
    return satir["dogru_cevap"] if satir else None


def ilerleme(baglanti, ogrenci_id: str) -> dict:
    satir = baglanti.execute(
        """SELECT COUNT(*) AS toplam, COALESCE(SUM(dogru_mu), 0) AS dogru
           FROM quiz_sonuclari WHERE ogrenci_id = ?""",
        (ogrenci_id,),
    ).fetchone()
    return {"toplam": satir["toplam"], "dogru": satir["dogru"]}


# --------------------------------------------------------------------------
# YAZMA
# --------------------------------------------------------------------------


def sonuc_kaydet(baglanti, ogrenci_id: str, soru_id: int, verilen: int, dogru_mu: bool) -> int:
    imlec = baglanti.execute(
        """INSERT INTO quiz_sonuclari (ogrenci_id, soru_id, verilen_cevap, dogru_mu)
           VALUES (?, ?, ?, ?)""",
        (ogrenci_id, soru_id, verilen, int(dogru_mu)),
    )
    baglanti.commit()
    return imlec.lastrowid
