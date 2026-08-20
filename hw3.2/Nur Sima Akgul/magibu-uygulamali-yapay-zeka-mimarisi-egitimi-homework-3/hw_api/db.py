"""
Kutuphane veritabani katmani (SQLite).
- Kitap envanteri, odunc kayitlari.
- Hem okuma (arama, listeleme) hem yazma (odunc, iade) fonksiyonlari.
Tum tool fonksiyonlari bu katmani kullanir; boylece cevaplar daima gercek
veriye dayanir (halusinasyon engellenir).
"""
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("KUTUPHANE_DB", "kutuphane.db")
ODUNC_GUN = 14  # odunc suresi: 2 hafta


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed=True):
    """Tablolari olusturur ve (bosssa) ornek kitaplarla doldurur."""
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kitaplar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            yazar TEXT NOT NULL,
            tur TEXT NOT NULL,
            sayfa INTEGER,
            koken TEXT,               -- 'yerli' / 'yabanci'
            durum TEXT DEFAULT 'bosta',   -- 'bosta' / 'oduncte'
            odunc_alan TEXT,          -- okuyucu adi (oduncteyse)
            odunc_tarih TEXT,         -- odunc alinma tarihi (ISO)
            teslim_tarih TEXT         -- en gec teslim tarihi (ISO)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS gecmis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kitap_id INTEGER,
            okuyucu TEXT,
            odunc_tarih TEXT,
            iade_tarih TEXT,
            durum_notu TEXT           -- 'erken', 'zamaninda', 'gec'
        )
    """)
    conn.commit()

    if seed:
        c.execute("SELECT COUNT(*) AS n FROM kitaplar")
        if c.fetchone()["n"] == 0:
            for k in ORNEK_KITAPLAR:
                c.execute(
                    "INSERT INTO kitaplar (baslik,yazar,tur,sayfa,koken,durum) VALUES (?,?,?,?,?,?)",
                    (k[0], k[1], k[2], k[3], k[4], "bosta"),
                )
            conn.commit()
    conn.close()


# (baslik, yazar, tur, sayfa, koken)
ORNEK_KITAPLAR = [
    # Polisiye
    ("Kürk Mantolu Madonna", "Sabahattin Ali", "roman", 160, "yerli"),
    ("Şu Çılgın Türkler", "Turgut Özakman", "tarih", 720, "yerli"),
    ("Benim Adım Kırmızı", "Orhan Pamuk", "roman", 472, "yerli"),
    ("Tutunamayanlar", "Oğuz Atay", "roman", 724, "yerli"),
    ("İnce Memed", "Yaşar Kemal", "roman", 456, "yerli"),
    ("Çalıkuşu", "Reşat Nuri Güntekin", "roman", 408, "yerli"),
    ("Aşk", "Elif Şafak", "roman", 420, "yerli"),
    ("Serenad", "Zülfü Livaneli", "roman", 480, "yerli"),
    ("Cinai Meseleler", "Ahmet Ümit", "polisiye", 336, "yerli"),
    ("Beyoğlu Rapsodisi", "Ahmet Ümit", "polisiye", 400, "yerli"),
    ("İstanbul Hatırası", "Ahmet Ümit", "polisiye", 528, "yerli"),
    ("Sis ve Gece", "Ahmet Ümit", "polisiye", 320, "yerli"),
    ("Şeytan Ayrıntıda Gizlidir", "Ahmet Ümit", "polisiye", 280, "yerli"),
    # Yabanci polisiye
    ("Cinayet Alfabesi", "Agatha Christie", "polisiye", 256, "yabanci"),
    ("Doğu Ekspresinde Cinayet", "Agatha Christie", "polisiye", 288, "yabanci"),
    ("On Küçük Zenci", "Agatha Christie", "polisiye", 264, "yabanci"),
    ("Sherlock Holmes: Kızıl Dosya", "Arthur Conan Doyle", "polisiye", 224, "yabanci"),
    ("Baskerville'lerin Köpeği", "Arthur Conan Doyle", "polisiye", 256, "yabanci"),
    ("Ejderha Dövmeli Kız", "Stieg Larsson", "polisiye", 640, "yabanci"),
    ("Gone Girl", "Gillian Flynn", "polisiye", 512, "yabanci"),
    # Bilim kurgu
    ("Dune", "Frank Herbert", "bilim kurgu", 688, "yabanci"),
    ("1984", "George Orwell", "bilim kurgu", 352, "yabanci"),
    ("Fahrenheit 451", "Ray Bradbury", "bilim kurgu", 256, "yabanci"),
    ("Ben, Robot", "Isaac Asimov", "bilim kurgu", 320, "yabanci"),
    ("Vakıf", "Isaac Asimov", "bilim kurgu", 296, "yabanci"),
    ("Cesur Yeni Dünya", "Aldous Huxley", "bilim kurgu", 288, "yabanci"),
    ("Marslı", "Andy Weir", "bilim kurgu", 448, "yabanci"),
    # Klasik
    ("Suç ve Ceza", "Dostoyevski", "klasik", 687, "yabanci"),
    ("Karamazov Kardeşler", "Dostoyevski", "klasik", 1024, "yabanci"),
    ("Sefiller", "Victor Hugo", "klasik", 1463, "yabanci"),
    ("Savaş ve Barış", "Tolstoy", "klasik", 1392, "yabanci"),
    ("Anna Karenina", "Tolstoy", "klasik", 864, "yabanci"),
    ("Bülbülü Öldürmek", "Harper Lee", "klasik", 384, "yabanci"),
    ("Gurur ve Önyargı", "Jane Austen", "klasik", 432, "yabanci"),
    ("Sineklerin Tanrısı", "William Golding", "klasik", 256, "yabanci"),
    # Cocuk / genclik
    ("Şeker Portakalı", "José Mauro de Vasconcelos", "çocuk", 182, "yabanci"),
    ("Küçük Prens", "Antoine de Saint-Exupéry", "çocuk", 96, "yabanci"),
    ("Momo", "Michael Ende", "çocuk", 288, "yabanci"),
    ("Bitmeyen Öykü", "Michael Ende", "çocuk", 448, "yabanci"),
    ("Charlie'nin Çikolata Fabrikası", "Roald Dahl", "çocuk", 192, "yabanci"),
    ("Matilda", "Roald Dahl", "çocuk", 240, "yabanci"),
    ("Pal Sokağı Çocukları", "Ferenc Molnár", "çocuk", 224, "yabanci"),
    # Kisisel gelisim / bilim
    ("Sapiens", "Yuval Noah Harari", "bilim", 512, "yabanci"),
    ("Homo Deus", "Yuval Noah Harari", "bilim", 496, "yabanci"),
    ("Kozmos", "Carl Sagan", "bilim", 432, "yabanci"),
    ("Zamanın Kısa Tarihi", "Stephen Hawking", "bilim", 256, "yabanci"),
    ("Hayvanlardan Tanrılara", "Yuval Noah Harari", "bilim", 512, "yabanci"),
    # Fantastik
    ("Yüzüklerin Efendisi", "J.R.R. Tolkien", "fantastik", 1178, "yabanci"),
    ("Hobbit", "J.R.R. Tolkien", "fantastik", 320, "yabanci"),
    ("Harry Potter ve Felsefe Taşı", "J.K. Rowling", "fantastik", 276, "yabanci"),
    ("Buz ve Ateşin Şarkısı", "George R.R. Martin", "fantastik", 704, "yabanci"),
]


# ---------- OKUMA ----------
def kitap_ara_db(sorgu):
    """Baslik ya da yazarda gecen kelimeye gore kitaplari arar."""
    conn = _conn()
    like = f"%{sorgu.strip()}%"
    rows = conn.execute(
        "SELECT * FROM kitaplar WHERE baslik LIKE ? OR yazar LIKE ? ORDER BY baslik",
        (like, like),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def kitap_getir(kitap_id):
    conn = _conn()
    r = conn.execute("SELECT * FROM kitaplar WHERE id=?", (kitap_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def oneri_db(tur=None, koken=None, max_sayfa=None, min_sayfa=None, sadece_bosta=True):
    """Turku ve filtrelere gore DB'den kitap onerir."""
    conn = _conn()
    q = "SELECT * FROM kitaplar WHERE 1=1"
    p = []
    if tur:
        q += " AND tur LIKE ?"; p.append(f"%{tur.strip()}%")
    if koken:
        q += " AND koken = ?"; p.append(koken.strip().lower())
    if max_sayfa:
        q += " AND sayfa <= ?"; p.append(int(max_sayfa))
    if min_sayfa:
        q += " AND sayfa >= ?"; p.append(int(min_sayfa))
    if sadece_bosta:
        q += " AND durum = 'bosta'"
    q += " ORDER BY sayfa"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- YAZMA ----------
