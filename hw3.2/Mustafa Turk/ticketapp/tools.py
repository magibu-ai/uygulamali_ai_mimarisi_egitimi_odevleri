"""tools.py — Araç (tool) katmanı.

Bu modül, veritabanı işlemlerini modelin çağırabileceği araçlara dönüştürür.
İki bileşeni vardır:

    1. Araç fonksiyonları — DB katmanını çağırır, sonucu JSON'a uygun
       sözlük olarak döndürür.
    2. TOOLS listesi — modele araçları tanıtan JSON şemaları.

Neden ayrı bir katman?
    database.py saf veritabanı işlemleri içerir ve (bool, dict) döndürür.
    Model ise düz JSON bekler ve hata durumunda ne yapacağını anlatan
    yönlendirici mesajlara ihtiyaç duyar. Bu modül ikisi arasında köprüdür;
    böylece veritabanı mantığı ile model arayüzü birbirinden bağımsız kalır.

Halüsinasyon engelleme:
    Araçlar asla veri uydurmaz. Sonuç bulunamazsa boş liste veya açık bir
    hata mesajı döner. Model bu çıktılara dayanmak zorundadır.
"""

import database as db


# ---------------------------------------------------------------------------
# ARAÇ 1 — Sefer arama (okuma)
# ---------------------------------------------------------------------------
def search_flights(kalkis=None, varis=None, tarih=None):
    """Verilen kriterlere uyan, boş koltuğu olan seferleri döndürür."""
    try:
        seferler = db.sefer_ara(kalkis=kalkis, varis=varis, tarih=tarih, limit=10)
    except Exception as e:
        return {"hata": f"Arama sırasında hata oluştu: {e}"}

    if not seferler:
        # Boş sonuç bir hata değildir; modelin bunu doğru yorumlaması için
        # açıkça belirtilir. Aksi hâlde model uygun sefer uydurabilir.
        return {
            "sonuc_sayisi": 0,
            "seferler": [],
            "bilgi": "Bu kriterlere uyan sefer bulunamadı. "
                     "Kullanıcıya sefer olmadığını bildir; sefer uydurma.",
        }

    return {
        "sonuc_sayisi": len(seferler),
        "seferler": [
            {
                "sefer_id": s["id"],            # book_ticket bu id'yi kullanır
                "ucus_kodu": s["ucus_kodu"],
                "firma": s["firma"],
                "kalkis": s["kalkis"],
                "varis": s["varis"],
                "tarih": s["tarih"],
                "kalkis_saati": s["kalkis_saati"],
                "varis_saati": s["varis_saati"],
                "fiyat_tl": s["fiyat"],
                "bos_koltuk": s["bos_koltuk"],
            }
            for s in seferler
        ],
    }


