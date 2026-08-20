"""database.py — Veritabanı katmanı.

Bu modül SQLite ile ilgili HER ŞEYİ içerir; başka hiçbir dosya doğrudan SQL
yazmaz. Böylece veritabanı değişirse (örneğin PostgreSQL'e geçilirse) yalnızca
bu dosya değişir.

Tablolar:
    seferler        — uçuş bilgileri ve boş koltuk sayısı
    rezervasyonlar  — yapılan rezervasyonlar (seferler tablosuna bağlı)
"""

import os
import random
import sqlite3
import string
from datetime import datetime, timedelta

VERITABANI = os.environ.get("DB_YOLU", "ucus.db")


# ---------------------------------------------------------------------------
# Bağlantı
# ---------------------------------------------------------------------------
def baglan():
    """Veritabanı bağlantısı açar.

    row_factory = sqlite3.Row sayesinde sonuçlara sütun adıyla erişilebilir:
        satir["kalkis"]   yerine   satir[1]
    Bu, kodu okunabilir kılar ve sütun sırası değişse bile bozulmaz.

    foreign_keys = ON: SQLite'ta yabancı anahtar denetimi varsayılan olarak
    KAPALIDIR; her bağlantıda açılması gerekir. Bu olmadan, var olmayan bir
    sefere rezervasyon eklenebilirdi.
    """
    conn = sqlite3.connect(VERITABANI)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Şema
