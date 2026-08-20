import os, json, logging
from dotenv import load_dotenv
from openai import OpenAI, BadRequestError
import araclar
import havuz

logger = logging.getLogger(__name__)

load_dotenv()
istemci = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
MODEL = "gemini-3.1-flash-lite"
MAX_GECMIS_MESAJ = 6  # sohbet hafizasi: yalnizca son 6 mesaj (~3 tur) modele gonderilir; her istegi kucuk tutar (hiz limiti)

def _havuz_metni():
    return ", ".join(m["ad"] for m in havuz.MESLEK_HAVUZU)

SISTEM_TALIMATI = f"""Sen, mesleğini henüz seçmemiş GENÇLERE yol gösteren; sıcak, meraklı ve sade bir kariyer rehberisin. Genç ayrı bir "İlgi Testi" sekmesinde test yapıp kendine uygun meslekleri görebilir. Sen sohbette onunla gerçek bir DİYALOG kurarsın: sorular sorar, merak uyandırır ve gerçek verilerle yol gösterirsin.

## TAVRIN (proaktif, soru soran)
- Tek yönlü bilgi DÖKME; sohbet et. Gence sorular sor: neyi merak ediyor, hangi meslek ilgisini çekti, günlük hayatta neyi sevdiği, iki mesleği karşılaştırmak ister mi.
- Her cevabın sonunda konuşmayı ilerleten bir soru sor (ör. "Bunun geleceğini de merak eder misin?", "Hangi yanı sana yakın geldi?").
- Kısa kısa ilerle; karşındaki 15 yaşında olabilir.

## HANGİ SORUYA HANGİ ARAÇ (soruya göre doğru kaynağı çağır)
- Bir mesleği GENEL tanıtma / hakkında genel bilgi ("X'i tanıt", "X nasıl bir meslek", "X hakkında bilgi ver") → SADECE meslek_tanit'i çağır (ne yapar + nasıl başlanır + büyüme + beceriler + gelecek skoru+maaş hepsi burada). Bunun için tek tek diğer araçları ÇAĞIRMA.
- Yalnızca TEK bir şey soruluyorsa ilgili tekil aracı çağır:
  - "Bu meslek ne iş yapar?" → meslek_ne_yapar (O*NET)
  - "Nasıl başlarım, ne eğitim gerekir?" → nasil_baslanir (O*NET)
  - "Hangi beceriler gerekir?" → meslek_becerileri (O*NET)
  - "Geleceği parlak mı, büyüyor mu?" → buyume_gorunumu (O*NET) VE gelecek_skoru (Adzuna)
  - "Avrupa'da iş var mı, maaş ne kadar?" → gelecek_skoru (Adzuna)
- Kaydet/listele/profil → listeme_ekle, listem, profil_kaydet, profilim
Aynı araç için birden fazla arka arkaya çağrı yapma; bir aracı bir mesleğe zaten çağırdıysan sonucu kullan.

## CEVAP İLKESİ (kaynaklı + damıtılmış + sıcak)
- ALTIN KURAL — SADECE GENİŞLET, UYDURMA: Görevin, araçlardan gelen veriyi Türkçeye çevirip anlaşılır ve sıcak biçimde AÇMAK. Araç sonucunda BULUNMAYAN hiçbir olguyu (belirli okul/üniversite/kurs adı, şirket, şehir, yüzde/oran, yıl, sayı, sertifika adı) EKLEME. Emin değilsen "bu konuda kesin veri yok" de; boşluğu tahminle doldurma.
- meslek_tanit ÜÇ kaynaktan veri döner. Cevabı İKİ AYRI COĞRAFİ BÖLÜME AYIR; verileri BİRBİRİNE KARIŞTIRMA. Önce Amerika, sonra Avrupa:
  1) "🇺🇸 Amerika (O*NET)" başlıklı bölüm: ne yapar / günlük görevler, nasıl başlanır / eğitim, büyüme görünümü ve O*NET becerileri — hepsi "O*NET'e göre".
  2) "🇪🇺 Avrupa (ESCO + Adzuna)" başlıklı bölüm: ESCO'nun Avrupa tanımı ve temel becerileri ("ESCO'ya göre") + talep skoru, ilan sayısı ve maaş ("Adzuna iş ilanlarına göre").
  Kaynak etiketlerini ASLA düşürme. Her iki bölüm de aynı cevapta, alt alta olsun.
- Bir kaynaktan (O*NET/Adzuna) rakam ya da bilgi vereceksen o aracı MUTLAKA çağır; çağırmadığın bir kaynaktan sayı/veri UYDURMA. Maaş ya da ilan sayısı söyleyeceksen önce gelecek_skoru'nu (veya meslek_tanit) çağır — çağırmadıysan sayı verme.
- Her iddiayı DAYANAĞIYLA söyle: "O*NET meslek verilerine göre...", "Avrupa iş ilanlarına (Adzuna) göre...". Türk kullanıcı içinden "neye göre?" diye sorar; cevabı peşinen ver.
- Araçlardan gelen İngilizce metni (açıklama, görevler, eğitim notları) Türkçeye çevirip SADELEŞTİR. Ham liste ya da JSON dökme.
- gelecek_skoru → "Gelecek skoru: X/100 — [band]" yaz; sonra ulke_dagilimi'ndaki TÜM ülkeleri ilan sayısı VE ortalama maaşıyla (para birimiyle) çoktan aza sıralı listele. Maaşlar yıllık ve yerel para birimindedir; net etiketle. Maaşı olmayan ülke için "maaş bilgisi yok" de.
- gelecek_skoru "hata" dönerse güvenilir talep verisi alınamadığını söyle, skor uydurma. "veri_guveni" alanı "orta" ise kaç ülkenin verisi alınabildiğini (basari_ulke / toplam_ulke) dürüstçe belirt.
- buyume_gorunumu → ASLA "parlak gelecek: evet/hayır" gibi ham bir şey yazma; MUTLAKA 2-3 cümleyle AÇIKLA. TRUE ise sıcak anlat: "O*NET'e göre önümüzdeki yıllarda hızla büyümesi ve çok sayıda fırsat sunması beklenen mesleklerden." FALSE ise cesaret kırma: "hızlı büyüyenler listesinde değil ama bu geleceği yok demek değil — köklü ve istikrarlı bir meslek" de ve talebi Adzuna verisiyle destekle.
- nasil_baslanir → gereken eğitim/hazırlık düzeyini cesaretlendirici anlat ("şöyle bir yol var ama adım adım gidilir").
- Sıcak, cesaretlendirici, sade; jargon yok.
- YAZMA araçları (profil_kaydet, listeme_ekle) yalnızca kullanıcı AÇIKÇA "kaydet" / "listeme ekle" dediğinde çağrılır; kendiliğinden kaydetme. Kaydetmeden önce kısaca ne kaydedeceğini söyle.

## MESLEK HAVUZU (yalnızca buradan öner; uydurma yok)
{_havuz_metni()}

## VERİ KAYNAKLARI
- meslek_ne_yapar: O*NET (ABD) — mesleğin tanımı ve günlük görevleri.
- meslek_esco: ESCO (Avrupa) — mesleğin Avrupa'daki resmi tanımı ve temel becerileri.
- nasil_baslanir: O*NET — gereken eğitim ve hazırlık düzeyi.
- buyume_gorunumu: O*NET — meslek "parlak gelecek" (hızlı büyüyen/çok fırsatlı) sayılıyor mu.
- meslek_becerileri: O*NET — meslekte gereken temel beceriler.
- gelecek_skoru: Adzuna — 10 Avrupa ülkesinde talep skoru, ilan sayısı, maaş (TÜRKÇE meslek adı ver).
- listeme_ekle / listem: ilgi listesi. profil_kaydet / profilim: gencin profil özeti.

## SINIR
YALNIZCA Türkçe yaz; başka dillerden tek kelime bile karıştırma. Genç yeni bir test isterse "İlgi Testi" sekmesine yönlendir. Kesin iş garantisi verme; bilgilendir."""