# ---------------------------------------------------------------------------
# ARAÇ 2 — Bilet rezervasyonu (YAZMA)
# ---------------------------------------------------------------------------
def book_ticket(sefer_id, yolcu_adi, koltuk_sayisi=1, kullanici_onayi=False):
    """Rezervasyon oluşturur ve seferin boş koltuk sayısını düşürür.

    kullanici_onayi parametresi, modelin yolcu adını uydurmasını engeller.
    Model önce kullanıcıya özeti gösterip onay almak zorundadır; onay
    alınmadan çağrı reddedilir. Sistem mesajındaki talimat tek başına
    yeterli olmamıştır: model, kullanıcı ad vermediğinde ad uydurmuştur.
    Bu nedenle denetim koda taşınmıştır.
    """
    # --- Girdi doğrulaması ---
    # Model sayı yerine metin gönderebilir ("2" gibi); güvenli biçimde çevir.
    try:
        sefer_id = int(sefer_id)
        koltuk_sayisi = int(koltuk_sayisi)
    except (TypeError, ValueError):
        return {"hata": "sefer_id ve koltuk_sayisi sayı olmalıdır."}

    if koltuk_sayisi < 1:
        return {"hata": "Koltuk sayısı en az 1 olmalıdır."}
    if koltuk_sayisi > 9:
        return {"hata": "Tek rezervasyonda en fazla 9 koltuk alınabilir."}

    yolcu_adi = (yolcu_adi or "").strip()
    if len(yolcu_adi) < 3:
        return {
            "basarili": False,
            "hata": "Yolcu adı eksik veya geçersiz.",
            "oneri": "Kullanıcıya yolcu adını sor. Ad uydurma.",
        }

    # --- Onay denetimi ---
    # Model bu aracı ilk kez çağırdığında kullanici_onayi=False olur ve
    # istek reddedilir. Model, kullanıcıya özeti gösterip onay aldıktan
    # sonra kullanici_onayi=True ile tekrar çağırmalıdır.
    if not kullanici_onayi:
        sefer = db.sefer_getir(sefer_id)
        if sefer is None:
            return {
                "basarili": False,
                "hata": f"{sefer_id} numaralı sefer bulunamadı.",
                "oneri": "Geçerli bir sefer_id için önce search_flights aracını kullan.",
            }
        return {
            "basarili": False,
            "onay_bekleniyor": True,
            "ozet": {
                "ucus_kodu": sefer["ucus_kodu"],
                "firma": sefer["firma"],
                "guzergah": f"{sefer['kalkis']} - {sefer['varis']}",
                "tarih": sefer["tarih"],
                "kalkis_saati": sefer["kalkis_saati"],
                "yolcu_adi": yolcu_adi,
                "koltuk_sayisi": koltuk_sayisi,
                "toplam_fiyat_tl": round(sefer["fiyat"] * koltuk_sayisi, 2),
            },
            "oneri": "Bu özeti kullanıcıya göster ve onay iste. Yolcu adının "
                     "kullanıcı tarafından verildiğinden emin ol; verilmediyse "
                     "önce adı sor. Kullanıcı açıkça onayladıktan sonra bu aracı "
                     "kullanici_onayi=true ile tekrar çağır.",
        }

    # --- Veritabanı işlemi (transaction içinde) ---
    basarili, sonuc = db.rezervasyon_olustur(sefer_id, yolcu_adi, koltuk_sayisi)

    if not basarili:
        # Hata mesajına yönlendirme eklenir: model ne yapacağını bilsin.
        return {
            "basarili": False,
            "hata": sonuc.get("hata", "Rezervasyon oluşturulamadı."),
            "oneri": "Geçerli bir sefer_id için önce search_flights aracını kullan.",
        }

    return {"basarili": True, "rezervasyon": sonuc}


# ---------------------------------------------------------------------------
# ARAÇ 3 — Rezervasyon sorgulama (okuma)
# ---------------------------------------------------------------------------
def check_booking(pnr):
    """PNR kodu ile rezervasyon bilgilerini döndürür."""
    pnr = (pnr or "").strip().upper()
    if len(pnr) != 6:
        return {"hata": "PNR kodu 6 karakter olmalıdır."}

    kayit = db.rezervasyon_getir(pnr)
    if kayit is None:
        return {
            "bulundu": False,
            "bilgi": f"{pnr} kodlu rezervasyon bulunamadı. "
                     "Kullanıcıya bulunamadığını bildir; bilgi uydurma.",
        }

    return {
        "bulundu": True,
        "rezervasyon": {
            "pnr": kayit["pnr"],
            "yolcu_adi": kayit["yolcu_adi"],
            "ucus_kodu": kayit["ucus_kodu"],
            "firma": kayit["firma"],
            "kalkis": kayit["kalkis"],
            "varis": kayit["varis"],
            "tarih": kayit["tarih"],
            "kalkis_saati": kayit["kalkis_saati"],
            "varis_saati": kayit["varis_saati"],
            "koltuk_sayisi": kayit["koltuk_sayisi"],
            "toplam_fiyat_tl": kayit["toplam_fiyat"],
            "durum": kayit["durum"],
            "olusturma_tarihi": kayit["olusturma_tarihi"],
        },
    }