# ---------------------------------------------------------------------------
def tablolari_olustur():
    """Tabloları oluşturur (yoksa)."""
    with baglan() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seferler (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ucus_kodu    TEXT    NOT NULL UNIQUE,
                firma        TEXT    NOT NULL,
                kalkis       TEXT    NOT NULL,
                varis        TEXT    NOT NULL,
                tarih        TEXT    NOT NULL,
                kalkis_saati TEXT    NOT NULL,
                varis_saati  TEXT    NOT NULL,
                fiyat        REAL    NOT NULL,
                bos_koltuk   INTEGER NOT NULL CHECK (bos_koltuk >= 0)
            );

            CREATE TABLE IF NOT EXISTS rezervasyonlar (
                pnr              TEXT    PRIMARY KEY,
                sefer_id         INTEGER NOT NULL,
                yolcu_adi        TEXT    NOT NULL,
                koltuk_sayisi    INTEGER NOT NULL CHECK (koltuk_sayisi > 0),
                toplam_fiyat     REAL    NOT NULL,
                durum            TEXT    NOT NULL DEFAULT 'onaylandi',
                olusturma_tarihi TEXT    NOT NULL,
                FOREIGN KEY (sefer_id) REFERENCES seferler(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sefer_arama
                ON seferler(kalkis, varis, tarih);
        """)


# CHECK (bos_koltuk >= 0):
#   Veritabanı düzeyinde koruma. Bir hata sonucu koltuk sayısı eksiye
#   düşmeye çalışırsa SQLite işlemi reddeder. Koddaki kontrolün yedeğidir.
#
# UNIQUE (ucus_kodu):
#   Aynı uçuş kodu iki kez eklenemez.
#
# INDEX:
#   Arama sorgusu (kalkis + varis + tarih) sık çalışacağı için hızlandırılır.


# ---------------------------------------------------------------------------
# Örnek veri
# ---------------------------------------------------------------------------
SEHIRLER = [
    ("İstanbul", "IST"), ("Ankara", "ESB"), ("İzmir", "ADB"),
    ("Antalya", "AYT"), ("Trabzon", "TZX"), ("Adana", "ADA"),
    ("Gaziantep", "GZT"), ("Dalaman", "DLM"),
]

FIRMALAR = ["Anadolu Hava", "Marmara Havayolları", "Ege Air", "Toros Havacılık"]


def ornek_veri_ekle(sefer_sayisi=28):
    """Rastgele ama gerçekçi seferler üretir.

    Sabit tohum (seed) kullanılır: her çalıştırmada aynı veri oluşur.
    Böylece test sonuçları tekrarlanabilir olur.
    """
    with baglan() as conn:
        mevcut = conn.execute("SELECT COUNT(*) FROM seferler").fetchone()[0]
        if mevcut > 0:
            return mevcut  # veri zaten var, tekrar ekleme

        rnd = random.Random(42)
        bugun = datetime.now().date()
        eklenen = 0
        kullanilan_kodlar = set()

        while eklenen < sefer_sayisi:
            kalkis, kalkis_kod = rnd.choice(SEHIRLER)
            varis, _ = rnd.choice(SEHIRLER)
            if kalkis == varis:
                continue                       # aynı şehre uçuş olmaz

            # Uçuş kodu: TK1234 gibi
            kod = f"{kalkis_kod[:2]}{rnd.randint(1000, 9999)}"
            if kod in kullanilan_kodlar:
                continue
            kullanilan_kodlar.add(kod)

            tarih = bugun + timedelta(days=rnd.randint(1, 14))
            kalkis_saat = rnd.choice(
                ["06:30", "08:15", "10:45", "13:20", "15:50", "18:30", "21:10"])

            # Varış saati: 1-2 saat sonra
            sa, dk = map(int, kalkis_saat.split(":"))
            sure = rnd.choice([60, 75, 90, 105, 120])
            varis_dt = datetime(2000, 1, 1, sa, dk) + timedelta(minutes=sure)

            conn.execute("""
                INSERT INTO seferler
                    (ucus_kodu, firma, kalkis, varis, tarih,
                     kalkis_saati, varis_saati, fiyat, bos_koltuk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                kod,
                rnd.choice(FIRMALAR),
                kalkis, varis,
                tarih.isoformat(),
                kalkis_saat,
                varis_dt.strftime("%H:%M"),
                round(rnd.uniform(850, 4200), 2),
                rnd.randint(0, 60),            # bazı seferler dolu olabilir (0)
            ))
            eklenen += 1

        return eklenen


# ---------------------------------------------------------------------------
# Okuma işlemleri
# ---------------------------------------------------------------------------
def sefer_ara(kalkis=None, varis=None, tarih=None, limit=10):
    """Seferleri arar. Parametreler isteğe bağlıdır; verilenler filtre olur."""
    sorgu = "SELECT * FROM seferler WHERE bos_koltuk > 0"
    parametreler = []

    # Sorguyu parça parça kur: yalnızca verilen filtreler eklenir.
    # Dikkat: değerler doğrudan metne eklenmez, ? ile parametre olarak geçer.
    # Bu, SQL injection saldırılarını önler.
    if kalkis:
        sorgu += " AND LOWER(kalkis) LIKE LOWER(?)"
        parametreler.append(f"%{kalkis}%")
    if varis:
        sorgu += " AND LOWER(varis) LIKE LOWER(?)"
        parametreler.append(f"%{varis}%")
    if tarih:
        sorgu += " AND tarih = ?"
        parametreler.append(tarih)

    sorgu += " ORDER BY tarih, kalkis_saati LIMIT ?"
    parametreler.append(limit)

    with baglan() as conn:
        satirlar = conn.execute(sorgu, parametreler).fetchall()
    return [dict(s) for s in satirlar]


def sefer_getir(sefer_id):
    """Tek bir seferi id ile getirir. Yoksa None döner."""
    with baglan() as conn:
        satir = conn.execute(
            "SELECT * FROM seferler WHERE id = ?", (sefer_id,)).fetchone()
    return dict(satir) if satir else None


def rezervasyon_getir(pnr):
    """PNR ile rezervasyonu, bağlı olduğu sefer bilgisiyle birlikte getirir.

    JOIN: iki tabloyu birleştirir. rezervasyonlar.sefer_id ile
    seferler.id eşleştirilerek uçuş detayları da tek sorguda alınır.
    """
    with baglan() as conn:
        satir = conn.execute("""
            SELECT r.*, s.ucus_kodu, s.firma, s.kalkis, s.varis,
                   s.tarih, s.kalkis_saati, s.varis_saati
            FROM rezervasyonlar r
            JOIN seferler s ON r.sefer_id = s.id
            WHERE r.pnr = ?
        """, (pnr.upper(),)).fetchone()
    return dict(satir) if satir else None


# ---------------------------------------------------------------------------
# Yazma işlemi
# ---------------------------------------------------------------------------
def _pnr_uret():
    """6 karakterlik rezervasyon kodu üretir (örn. 'K7X2M9')."""
    karakterler = string.ascii_uppercase + string.digits
    return "".join(random.choices(karakterler, k=6))


def rezervasyon_olustur(sefer_id, yolcu_adi, koltuk_sayisi):
    """Rezervasyon oluşturur ve seferin boş koltuk sayısını düşürür.

    Bu iki işlem TEK BİR TRANSACTION içinde yapılır: ya ikisi de gerçekleşir
    ya da hiçbiri. Aksi hâlde rezervasyon kaydedilip koltuk düşmezse aynı
    koltuk iki kez satılabilir.

    Dönüş: (basarili: bool, sonuc: dict)
    """
    conn = baglan()
    try:
        # BEGIN IMMEDIATE: yazma kilidini hemen alır. Aynı anda iki kişi
        # son koltuğu almaya çalışırsa biri beklemek zorunda kalır.
        conn.execute("BEGIN IMMEDIATE")

        sefer = conn.execute(
            "SELECT * FROM seferler WHERE id = ?", (sefer_id,)).fetchone()

        # --- Doğrulama 1: sefer var mı? ---
        # Model uydurma bir sefer_id gönderirse burada durur.
        if sefer is None:
            conn.rollback()
            return False, {"hata": f"{sefer_id} numaralı sefer bulunamadı."}

        # --- Doğrulama 2: yeterli koltuk var mı? ---
        if sefer["bos_koltuk"] < koltuk_sayisi:
            conn.rollback()
            return False, {
                "hata": f"Yetersiz koltuk. Talep: {koltuk_sayisi}, "
                        f"mevcut: {sefer['bos_koltuk']}."
            }

        # --- Benzersiz PNR üret ---
        for _ in range(10):
            pnr = _pnr_uret()
            varsa = conn.execute(
                "SELECT 1 FROM rezervasyonlar WHERE pnr = ?", (pnr,)).fetchone()
            if not varsa:
                break
        else:
            conn.rollback()
            return False, {"hata": "Rezervasyon kodu üretilemedi, tekrar deneyin."}

        toplam = round(sefer["fiyat"] * koltuk_sayisi, 2)

        # --- İşlem 1: rezervasyonu kaydet ---
        conn.execute("""
            INSERT INTO rezervasyonlar
                (pnr, sefer_id, yolcu_adi, koltuk_sayisi,
                 toplam_fiyat, durum, olusturma_tarihi)
            VALUES (?, ?, ?, ?, ?, 'onaylandi', ?)
        """, (pnr, sefer_id, yolcu_adi, koltuk_sayisi, toplam,
              datetime.now().isoformat(timespec="seconds")))

        # --- İşlem 2: koltuk sayısını düşür ---
        conn.execute(
            "UPDATE seferler SET bos_koltuk = bos_koltuk - ? WHERE id = ?",
            (koltuk_sayisi, sefer_id))

        conn.commit()          # ikisi birden kalıcı olur

        return True, {
            "pnr": pnr,
            "ucus_kodu": sefer["ucus_kodu"],
            "firma": sefer["firma"],
            "kalkis": sefer["kalkis"],
            "varis": sefer["varis"],
            "tarih": sefer["tarih"],
            "kalkis_saati": sefer["kalkis_saati"],
            "yolcu_adi": yolcu_adi,
            "koltuk_sayisi": koltuk_sayisi,
            "toplam_fiyat": toplam,
            "kalan_koltuk": sefer["bos_koltuk"] - koltuk_sayisi,
        }

    except sqlite3.Error as e:
        conn.rollback()        # hata olursa hiçbir değişiklik kalmaz
        return False, {"hata": f"Veritabanı hatası: {e}"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
def hazirla():
    """Uygulama başlarken çağrılır: tabloları kurar, veri yoksa ekler."""
    tablolari_olustur()
    return ornek_veri_ekle()


if __name__ == "__main__":
    sayi = hazirla()
    print(f"Veritabanı hazır: {VERITABANI}")
    with baglan() as c:
        toplam = c.execute("SELECT COUNT(*) FROM seferler").fetchone()[0]
        rez = c.execute("SELECT COUNT(*) FROM rezervasyonlar").fetchone()[0]
    print(f"  Sefer sayısı       : {toplam}")
    print(f"  Rezervasyon sayısı : {rez}")