def _arac(ad, aciklama, ozellikler=None, zorunlu=None):
    return {"type": "function", "function": {
        "name": ad, "description": aciklama,
        "parameters": {"type": "object", "properties": ozellikler or {}, "required": zorunlu or []},
    }}

_meslek = {"meslek": {"type": "string", "description": "Türkçe meslek adı (havuzdan)"}}

araclar_tanim = [
    _arac("meslek_tanit", "Bir mesleği GENEL tanıtmak için gereken her şeyi ÜÇ kaynaktan (ESCO Avrupa tanımı+becerileri, O*NET ABD görevleri+eğitim+büyüme, Adzuna talep+maaş) TEK çağrıda getirir. Kullanıcı bir mesleği genel olarak sorduğunda tek tek araç yerine BUNU çağır.", _meslek, ["meslek"]),
    _arac("meslek_ne_yapar", "Bir mesleğin ne iş yaptığını ve günlük görevlerini getirir (O*NET; sadeleştir).", _meslek, ["meslek"]),
    _arac("meslek_esco", "Bir mesleğin Avrupa'daki (ESCO) resmi tanımını ve temel becerilerini getirir.", _meslek, ["meslek"]),
    _arac("nasil_baslanir", "Bir mesleğe başlamak için gereken eğitim/hazırlık düzeyini getirir (O*NET).", _meslek, ["meslek"]),
    _arac("buyume_gorunumu", "Bir mesleğin 'parlak gelecek' (hızlı büyüyen/çok fırsatlı) sayılıp sayılmadığını getirir (O*NET).", _meslek, ["meslek"]),
    _arac("meslek_becerileri", "Bir meslekte gereken temel becerileri getirir (O*NET).", _meslek, ["meslek"]),
    _arac("gelecek_skoru", "Bir mesleğin talep skoru (0-100), en talepli ülkelerdeki ilan sayısı ve maaşı (Adzuna, 10 Avrupa ülkesi).", _meslek, ["meslek"]),
    _arac("listeme_ekle", "Bir mesleği gencin ilgi listesine kaydeder.", _meslek, ["meslek"]),
    _arac("listem", "Kayıtlı ilgi listesini getirir."),
    _arac("profil_kaydet", "Gencin ilgi/profil özetini kaydeder.", {"ozet": {"type": "string", "description": "Gencin ilgilerinin kısa özeti"}}, ["ozet"]),
    _arac("profilim", "Daha önce kaydedilmiş profil özetini getirir."),
]

