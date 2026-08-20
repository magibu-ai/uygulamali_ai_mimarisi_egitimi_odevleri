"""
Sondaj Malzeme Depo Yönetim Asistanı - Tool (Fonksiyon) Katmanı.

Model bu fonksiyonları HALÜSİNASYON İLE DEĞİL, gerçek veritabanı sorgularıyla
çağırır - her cevap gerçek 'malzeme'/'talep' tablosundaki veriye dayanır.
"""
from datetime import datetime
from db import baglanti_al, veritabanini_kur


# ------------------ TOOL 1: Stok sorgulama (OKUMA) ------------------

def get_stok_durumu(malzeme_adi: str) -> str:
    """Depodaki bir malzemenin güncel stok durumunu sorgular.

    Args:
        malzeme_adi: Aranacak malzeme adı ya da adının bir kısmı (örn. "9 5/8 casing",
                     "centralizer", "matkap"). Kısmi eşleşme yapılır.

    Returns:
        Eşleşen malzeme(ler)in stok bilgisi, ya da hiç eşleşme yoksa açık bir uyarı.
    """
    def normalize(metin: str) -> str:
        # İnç işareti (") ve fazla boşlukları yok sayarak karşılaştırma yapıyoruz -
        # kullanıcı/model "9 5/8 casing" yazabilir, veritabanında '9 5/8" Casing' kayıtlı.
        return metin.replace('"', '').replace("''", '').strip().lower()

    hedef = normalize(malzeme_adi)

    conn = baglanti_al()
    try:
        tum_satirlar = conn.execute(
            "SELECT ad, kategori, stok_adet, birim, lokasyon FROM malzeme"
        ).fetchall()
    finally:
        conn.close()

    satirlar = [s for s in tum_satirlar if hedef in normalize(s["ad"]) or hedef in normalize(s["kategori"])]

    if not satirlar:
        return f"'{malzeme_adi}' için depoda eşleşen bir malzeme bulunamadı."

    sonuc = [f"'{malzeme_adi}' için {len(satirlar)} sonuç bulundu:"]
    for s in satirlar:
        sonuc.append(
            f"- Tam Ad: '{s['ad']}' | Kategori: {s['kategori']} | "
            f"Stok: {s['stok_adet']} {s['birim']} | Lokasyon: {s['lokasyon']}"
        )
    return "\n".join(sonuc)


# ------------------ TOOL 2: Malzeme talebi oluşturma (YAZMA) ------------------

def malzeme_talep_olustur(malzeme_adi: str, adet: int, kuyu_adi: str) -> str:
    """Belirtilen malzeme için yeni bir talep oluşturur ve stoktan düşer.

    Args:
        malzeme_adi: Talep edilecek malzemenin adı (tam ya da yaklaşık - tırnak/boşluk
                     farkları otomatik tolere edilir, ama tek bir kesin sonuca ulaşmalı).
        adet: Talep edilen miktar (pozitif tam sayı).
        kuyu_adi: Malzemenin gönderileceği kuyu adı (örn. "SABUN-12").

    Returns:
        Talep başarıyla oluşturulduysa talep ID'si ve özet; stok yetersizse, malzeme
        bulunamazsa ya da birden fazla eşleşme varsa açık bir hata/uyarı mesajı.
    """
    if adet <= 0:
        return "Hata: Talep edilen adet pozitif bir sayı olmalıdır."

    def normalize(metin: str) -> str:
        return metin.replace('"', '').replace("''", '').strip().lower()

    hedef = normalize(malzeme_adi)

    conn = baglanti_al()
    try:
        tum_satirlar = conn.execute("SELECT id, ad, stok_adet, birim FROM malzeme").fetchall()
        eslesenler = [
            m for m in tum_satirlar
            if hedef in normalize(m["ad"]) or normalize(m["ad"]) in hedef
        ]

        if not eslesenler:
            return (f"Hata: '{malzeme_adi}' adında bir malzeme depoda kayıtlı değil. "
                     f"Önce get_stok_durumu ile tam malzeme adını doğrulayın.")

        if len(eslesenler) > 1:
            secenekler = ", ".join(f"'{m['ad']}'" for m in eslesenler)
            return (f"Hata: '{malzeme_adi}' ifadesi birden fazla malzemeyle eşleşiyor "
                     f"({secenekler}). Lütfen tam olarak hangisini kastettiğinizi belirtin.")

        malzeme = eslesenler[0]

        if malzeme["stok_adet"] < adet:
            return (f"Hata: Yetersiz stok. '{malzeme['ad']}' için depoda sadece "
                     f"{malzeme['stok_adet']} {malzeme['birim']} var, {adet} talep edildi.")

        cur = conn.cursor()
        cur.execute(
            "UPDATE malzeme SET stok_adet = stok_adet - ? WHERE id = ?",
            (adet, malzeme["id"]),
        )
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
        cur.execute(
            "INSERT INTO talep (malzeme_id, malzeme_adi, adet, kuyu_adi, durum, tarih) "
            "VALUES (?, ?, ?, ?, 'Onay Bekliyor', ?)",
            (malzeme["id"], malzeme["ad"], adet, kuyu_adi, tarih),
        )
        talep_id = cur.lastrowid
        conn.commit()

        return (f"Talep oluşturuldu (Talep ID: {talep_id}). {adet} {malzeme['birim']} "
                 f"'{malzeme['ad']}', {kuyu_adi} kuyusu için talep edildi. Durum: Onay Bekliyor. "
                 f"Kalan stok: {malzeme['stok_adet'] - adet} {malzeme['birim']}.")
    finally:
        conn.close()


