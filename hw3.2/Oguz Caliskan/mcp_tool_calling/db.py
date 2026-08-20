"""
Sondaj Malzeme Depo Yönetim Asistanı - Veritabanı Katmanı (SQLite).

Tablolar:
  - malzeme: depodaki ekipman/malzeme envanteri (okuma ağırlıklı)
  - talep: kuyu bazlı malzeme talepleri (yazma + okuma)
"""
import sqlite3
import os
from datetime import datetime

DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "depo.db")


def baglanti_al():
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    return conn


def veritabanini_kur():
    """Tabloları oluşturur (yoksa) ve örnek envanter verisiyle doldurur (boşsa)."""
    conn = baglanti_al()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS malzeme (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL UNIQUE,
            kategori TEXT NOT NULL,
            stok_adet INTEGER NOT NULL,
            birim TEXT NOT NULL,
            lokasyon TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS talep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            malzeme_id INTEGER NOT NULL,
            malzeme_adi TEXT NOT NULL,
            adet INTEGER NOT NULL,
            kuyu_adi TEXT NOT NULL,
            durum TEXT NOT NULL DEFAULT 'Onay Bekliyor',
            tarih TEXT NOT NULL,
            FOREIGN KEY (malzeme_id) REFERENCES malzeme (id)
        )
    """)

    cur.execute("SELECT COUNT(*) FROM malzeme")
    if cur.fetchone()[0] == 0:
        ornek_malzemeler = [
            ("9 5/8\" Casing", "Casing", 1200, "adet", "Batman Depo"),
            ("7\" Casing", "Casing", 850, "adet", "Batman Depo"),
            ("13 3/8\" Casing", "Casing", 400, "adet", "Sırnak Depo"),
            ("9 5/8\" Centralizer", "Centralizer", 600, "adet", "Batman Depo"),
            ("7\" Centralizer", "Centralizer", 450, "adet", "Batman Depo"),
            ("12 1/4\" TCI Matkap", "Matkap", 80, "adet", "Trakya Depo"),
            ("8 1/2\" PDC Matkap", "Matkap", 150, "adet", "Sırnak Depo"),
            ("OBM Çamuru", "Çamur Kimyasalı", 34000, "bbl", "Batman Depo"),
            ("KCl Polimer Çamuru", "Çamur Kimyasalı", 18000, "bbl", "Sırnak Depo"),
            ("Float Shoe (FS) 9 5/8\"", "Floating Ekipmanı", 220, "adet", "Batman Depo"),
        ]
        cur.executemany(
            "INSERT INTO malzeme (ad, kategori, stok_adet, birim, lokasyon) VALUES (?, ?, ?, ?, ?)",
            ornek_malzemeler,
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    veritabanini_kur()
    conn = baglanti_al()
    for row in conn.execute("SELECT * FROM malzeme"):
        print(dict(row))
    conn.close()