BILGI_ARACLARI = {
    "meslek_tanit": araclar.meslek_tanit,
    "meslek_ne_yapar": araclar.meslek_ne_yapar,
    "meslek_esco": araclar.meslek_esco,
    "nasil_baslanir": araclar.nasil_baslanir,
    "buyume_gorunumu": araclar.buyume_gorunumu,
    "meslek_becerileri": araclar.meslek_becerileri,
    "gelecek_skoru": araclar.gelecek_skoru,
}

def tool_calistir(ad, argumanlar, kullanici_id="yerel"):
    argumanlar = argumanlar if isinstance(argumanlar, dict) else {}
    try:
        if ad in BILGI_ARACLARI:
            meslek = argumanlar.get("meslek")
            if not meslek:
                return {"hata": "Meslek adi belirtilmedi."}
            if not araclar.havuzda_var(meslek):
                return {"hata": f"'{meslek}' havuzda yok. Havuzdaki mesleklerden birini sec."}
            return BILGI_ARACLARI[ad](meslek)
        if ad == "listeme_ekle":
            meslek = argumanlar.get("meslek")
            if not meslek:
                return {"hata": "Meslek adi belirtilmedi."}
            if not araclar.havuzda_var(meslek):
                return {"hata": f"'{meslek}' havuzda yok. Havuzdaki mesleklerden birini sec."}
            return araclar.listeme_ekle(kullanici_id, meslek)
        if ad == "listem":
            return araclar.listem(kullanici_id)
        if ad == "profilim":
            return araclar.profilim(kullanici_id)
        if ad == "profil_kaydet":
            ozet = argumanlar.get("ozet")
            if not ozet:
                return {"hata": "Profil ozeti belirtilmedi."}
            return araclar.profil_kaydet(kullanici_id, ozet)
        return {"hata": f"Bilinmeyen arac: {ad}"}
    except Exception:
        logger.exception("Arac hatasi: %s", ad)
        return {"hata": "Arac calistirilirken bir sorun olustu."}

def _model_yaniti(mesajlar, deneme=3):
    # Model ara sira gecersiz bir arac adi/bicimi uretip 400 dondurebilir.
    # Ornekleme rastgele oldugu icin ayni cagriyi birkac kez tekrar denemek
    # genelde temiz bir sonuc verir.
    son_hata = None
    for _ in range(deneme):
        try:
            return istemci.chat.completions.create(
                model=MODEL, messages=mesajlar, tools=araclar_tanim,
                reasoning_effort="low",  # Gemini 3.x "dusunme" suresini kisar -> daha hizli
            )
        except BadRequestError as hata:
            if "tool" in str(hata).lower():
                son_hata = hata
                continue
            raise
    raise son_hata

def sohbet(kullanici_mesaji, gecmis=None, kullanici_id="yerel"):
    mesajlar = [{"role": "system", "content": SISTEM_TALIMATI}]
    if gecmis:
        mesajlar.extend(gecmis[-MAX_GECMIS_MESAJ:])
    mesajlar.append({"role": "user", "content": kullanici_mesaji})

    mesaj = None
    for _ in range(6):
        try:
            yanit = _model_yaniti(mesajlar)
        except Exception:
            logger.exception("Model cagrisi basarisiz")
            return "Şu an yanıt veremedim (bağlantı ya da kota sorunu olabilir). Lütfen biraz sonra tekrar dener misin?"

        mesaj = yanit.choices[0].message
        mesajlar.append(mesaj)

        if not mesaj.tool_calls:
            return mesaj.content or "Bir şey ters gitti; sorunu biraz farklı sorar mısın?"

        for cagri in mesaj.tool_calls:
            try:
                argumanlar = json.loads(cagri.function.arguments or "{}")
            except (ValueError, TypeError):
                argumanlar = {}
            logger.info("ARAÇ ÇAĞRISI → %s(%s)", cagri.function.name, argumanlar)
            sonuc = tool_calistir(cagri.function.name, argumanlar, kullanici_id)
            icerik = json.dumps(sonuc, ensure_ascii=False)
            logger.info("ARAÇ SONUCU ← %s: %s", cagri.function.name, icerik[:400])
            mesajlar.append({
                "role": "tool",
                "tool_call_id": cagri.id,
                "content": icerik,
            })

    return (mesaj.content if mesaj else None) or "Bu isteği tam sonuçlandıramadım; biraz daha basit sorar mısın?"

if __name__ == "__main__":
    print(sohbet("Grafik tasarımcı nasıl bir meslek, geleceği parlak mı?"))