# ------------------ TOOL 3: Talep durumu sorgulama (OKUMA) ------------------

def talep_durumu_sorgula(talep_id: int = None, kuyu_adi: str = None) -> str:
    """Malzeme taleplerini sorgular. Üç kullanım şekli vardır:
      1) talep_id verilirse -> sadece o talebin detayını döner.
      2) sadece kuyu_adi verilirse -> o kuyuya ait TÜM talepleri (geçmiş + onay
         bekleyenler) listeler.
      3) hiçbiri verilmezse -> sistemdeki TÜM talepleri (geçmiş + güncel onay
         bekleyenler) listeler, onay bekleyen sayısını özetler.

    Args:
        talep_id: (opsiyonel) Belirli bir talebin ID numarası.
        kuyu_adi: (opsiyonel) Taleplerin filtreleneceği kuyu adı (örn. "SABUN-12").

    Returns:
        Sorgulanan talep(ler)in detayları, ya da hiç sonuç yoksa açık bir uyarı.
    """
    conn = baglanti_al()
    try:
        if talep_id is not None:
            talep = conn.execute("SELECT * FROM talep WHERE id = ?", (talep_id,)).fetchone()
            if talep is None:
                return f"Talep ID {talep_id} bulunamadı."
            return (f"Talep ID {talep['id']}: {talep['adet']} adet '{talep['malzeme_adi']}', "
                     f"{talep['kuyu_adi']} kuyusu için ({talep['tarih']}). Durum: {talep['durum']}.")

        if kuyu_adi is not None:
            satirlar = conn.execute(
                "SELECT * FROM talep WHERE kuyu_adi = ? ORDER BY id DESC", (kuyu_adi,)
            ).fetchall()
            if not satirlar:
                return f"'{kuyu_adi}' kuyusu için kayıtlı hiç talep bulunamadı."
            baslik = f"'{kuyu_adi}' kuyusu için toplam {len(satirlar)} talep:"
        else:
            satirlar = conn.execute("SELECT * FROM talep ORDER BY id DESC").fetchall()
            if not satirlar:
                return "Sistemde kayıtlı hiç talep bulunmuyor."
            baslik = f"Toplam {len(satirlar)} talep kayıtlı:"

        bekleyen_sayisi = sum(1 for t in satirlar if t["durum"] == "Onay Bekliyor")
        satirlar_metni = [baslik, f"({bekleyen_sayisi} tanesi onay bekliyor)\n"]
        for t in satirlar:
            isaret = "⏳" if t["durum"] == "Onay Bekliyor" else "✓"
            satirlar_metni.append(
                f"{isaret} Talep ID {t['id']}: {t['adet']} adet '{t['malzeme_adi']}', "
                f"{t['kuyu_adi']} kuyusu için ({t['tarih']}). Durum: {t['durum']}."
            )
        return "\n".join(satirlar_metni)
    finally:
        conn.close()


