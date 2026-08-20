import sqlite3

def baglan():
    return sqlite3.connect("meslekler.db")

def tablo_kur():
    baglanti = baglan()
    baglanti.execute("""
    CREATE TABLE IF NOT EXISTS meslek_listem (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_id TEXT NOT NULL,
        meslek TEXT NOT NULL,
        not_bilgisi TEXT,
        eklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    baglanti.execute("""
    CREATE TABLE IF NOT EXISTS kullanici_profili (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kullanici_id TEXT NOT NULL,
        ozet TEXT NOT NULL,
        kayit_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    baglanti.commit()
    baglanti.close()

def ekle(kullanici_id, meslek, not_bilgisi=""):
    baglanti = baglan()
    baglanti.execute(
        "INSERT INTO meslek_listem (kullanici_id, meslek, not_bilgisi) VALUES (?, ?, ?)",
        (kullanici_id, meslek, not_bilgisi),
    )
    baglanti.commit()
    baglanti.close()

def listele(kullanici_id):
    baglanti = baglan()
    imlec = baglanti.execute(
        "SELECT id, meslek, not_bilgisi, eklenme_tarihi FROM meslek_listem WHERE kullanici_id = ?",
        (kullanici_id,),
    )
    satirlar = imlec.fetchall()
    baglanti.close()
    return satirlar

def profil_kaydet(kullanici_id, ozet):
    baglanti = baglan()
    baglanti.execute(
        "INSERT INTO kullanici_profili (kullanici_id, ozet) VALUES (?, ?)",
        (kullanici_id, ozet),
    )
    baglanti.commit()
    baglanti.close()

def profil_getir(kullanici_id):
    baglanti = baglan()
    imlec = baglanti.execute(
        "SELECT ozet FROM kullanici_profili WHERE kullanici_id = ? ORDER BY id DESC LIMIT 1",
        (kullanici_id,),
    )
    satir = imlec.fetchone()
    baglanti.close()
    return satir[0] if satir else None

tablo_kur()

if __name__ == "__main__":
    profil_kaydet("deneme", "Matematik ve bilgisayari seven bir ogrenci.")
    print("deneme profili:", profil_getir("deneme"))
