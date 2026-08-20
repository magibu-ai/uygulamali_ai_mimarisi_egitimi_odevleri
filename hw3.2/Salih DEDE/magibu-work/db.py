"""SQLite üzerinde THY uçuş kataloğu ve bilet kayıtları.

Uçuşlar sabit bir kaynak veri (gerçek THY API'si değil, mock kayıt seti).
Bilet alma DB'ye satır yazar ve koltuk sayısını düşer — gerçek okuma/yazma burada olur.
"""

import random
import sqlite3
import uuid
from datetime import date, timedelta
from pathlib import Path

DB_YOLU = Path(__file__).parent / "thy.db"

# Uçuşlar İstanbul'dan kalkar; hub şehir olduğu için kendisi varış listesinde yok.
KALKIS_SEHRI = "İstanbul"

# Havalimanı olan TR illeri -> IATA kodu (Türkiye tek saat diliminde: Europe/Istanbul)
SEHIRLER = {
    "Adana": "ADA", "Adıyaman": "ADF", "Afyonkarahisar": "AFY", "Ağrı": "AJI",
    "Amasya": "MZH", "Antalya": "AYT", "Balıkesir": "EDO", "Batman": "BAL",
    "Bingöl": "BGG", "Bursa": "YEI", "Çanakkale": "CKZ", "Denizli": "DNZ",
    "Diyarbakır": "DIY", "Elazığ": "EZS", "Erzincan": "ERC", "Erzurum": "ERZ",
    "Eskişehir": "AOE", "Gaziantep": "GZT", "Giresun": "OGU", "Hatay": "HTY",
    "Iğdır": "IGD", "Isparta": "ISE", "İzmir": "ADB", "Kahramanmaraş": "KCM",
    "Kars": "KSY", "Kastamonu": "KFS", "Kayseri": "ASR", "Kocaeli": "KCO",
    "Konya": "KYA", "Malatya": "MLX", "Mardin": "MQM", "Muğla-Bodrum": "BJV",
    "Muğla-Dalaman": "DLM", "Muş": "MSR", "Nevşehir": "NAV", "Ordu": "OGU",
    "Rize": "RZV", "Samsun": "SZF", "Şanlıurfa": "GNY", "Siirt": "SXZ",
    "Sinop": "NOP", "Sivas": "VAS", "Tekirdağ": "TEQ", "Tokat": "TJK",
    "Trabzon": "TZX", "Uşak": "USQ", "Van": "VAN", "Zonguldak": "ONQ",
}
SAAT_DILIMI = "Europe/Istanbul"

_RASTGELE = random.Random(42)  # sabit seed: her kurulumda ayni "rastgele" veri


def _ucus_tohumu_uret():
    tohum = []
    for sehir in SEHIRLER:
        for _ in range(_RASTGELE.randint(1, 3)):
            gun_sonra = _RASTGELE.randint(1, 30)  # 1 ay icinde, her zaman kullanilabilir
            tarih = (date.today() + timedelta(days=gun_sonra)).isoformat()
            saat = f"{_RASTGELE.randint(6, 22):02d}:{_RASTGELE.choice(['00', '15', '30', '45'])}"
            sefer_no = f"TK{_RASTGELE.randint(100, 1999)}"
            fiyat = _RASTGELE.randint(14, 65) * 50  # 700 - 3250 TRY, 50'nin katlari
            koltuk = _RASTGELE.randint(0, 9)  # bos koltuk; 0 = dolu ucus
            tohum.append((sehir, sefer_no, tarih, saat, fiyat, koltuk))
    return tohum


def baglan():
    conn = sqlite3.connect(DB_YOLU)
    conn.row_factory = sqlite3.Row
    return conn


def kur():
    """Tablolari olusturur ve bos ise ucus tohumunu yazar (idempotent)."""
    conn = baglan()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ucuslar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sehir TEXT NOT NULL,
            kod TEXT NOT NULL,
            kalkis TEXT NOT NULL,
            sefer_no TEXT NOT NULL,
            tarih TEXT NOT NULL,
            saat TEXT NOT NULL,
            fiyat_try REAL NOT NULL,
            koltuk INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS biletler (
            pnr TEXT PRIMARY KEY,
            ucus_id INTEGER NOT NULL,
            fiyat_try REAL NOT NULL,
            olusturma_zamani TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (ucus_id) REFERENCES ucuslar(id)
        )"""
    )
    if conn.execute("SELECT COUNT(*) FROM ucuslar").fetchone()[0] == 0:
        for sehir, sefer_no, tarih, saat, fiyat, koltuk in _ucus_tohumu_uret():
            conn.execute(
                "INSERT INTO ucuslar (sehir, kod, kalkis, sefer_no, tarih, saat, fiyat_try, koltuk) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sehir, SEHIRLER[sehir], KALKIS_SEHRI, sefer_no, tarih, saat, fiyat, koltuk),
            )
    conn.commit()
    conn.close()


def ucus_ara(sehir):
    """Bir sehre giden, kontenjani dolmamis ucuslari dondurur."""
    conn = baglan()
    satirlar = conn.execute(
        "SELECT * FROM ucuslar WHERE sehir LIKE ? AND koltuk > 0 ORDER BY tarih, saat",
        (f"%{sehir.strip()}%",),
    ).fetchall()
    conn.close()
    return [dict(satir) for satir in satirlar]


def ucus_getir(ucus_id):
    conn = baglan()
    satir = conn.execute("SELECT * FROM ucuslar WHERE id = ?", (ucus_id,)).fetchone()
    conn.close()
    return dict(satir) if satir else None


def bilet_yaz(ucus_id):
    """Koltugu bir azaltir ve yeni bir PNR ile bilet kaydi olusturur (atomik)."""
    conn = baglan()
    try:
        ucus = conn.execute("SELECT * FROM ucuslar WHERE id = ?", (ucus_id,)).fetchone()
        if ucus is None:
            return None
        if ucus["koltuk"] <= 0:
            return {"dolu": True}

        pnr = uuid.uuid4().hex[:6].upper()
        conn.execute("UPDATE ucuslar SET koltuk = koltuk - 1 WHERE id = ?", (ucus_id,))
        conn.execute(
            "INSERT INTO biletler (pnr, ucus_id, fiyat_try) VALUES (?, ?, ?)",
            (pnr, ucus_id, ucus["fiyat_try"]),
        )
        conn.commit()
        return {"pnr": pnr, "ucus": dict(ucus)}
    finally:
        conn.close()
