import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta


# Veritabanı backend klasörünün içinde tutulacak
DB_PATH = Path(__file__).resolve().parent / "kariyer.db"


GECERLI_DURUMLAR = [
    "Başvuruldu",
    "Değerlendirmede",
    "Test Aşamasında",
    "Mülakat",
    "Teklif",
    "Reddedildi",
    "Geri Dönüş Yok",
]


def turkce_kucuk_harf(metin):
    """
    Türkçe'ye duyarlı küçük harfe çevirme.

    SQLite'ın yerleşik COLLATE NOCASE'i yalnızca ASCII harfleri (a-z)
    büyük/küçük harf eşitliyor; Türkçe'ye özgü İ/I harflerini doğru
    çevirmiyor (Ş/ğ/ü/ö/ç zaten Python'un standart .lower()'ında doğru
    çalışıyor, sorun yalnızca İ/I/ı/i kümesinde).
    """

    if metin is None:
        return None

    metin = metin.replace("İ", "i").replace("I", "ı")

    return metin.lower()


def baglanti_olustur():
    """
    SQLite veritabanına bağlantı oluşturur.

    Türkçe karakterlerde doğru büyük/küçük harf duyarsız arama
    yapabilmek için TR_LOWER adında özel bir SQL fonksiyonu kaydedilir
    (bkz. turkce_kucuk_harf).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("TR_LOWER", 1, turkce_kucuk_harf)
    return conn


def db_baslat():
    """
    Gerekli tabloları oluşturur.
    """
    conn = baglanti_olustur()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS basvurular (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sirket TEXT NOT NULL,
            pozisyon TEXT NOT NULL,
            basvuru_tarihi TEXT NOT NULL,
            durum TEXT NOT NULL DEFAULT 'Başvuruldu',
            ilan_linki TEXT,
            mulakat_tarihi TEXT,
            notlar TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def basvuru_ekle(
    sirket,
    pozisyon,
    basvuru_tarihi,
    durum="Başvuruldu",
    ilan_linki="",
    mulakat_tarihi=None,
    notlar="",
):
    """
    Yeni iş başvurusu ekler.
    """

    if durum not in GECERLI_DURUMLAR:
        return {
            "basarili": False,
            "mesaj": f"Geçersiz durum: {durum}",
            "gecerli_durumlar": GECERLI_DURUMLAR,
        }

    conn = baglanti_olustur()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO basvurular (
            sirket,
            pozisyon,
            basvuru_tarihi,
            durum,
            ilan_linki,
            mulakat_tarihi,
            notlar,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sirket,
            pozisyon,
            basvuru_tarihi,
            durum,
            ilan_linki,
            mulakat_tarihi,
            notlar,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )

    basvuru_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "basarili": True,
        "mesaj": "Başvuru başarıyla eklendi.",
        "basvuru_id": basvuru_id,
        "sirket": sirket,
        "pozisyon": pozisyon,
        "durum": durum,
    }


def basvuru_ara(arama):
    """
    Şirket veya pozisyon adına göre başvuru arar.
    """
    conn = baglanti_olustur()
    cursor = conn.cursor()

    arama_degeri = f"%{arama}%"

    cursor.execute(
        """
        SELECT *
        FROM basvurular
        WHERE TR_LOWER(sirket) LIKE TR_LOWER(?)
           OR TR_LOWER(pozisyon) LIKE TR_LOWER(?)
        ORDER BY id DESC
        """,
        (arama_degeri, arama_degeri),
    )

    satirlar = cursor.fetchall()
    conn.close()

    if not satirlar:
        return {
            "basarili": False,
            "mesaj": "Bu kriterlere uygun bir başvuru bulunamadı.",
            "sonuclar": [],
        }

    return {
        "basarili": True,
        "adet": len(satirlar),
        "sonuclar": [dict(satir) for satir in satirlar],
    }


def basvuru_listele(durum=None, sirket=None, pozisyon=None):
    """
    Başvuruları isteğe bağlı filtrelerle listeler.
    """
    conn = baglanti_olustur()
    cursor = conn.cursor()

    sorgu = "SELECT * FROM basvurular WHERE 1=1"
    parametreler = []

    if durum:
        sorgu += " AND durum = ?"
        parametreler.append(durum)

    if sirket:
        sorgu += " AND TR_LOWER(sirket) LIKE TR_LOWER(?)"
        parametreler.append(f"%{sirket}%")

    if pozisyon:
        sorgu += " AND TR_LOWER(pozisyon) LIKE TR_LOWER(?)"
        parametreler.append(f"%{pozisyon}%")

    sorgu += " ORDER BY basvuru_tarihi DESC, id DESC"

    cursor.execute(sorgu, parametreler)
    satirlar = cursor.fetchall()

    conn.close()

    return {
        "basarili": True,
        "adet": len(satirlar),
        "sonuclar": [dict(satir) for satir in satirlar],
    }


def basvuru_guncelle(
    basvuru_id,
    yeni_durum=None,
    mulakat_tarihi=None,
    notlar=None,
):
    """
    Belirtilen ID'ye ait başvuruyu günceller.
    """

    if yeni_durum and yeni_durum not in GECERLI_DURUMLAR:
        return {
            "basarili": False,
            "mesaj": f"Geçersiz durum: {yeni_durum}",
            "gecerli_durumlar": GECERLI_DURUMLAR,
        }

    conn = baglanti_olustur()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM basvurular WHERE id = ?",
        (basvuru_id,),
    )

    mevcut = cursor.fetchone()

    if mevcut is None:
        conn.close()
        return {
            "basarili": False,
            "mesaj": f"{basvuru_id} ID'li başvuru bulunamadı.",
        }

    alanlar = []
    degerler = []

    if yeni_durum is not None:
        alanlar.append("durum = ?")
        degerler.append(yeni_durum)

    if mulakat_tarihi is not None:
        alanlar.append("mulakat_tarihi = ?")
        degerler.append(mulakat_tarihi)

    if notlar is not None:
        alanlar.append("notlar = ?")
        degerler.append(notlar)

    if not alanlar:
        conn.close()
        return {
            "basarili": False,
            "mesaj": "Güncellenecek herhangi bir alan belirtilmedi.",
        }

    degerler.append(basvuru_id)

    sorgu = f"""
        UPDATE basvurular
        SET {", ".join(alanlar)}
        WHERE id = ?
    """

    cursor.execute(sorgu, degerler)

    conn.commit()

    cursor.execute(
        "SELECT * FROM basvurular WHERE id = ?",
        (basvuru_id,),
    )

    guncel_basvuru = cursor.fetchone()

    conn.close()

    return {
        "basarili": True,
        "mesaj": "Başvuru başarıyla güncellendi.",
        "basvuru": dict(guncel_basvuru),
    }


def basvuru_istatistikleri():
    """
    Başvuruların genel istatistiklerini döndürür.
    """
    conn = baglanti_olustur()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS toplam FROM basvurular")
    toplam = cursor.fetchone()["toplam"]

    cursor.execute(
        """
        SELECT durum, COUNT(*) AS adet
        FROM basvurular
        GROUP BY durum
        ORDER BY adet DESC
        """
    )

    durumlar = {
        satir["durum"]: satir["adet"]
        for satir in cursor.fetchall()
    }

    cursor.execute(
        """
        SELECT pozisyon, COUNT(*) AS adet
        FROM basvurular
        GROUP BY pozisyon
        ORDER BY adet DESC
        LIMIT 5
        """
    )

    pozisyonlar = [
        dict(satir)
        for satir in cursor.fetchall()
    ]

    conn.close()

    return {
        "basarili": True,
        "toplam_basvuru": toplam,
        "durumlara_gore": durumlar,
        "en_cok_basvurulan_pozisyonlar": pozisyonlar,
    }


def yaklasan_mulakatlari_getir(gun_sayisi=30):
    """
    Bugünden itibaren belirtilen gün sayısı içindeki
    mülakatları getirir.
    """

    bugun = date.today()
    bitis_tarihi = bugun + timedelta(days=gun_sayisi)

    conn = baglanti_olustur()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM basvurular
        WHERE mulakat_tarihi IS NOT NULL
          AND DATE(mulakat_tarihi) BETWEEN DATE(?) AND DATE(?)
        ORDER BY DATE(mulakat_tarihi) ASC
        """,
        (
            bugun.isoformat(),
            bitis_tarihi.isoformat(),
        ),
    )

    satirlar = cursor.fetchall()
    conn.close()

    return {
        "basarili": True,
        "gun_sayisi": gun_sayisi,
        "adet": len(satirlar),
        "sonuclar": [dict(satir) for satir in satirlar],
    }


if __name__ == "__main__":
    db_baslat()

    sonuc = basvuru_ekle(
        sirket="Test Bank",
        pozisyon="AI Engineer Intern",
        basvuru_tarihi="2026-08-12"
    )

    print(sonuc)

    print(basvuru_listele())