# ------------------ DEBUG: Veritabanının tam içeriğini gösterme ------------------

def veritabani_durumunu_goster() -> str:
    """Doğrulama/hata ayıklama amaçlı: 'malzeme' ve 'talep' tablolarının GÜNCEL,
    ham içeriğini olduğu gibi döner. Bu bir tool DEĞİLDİR, modele sunulmaz -
    sadece Gradio arayüzündeki 'Veritabanı Durumu' sekmesinden elle tetiklenir."""
    conn = baglanti_al()
    try:
        satirlar = ["=== MALZEME TABLOSU ===\n"]
        for m in conn.execute("SELECT * FROM malzeme ORDER BY id"):
            satirlar.append(
                f"ID {m['id']}: {m['ad']} ({m['kategori']}) - "
                f"{m['stok_adet']} {m['birim']} - {m['lokasyon']}"
            )

        satirlar.append("\n=== TALEP TABLOSU ===\n")
        talepler = conn.execute("SELECT * FROM talep ORDER BY id").fetchall()
        if not talepler:
            satirlar.append("(Henüz hiç talep oluşturulmamış.)")
        else:
            for t in talepler:
                satirlar.append(
                    f"ID {t['id']}: {t['adet']} adet '{t['malzeme_adi']}' - "
                    f"{t['kuyu_adi']} - {t['tarih']} - Durum: {t['durum']}"
                )

        return "\n".join(satirlar)
    finally:
        conn.close()

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_stok_durumu",
            "description": (
                "Search the warehouse inventory for a material/equipment by name or "
                "category and return its current stock quantity and location. Use this "
                "whenever the user asks if an item is in stock, how much of something "
                "is available, or wants to browse inventory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "malzeme_adi": {
                        "type": "string",
                        "description": "Material name or partial name/category to search for, e.g. '9 5/8 casing', 'centralizer'.",
                    },
                },
                "required": ["malzeme_adi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "malzeme_talep_olustur",
            "description": (
                "Create a new material request for a specific well, deducting the "
                "requested quantity from warehouse stock. Use this when the user asks "
                "to order, request, or send material to a well. The exact material name "
                "must match the inventory (verify with get_stok_durumu first if unsure)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "malzeme_adi": {"type": "string", "description": "Exact material name as stored in inventory."},
                    "adet": {"type": "integer", "description": "Quantity to request."},
                    "kuyu_adi": {"type": "string", "description": "Name of the well the material is for, e.g. 'SABUN-12'."},
                },
                "required": ["malzeme_adi", "adet", "kuyu_adi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "talep_durumu_sorgula",
            "description": (
                "Look up material request(s). If a request ID is given, returns that "
                "single request's status. If a well name is given (without an ID), "
                "returns ALL requests for that well. If neither is given, returns ALL "
                "requests in the system, including how many are currently pending "
                "approval. Use this when the user asks about request status, wants to "
                "see request history for a well, or wants to see all pending requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "talep_id": {"type": "integer", "description": "(optional) Specific request ID to look up."},
                    "kuyu_adi": {"type": "string", "description": "(optional) Filter requests by well name, e.g. 'SABUN-12'."},
                },
                "required": [],
            },
        },
    },
]

ARAC_SOZLUGU = {
    "get_stok_durumu": get_stok_durumu,
    "malzeme_talep_olustur": malzeme_talep_olustur,
    "talep_durumu_sorgula": talep_durumu_sorgula,
}


if __name__ == "__main__":
    veritabanini_kur()
    print(get_stok_durumu("casing"))
    print()
    print(malzeme_talep_olustur("9 5/8\" Casing", 10, "SABUN-12"))
    print()
    print(talep_durumu_sorgula(1))
    print()
    print(get_stok_durumu("9 5/8\" Casing"))