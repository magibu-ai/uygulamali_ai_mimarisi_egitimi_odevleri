import logging
from concurrent.futures import ThreadPoolExecutor

import veritabani
import adzuna
import havuz
import onet
import esco

logger = logging.getLogger(__name__)

SORULAR = [
    {"soru": "Bir aleti ya da makineyi elimle tamir etmek, bir şeyler kurmak hoşuma gider.", "tip": "R"},
    {"soru": "Bir konuyu araştırıp 'neden böyle oluyor?' sorusunun cevabını bulmayı severim.", "tip": "I"},
    {"soru": "Çizmek, yazmak, tasarlamak ya da yeni bir şey yaratmak beni mutlu eder.", "tip": "A"},
    {"soru": "İnsanlara yardım etmek, onlara bir şey öğretmek bana iyi gelir.", "tip": "S"},
    {"soru": "Bir grubu yönlendirmek, insanları ikna etmek ya da bir iş kurmak hoşuma gider.", "tip": "E"},
    {"soru": "Planlı, düzenli ve belli kurallara göre çalışmak beni rahatlatır.", "tip": "C"},
    {"soru": "Açık havada ya da fiziksel olarak hareketli işlerde çalışmayı tercih ederim.", "tip": "R"},
    {"soru": "Sayılarla, verilerle ya da bilimsel problemlerle uğraşmak ilgimi çeker.", "tip": "I"},
    {"soru": "Özgün fikirler üretmeyi ve kendimi yaratıcı yollarla ifade etmeyi severim.", "tip": "A"},
    {"soru": "Başkalarının dertlerini dinlemek ve onlara destek olmak bana anlamlı gelir.", "tip": "S"},
    {"soru": "Sorumluluk almak, rekabet etmek ve bir hedefe ulaşmak beni motive eder.", "tip": "E"},
    {"soru": "Detaylara dikkat etmeyi ve işleri baştan sona düzenli bitirmeyi severim.", "tip": "C"},
    {"soru": "Montaj, tamir, bahçe ya da atölye işi gibi elle yapılan işlerden keyif alırım.", "tip": "R"},
    {"soru": "Karmaşık bir problemi ya da bilmeceyi çözene kadar uğraşmaktan hoşlanırım.", "tip": "I"},
    {"soru": "Müzik, sinema, sanat ya da tasarımla ilgilenmek bana zevk verir.", "tip": "A"},
    {"soru": "Bir ekipte insanlarla birlikte çalışıp onlara faydalı olmayı severim.", "tip": "S"},
    {"soru": "Fikirlerimi savunmak ve başkalarını peşimden sürüklemek bana heyecan verir.", "tip": "E"},
    {"soru": "Liste yapmak, kayıt tutmak ve her şeyi yerli yerinde tutmak hoşuma gider.", "tip": "C"},
]

def holland_analiz(cevaplar):
    if len(cevaplar) != len(SORULAR):
        return {"hata": f"{len(SORULAR)} cevap bekleniyor, {len(cevaplar)} geldi."}

    tip_skoru = {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}
    for soru, puan in zip(SORULAR, cevaplar):
        tip_skoru[soru["tip"]] += max(1, min(5, int(puan)))

    def uyum(meslek):
        harfler = meslek["riasec"]
        if not harfler:
            return 0
        return round(sum(tip_skoru[harf] for harf in harfler) / len(harfler), 2)

    sirali = sorted(havuz.MESLEK_HAVUZU, key=uyum, reverse=True)
    ortalama = sum(tip_skoru.values()) / len(tip_skoru)
    baskin = [
        t for t in sorted(tip_skoru, key=tip_skoru.get, reverse=True)
        if tip_skoru[t] > ortalama
    ][:2]

    def ozet(m):
        return {
            "ad": m["ad"],
            "adzuna": m["adzuna"],
            "kategori": m["kategori"],
            "riasec": m["riasec"],
            "uyum": uyum(m),
        }

    return {
        "tip_skorlari": tip_skoru,
        "baskin_tipler": baskin,
        "birincil": [ozet(m) for m in sirali[:8]],
        "ikincil": [ozet(m) for m in sirali[8:16]],
    }

def _onet_soc(meslek):
    kayit = _havuzda_bul(meslek)
    return kayit.get("onet") if kayit else None