# ---------------------------------------------------------------------------
# Araç şemaları (modele araçları tanıtır)
# ---------------------------------------------------------------------------
# description alanları modelin aracı DOĞRU KULLANMASINI sağlar; bu nedenle
# yalnızca ne yaptığını değil, ne zaman kullanılacağını da anlatır.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "Uçuş seferlerini arar ve boş koltuğu olan seferleri listeler. "
                "Kullanıcı bilet aramak istediğinde ilk bu araç kullanılmalıdır. "
                "Rezervasyon yapmadan önce sefer_id öğrenmek için gereklidir. "
                "Tüm parametreler isteğe bağlıdır; verilenler filtre olarak uygulanır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kalkis": {
                        "type": "string",
                        "description": "Kalkış şehri, örneğin 'İstanbul'.",
                    },
                    "varis": {
                        "type": "string",
                        "description": "Varış şehri, örneğin 'Ankara'.",
                    },
                    "tarih": {
                        "type": "string",
                        "description": "Uçuş tarihi, YYYY-AA-GG biçiminde "
                                       "(örneğin '2026-08-15').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_ticket",
            "description": (
                "Belirtilen sefer için bilet rezervasyonu oluşturur ve seferin "
                "boş koltuk sayısını düşürür. sefer_id mutlaka search_flights "
                "sonucundan alınmalıdır; tahmin edilmemelidir. "
                "ÖNEMLİ: yolcu_adi kullanıcı tarafından açıkça belirtilmelidir; "
                "asla uydurulmamalı veya varsayılmamalıdır. Kullanıcı ad "
                "vermediyse önce sorulmalıdır. "
                "Bu araç iki aşamalı çalışır: ilk çağrıda kullanici_onayi "
                "verilmezse rezervasyon özeti döner; bu özet kullanıcıya "
                "gösterilip onay alındıktan sonra araç kullanici_onayi=true "
                "ile tekrar çağrılmalıdır. İşlem başarılı olursa PNR kodu döner."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sefer_id": {
                        "type": "integer",
                        "description": "search_flights sonucundan alınan sefer kimliği.",
                    },
                    "yolcu_adi": {
                        "type": "string",
                        "description": "Yolcunun adı ve soyadı. Kullanıcının "
                                       "verdiği ad kullanılmalıdır; uydurulmamalıdır.",
                    },
                    "koltuk_sayisi": {
                        "type": "integer",
                        "description": "Rezerve edilecek koltuk sayısı (1-9). "
                                       "Belirtilmezse 1 kabul edilir.",
                    },
                    "kullanici_onayi": {
                        "type": "boolean",
                        "description": "Kullanıcı rezervasyon özetini görüp açıkça "
                                       "onayladıysa true. İlk çağrıda false "
                                       "bırakılmalıdır.",
                    },
                },
                "required": ["sefer_id", "yolcu_adi"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_booking",
            "description": (
                "PNR kodu ile mevcut bir rezervasyonun bilgilerini sorgular. "
                "Kullanıcı rezervasyonunu kontrol etmek istediğinde kullanılır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr": {
                        "type": "string",
                        "description": "6 karakterlik rezervasyon kodu, örneğin 'K7X2M9'.",
                    },
                },
                "required": ["pnr"],
            },
        },
    },
]

# Model bir araç çağırdığında adından fonksiyona ulaşmak için kullanılır.
ARACLAR = {
    "search_flights": search_flights,
    "book_ticket": book_ticket,
    "check_booking": check_booking,
}


def arac_calistir(ad, argumanlar):
    """Adı verilen aracı çalıştırır.

    Model var olmayan bir araç adı üretebilir; bu durumda hata döndürülür,
    istisna fırlatılmaz. Böylece döngü kesintiye uğramaz ve model kendini
    düzeltebilir.
    """
    fonksiyon = ARACLAR.get(ad)
    if fonksiyon is None:
        return {
            "hata": f"'{ad}' adlı bir araç yok.",
            "kullanilabilir_araclar": list(ARACLAR),
        }
    try:
        return fonksiyon(**argumanlar)
    except TypeError as e:
        return {"hata": f"Geçersiz parametreler: {e}"}
    except Exception as e:
        return {"hata": f"Araç çalıştırılamadı: {e}"}
