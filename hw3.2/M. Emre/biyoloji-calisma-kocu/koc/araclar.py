"""Araç (tool) katmanı.

Modelin çağırabileceği üç fonksiyon ve bunların JSON şemaları. Her fonksiyon
yalnızca veritabanından dönen gerçek veriyi döndürür; veri yoksa `bulundu: false`
der. Model bu alanı gördüğünde tanım uydurmamalıdır.

  terim_ara     -> OKUMA   (sözlük)
  quiz_getir    -> OKUMA   (soru bankası)
  cevap_kaydet  -> YAZMA   (quiz_sonuclari tablosuna INSERT)
"""

from __future__ import annotations

from . import db

SIKLAR = ["A", "B", "C", "D", "E"]

_baglanti = None


def baglanti():
    global _baglanti
    if _baglanti is None:
        _baglanti = db.baglan()
    return _baglanti


# --------------------------------------------------------------------------
# 1) OKUMA — sözlükten terim tanımı
# --------------------------------------------------------------------------


def terim_ara(terim: str) -> dict:
    kayitlar, kademe = db.terim_bul(baglanti(), terim)
    if not kayitlar:
        oneriler = db.terim_onerileri(baglanti(), terim)
        return {
            "bulundu": False,
            "aranan": terim,
            "arama_yontemi": "benzerlik taraması" if oneriler else kademe,
            "oneriler": oneriler,
            "not": (
                "Bu terim sözlükte yok. Tanım uydurma; kaynakta bulunmadığını söyle. "
                "Öneri listesi doluysa bunları kullanıcıya seçenek olarak sun."
            ),
        }
    return {
        "bulundu": True,
        "arama_yontemi": kademe,
        "sonuclar": [
            {
                "terim": k["terim"],
                "tanim": k["tanim"],
                "kitap_sayfasi": k["kitap_sayfasi"],
            }
            for k in kayitlar
        ],
    }


# --------------------------------------------------------------------------
# 2) OKUMA — soru bankasından soru
# --------------------------------------------------------------------------


def quiz_getir(konu: str = None, adet: int = 1) -> dict:
    sorular = db.soru_getir(baglanti(), konu=konu, adet=adet)
    if not sorular:
        oneriler = db.konu_onerileri(baglanti(), konu) if konu else []
        return {
            "bulundu": False,
            "konu": konu,
            "oneriler": oneriler,
            "not": (
                "Bu konuda soru bulunamadı. Soru UYDURMA, başka konudan soru da verme. "
                "Öneri listesi doluysa kullanıcıya 'şunlardan biri olabilir mi?' diye sor."
            ),
        }
    # Şıklar harflendirilerek verilir; doğru cevap BİLİNÇLİ OLARAK gönderilmez.
    return {
        "bulundu": True,
        "arama_yontemi": "kelime sınırı eşleşmesi" if konu else "rastgele seçim",
        "sorular": [
            {
                "soru_id": s["soru_id"],
                "soru": s["soru"],
                "secenekler": {SIKLAR[i]: m for i, m in enumerate(s["secenekler"])},
            }
            for s in sorular
        ],
    }


# --------------------------------------------------------------------------
# 3) YAZMA — cevabı değerlendir ve kaydet
# --------------------------------------------------------------------------


def cevap_kaydet(soru_id: int, cevap: str, ogrenci_id: str = "misafir") -> dict:
    dogru_index = db.soru_cevabi(baglanti(), int(soru_id))
    if dogru_index is None:
        return {"kaydedildi": False, "not": f"{soru_id} numaralı soru yok."}

    verilen = _cevabi_indexe_cevir(cevap)
    if verilen is None:
        return {"kaydedildi": False, "not": "Cevap A-E arası bir şık olmalı."}

    dogru_mu = verilen == dogru_index
    db.sonuc_kaydet(baglanti(), ogrenci_id, int(soru_id), verilen, dogru_mu)
    durum = db.ilerleme(baglanti(), ogrenci_id)

    return {
        "kaydedildi": True,
        "dogru_mu": dogru_mu,
        "verilen_cevap": SIKLAR[verilen],
        "dogru_cevap": SIKLAR[dogru_index],
        "ilerleme": {
            "toplam_soru": durum["toplam"],
            "dogru_sayisi": durum["dogru"],
            "basari_yuzdesi": round(100 * durum["dogru"] / durum["toplam"], 1)
            if durum["toplam"]
            else 0.0,
        },
    }


def _cevabi_indexe_cevir(cevap) -> int | None:
    """'A' / 'a' / '0' / 0 gibi girdileri 0-4 aralığına çevirir."""
    if cevap is None:
        return None
    metin = str(cevap).strip().upper()
    if metin in SIKLAR:
        return SIKLAR.index(metin)
    if metin.isdigit() and 0 <= int(metin) <= 4:
        return int(metin)
    return None


# --------------------------------------------------------------------------
# Model tarafına açılan arayüz
# --------------------------------------------------------------------------

ARAC_HARITASI = {
    "terim_ara": terim_ara,
    "quiz_getir": quiz_getir,
    "cevap_kaydet": cevap_kaydet,
}

ARAC_SEMALARI = [
    {
        "type": "function",
        "function": {
            "name": "terim_ara",
            "description": (
                "Biyoloji sözlüğünden bir terimin tanımını, ders kitabı sayfasını ve kaynak "
                "adresini getirir. Bir biyoloji terimi/kavramı sorulduğunda MUTLAKA bu araç "
                "kullanılmalıdır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "terim": {
                        "type": "string",
                        "description": "Aranacak biyoloji terimi, örn: mayoz, fotosentez",
                    }
                },
                "required": ["terim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quiz_getir",
            "description": (
                "Gerçek sınav sorularından oluşan bankadan çoktan seçmeli soru getirir. "
                "Öğrenci soru sorulmasını istediğinde kullanılır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "konu": {
                        "type": "string",
                        "description": "Soru konusu, örn: mayoz. Boş bırakılırsa rastgele soru gelir.",
                    },
                    # Tip bilinçli olarak string: modeller sayıları sık sık "1"
                    # şeklinde tırnaklı gönderir ve katı şema doğrulaması
                    # (Groq) bunu 400 ile reddeder. Çevirim db katmanında yapılır.
                    "adet": {
                        "type": "string",
                        "description": "Kaç soru getirileceği, 1-5 arası bir sayı",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cevap_kaydet",
            "description": (
                "Öğrencinin bir quiz sorusuna verdiği cevabı değerlendirip veritabanına kaydeder "
                "ve güncel ilerleme özetini döndürür. Öğrenci bir şık söylediğinde kullanılır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "soru_id": {
                        "type": "string",
                        "description": "Cevaplanan sorunun quiz_getir ile dönen soru_id değeri",
                    },
                    "cevap": {
                        "type": "string",
                        "description": "Öğrencinin verdiği şık",
                        "enum": ["A", "B", "C", "D", "E"],
                    },
                },
                "required": ["soru_id", "cevap"],
            },
        },
    },
]


def calistir(ad: str, argumanlar: dict) -> dict:
    """Model tarafından istenen aracı çalıştırır (fonksiyon yönlendirme)."""
    fonksiyon = ARAC_HARITASI.get(ad)
    if fonksiyon is None:
        return {"hata": f"'{ad}' adında bir araç yok."}
    try:
        return fonksiyon(**(argumanlar or {}))
    except TypeError as hata:
        return {"hata": f"'{ad}' araç parametreleri hatalı: {hata}"}