def meslek_ne_yapar(meslek):
    soc = _onet_soc(meslek)
    veri = onet.ne_yapar(soc) if soc else None
    return veri or f"'{meslek}' icin bilgi bulunamadi."

def nasil_baslanir(meslek):
    soc = _onet_soc(meslek)
    veri = onet.nasil_baslanir(soc) if soc else None
    return veri or f"'{meslek}' icin bilgi bulunamadi."

def buyume_gorunumu(meslek):
    soc = _onet_soc(meslek)
    veri = onet.buyume_gorunumu(soc) if soc else None
    return veri or f"'{meslek}' icin buyume verisi bulunamadi."

def meslek_becerileri(meslek):
    soc = _onet_soc(meslek)
    veri = onet.beceriler(soc) if soc else None
    return veri or f"'{meslek}' icin beceri bilgisi bulunamadi."

def _havuzda_bul(meslek_adi):
    for m in havuz.MESLEK_HAVUZU:
        if m["ad"].strip().lower() == meslek_adi.strip().lower():
            return m
    return None

def havuzda_var(meslek):
    return _havuzda_bul(meslek) is not None

def gelecek_skoru(meslek):
    kayit = _havuzda_bul(meslek)
    if kayit:
        sonuc = adzuna.gelecek_skoru(kayit["adzuna"], kategori=kayit["kategori"])
        sonuc["meslek"] = kayit["ad"]
        return sonuc
    return adzuna.gelecek_skoru(meslek)

def meslek_esco(meslek):
    # ESCO (Avrupa) meslek tanimi + temel beceriler. Havuzdaki Ingilizce obeki
    # arama terimi olarak kullaniriz; ESCO basliklari Ingilizce oldugu icin
    # eslesme Turkce ada gore cok daha saglikli olur.
    kayit = _havuzda_bul(meslek)
    terim = kayit["adzuna"] if kayit else meslek
    veri = esco.meslek_bilgisi(terim)
    return veri or f"'{meslek}' icin ESCO (Avrupa) bilgisi bulunamadi."

def meslek_tanit(meslek):
    # Bir meslegi genel tanitmak icin gereken tum bilgileri (ESCO + O*NET + Adzuna)
    # TEK cagrida toplar. Boylece model bunlari tek tek cagirmak zorunda kalmaz;
    # sohbette 6 model turu yerine ~2 tur olur (hiz limitini az yorar).
    # Alt cagrilar birbirinden bagimsiz oldugu icin PARALEL calisir -> toplam sure
    # en yavas cagri kadar olur, hepsinin toplami kadar degil.
    isler = {
        "ne_yapar": meslek_ne_yapar,
        "esco": meslek_esco,
        "nasil_baslanir": nasil_baslanir,
        "buyume": buyume_gorunumu,
        "beceriler": meslek_becerileri,
        "gelecek_skoru": gelecek_skoru,
    }
    sonuc = {"meslek": meslek}
    with ThreadPoolExecutor(max_workers=len(isler)) as calisan:
        gelecekler = {ad: calisan.submit(fn, meslek) for ad, fn in isler.items()}
        for ad, gelecek in gelecekler.items():
            try:
                sonuc[ad] = gelecek.result()
            except Exception:
                logger.exception("meslek_tanit alt cagrisi basarisiz: %s", ad)
                sonuc[ad] = None
    return sonuc

def meslek_talebi(meslek):
    return adzuna.meslek_talebi_adzuna(meslek)

def profil_kaydet(kullanici_id, ozet):
    veritabani.profil_kaydet(kullanici_id, ozet)
    return "Profilin kaydedildi."

def profilim(kullanici_id):
    ozet = veritabani.profil_getir(kullanici_id)
    if ozet is None:
        return "Henuz kayitli profilin yok."
    return ozet

def listeme_ekle(kullanici_id, meslek, not_bilgisi=""):
    veritabani.ekle(kullanici_id, meslek, not_bilgisi)
    return f"'{meslek}' listene eklendi."

def listem(kullanici_id):
    satirlar = veritabani.listele(kullanici_id)
    if not satirlar:
        return "Listen bos."
    return [{"meslek": s[1], "not": s[2]} for s in satirlar]

if __name__ == "__main__":
    print(profil_kaydet("deneme", "Sanata ve insanlarla calismaya ilgi duyan biri."))
    print(profilim("deneme"))
    print(gelecek_skoru("Grafik Tasarımcı"))