def odunc_al_db(kitap_id, okuyucu):
    """Kitabi odunc verir: durumu gunceller, 2 hafta teslim tarihi yazar."""
    conn = _conn()
    r = conn.execute("SELECT * FROM kitaplar WHERE id=?", (kitap_id,)).fetchone()
    if not r:
        conn.close(); return {"ok": False, "hata": "Kitap bulunamadi."}
    if r["durum"] == "oduncte":
        conn.close(); return {"ok": False, "hata": "Kitap su an oduncte.",
                              "teslim_tarih": r["teslim_tarih"]}
    bugun = datetime.now()
    teslim = bugun + timedelta(days=ODUNC_GUN)
    conn.execute(
        "UPDATE kitaplar SET durum='oduncte', odunc_alan=?, odunc_tarih=?, teslim_tarih=? WHERE id=?",
        (okuyucu, bugun.date().isoformat(), teslim.date().isoformat(), kitap_id),
    )
    conn.commit(); conn.close()
    return {"ok": True, "teslim_tarih": teslim.date().isoformat(),
            "odunc_tarih": bugun.date().isoformat()}


def iade_et_db(kitap_id):
    """Kitabi iade alir: erken/zamaninda/gec notu duser, bosa cikarir."""
    conn = _conn()
    r = conn.execute("SELECT * FROM kitaplar WHERE id=?", (kitap_id,)).fetchone()
    if not r:
        conn.close(); return {"ok": False, "hata": "Kitap bulunamadi."}
    if r["durum"] != "oduncte":
        conn.close(); return {"ok": False, "hata": "Bu kitap zaten kutuphanede (bosta)."}
    bugun = datetime.now().date()
    teslim = datetime.fromisoformat(r["teslim_tarih"]).date() if r["teslim_tarih"] else bugun
    if bugun < teslim:
        notu = "erken"
    elif bugun == teslim:
        notu = "zamaninda"
    else:
        notu = "gec"
    conn.execute(
        "INSERT INTO gecmis (kitap_id, okuyucu, odunc_tarih, iade_tarih, durum_notu) VALUES (?,?,?,?,?)",
        (kitap_id, r["odunc_alan"], r["odunc_tarih"], bugun.isoformat(), notu),
    )
    conn.execute(
        "UPDATE kitaplar SET durum='bosta', odunc_alan=NULL, odunc_tarih=NULL, teslim_tarih=NULL WHERE id=?",
        (kitap_id,),
    )
    conn.commit(); conn.close()
    gun_farki = (teslim - bugun).days
    return {"ok": True, "durum_notu": notu, "teslim_tarih": teslim.isoformat(),
            "gun_farki": gun_farki}


if __name__ == "__main__":
    init_db()
    print("DB hazir. Toplam kitap:", len(kitap_ara_db("")))
