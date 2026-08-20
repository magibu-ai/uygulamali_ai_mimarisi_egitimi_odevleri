"""Modelin çağırabileceği 4 araç (tool).

Her araç sade bir Python fonksiyonudur ve METİN döndürür; bu metin modele geri
beslenir.  Hiçbiri hata fırlatmaz — hata olursa Türkçe bir açıklama döner,
böylece sohbet döngüsü çökmez.

Araçlar:
    1. aciliyet_degerlendir  -> SENARYOYA ÖZEL. Kural tabanlı kırmızı-bayrak
                                puanlaması ile aciliyet düzeyini ve önerilen
                                bölümü hesaplar (kod yürütme / hesaplama).
    2. tibbi_bilgi_ara       -> RAG. Gerçek hastane makalelerinden bilgi getirir.
    3. internet_arama        -> Web araması (DuckDuckGo), en yakın kurum / güncel bilgi.
    4. yakin_saglik_kurulusu -> HARİCİ API (OpenStreetMap). Şehirdeki en yakın
                                hastane / eczaneleri listeler.

TOOL_SCHEMAS listesi ise modele "elinde şu araçlar var" demenin JSON hâlidir.
"""

import html
import re
import subprocess
import sys

import requests

import triyaj_rag

TIMEOUT = 20
HEADERS = {"User-Agent": "triyaj-asistan/1.0 (egitim projesi)"}


# ---------------------------------------------------------------------------
# 1) SENARYOYA ÖZEL ARAÇ: aciliyet değerlendirme (kural tabanlı hesaplama)
# ---------------------------------------------------------------------------
#
# Mantık: kullanıcının anlattığı şikâyette "kırmızı bayrak" ifadeleri ararız.
# Her bulunan ifade bir puan ekler; toplam puan aciliyet düzeyini belirler.
# Bu, LLM'in sezgisine bırakılmayan, ŞEFFAF ve DETERMİNİSTİK bir karardır —
# aynı girdi her zaman aynı sonucu verir.  (Kesin tanı DEĞİLDİR; yönlendirmedir.)

# Hayatı tehdit eden ifadeler -> doğrudan 112 / ACİL.
KIRMIZI_BAYRAKLAR = [
    "nefes alamıyor", "nefes alamıyorum", "nefesim daralıyor", "nefes darlığı",
    "göğüs ağrısı", "göğsümde baskı", "göğsüme baskı", "göğsüm sıkışıyor",
    "sol koluma yayıl", "kola yayılan", "çeneme yayıl",
    "felç", "yüzüm kaydı", "yüzde kayma", "konuşamıyor", "konuşmam bozuldu",
    "kolum tutmuyor", "bir tarafım tutmuyor", "dilim dolaşıyor",
    "bilincini kaybet", "bayıldı", "bayılma", "kendinde değil", "baygın",
    "morarma", "morardı", "dudakları mor",
    "durmayan kanama", "kan fışkır", "çok kan kaybı", "kanamayı durduramıyor",
    "havale", "nöbet geçir", "kasılma",
    "boğazım şişti", "dilim şişti", "dudaklarım şişti", "anafilaksi",
    "en şiddetli baş ağrısı", "hayatımın en kötü baş ağrısı",
    "intihar", "kendime zarar",
    "zehirlendi", "ilaç içti", "aşırı doz",
]

# Ciddi ama her zaman 112 gerektirmeyen ifadeler -> ACİL SERVİS / bugün.
SARI_BAYRAKLAR = [
    "yüksek ateş", "40 derece", "39 derece", "ateşim düşmüyor",
    "sürekli kusma", "durmayan kusma", "kanlı kusma", "siyah dışkı",
    "şiddetli karın ağrısı", "şiddetli ağrı", "dayanılmaz ağrı",
    "kanlı idrar", "idrarımda kan", "kanlı balgam",
    "ense sertliği", "boynum tutuldu ateş",
    "şiddetli baş dönmesi", "yürüyemiyorum",
    "gebe", "hamile", "hamileyim",
    "şeker düştü", "şekerim düştü", "kan şekeri",
    "derin kesik", "dikiş", "kemik göründü",
    "3 günden fazla ateş", "üç gündür ateş",
]

# Şikâyet -> önerilen poliklinik/bölüm eşlemesi (anahtar kök'e göre).
# Not: Türkçe ekler nedeniyle KÖK kullanıyoruz ("göğs" -> göğüs/göğsümde/göğsüm).
BOLUM_ESLEME = [
    (["göğs", "göğ", "kalp", "çarpıntı", "tansiyon", "nefes", "kol"], "Kardiyoloji / Acil"),
    (["baş ağrı", "baş dön", "felç", "inme", "uyuşma", "konuş", "denge"], "Nöroloji"),
    (["karın", "karn", "mide", "bulantı", "kusma", "ishal", "reflü", "hazımsız"], "İç Hastalıkları / Gastroenteroloji"),
    (["idrar", "böbrek", "yan ağrı", "sidik"], "Üroloji"),
    (["boğaz", "boğz", "kulak", "burun", "geniz", "ses"], "Kulak Burun Boğaz"),
    (["cilt", "deri", "döküntü", "kaşıntı", "kızarık", "kızarıklık"], "Dermatoloji"),
    (["bel", "sırt", "eklem", "kırık", "burkul", "diz", "kemik"], "Ortopedi / Fizik Tedavi"),
    (["ateş", "grip", "halsiz", "enfeksiyon", "üşütme"], "İç Hastalıkları / Aile Hekimliği"),
    (["göz", "görme", "bulanık gör"], "Göz Hastalıkları"),
    (["şeker", "tiroit", "hormon"], "Endokrinoloji"),
]


def _bolum_oner(metin: str) -> str:
    """Şikâyet metnine göre uygun poliklinik(ler)i önerir."""
    for anahtarlar, bolum in BOLUM_ESLEME:
        if any(k in metin for k in anahtarlar):
            return bolum
    return "Aile Hekimliği / İç Hastalıkları"


def aciliyet_degerlendir(belirtiler: str, sure: str = "") -> str:
    """Şikâyeti kural tabanlı puanlayarak aciliyet düzeyini belirler.

    Bu bir TANI değildir; nereye başvurulacağına dair bir YÖNLENDİRMEdir.
    """
    metin = f"{belirtiler} {sure}".lower()

    kirmizi = [b for b in KIRMIZI_BAYRAKLAR if b in metin]
    sari = [b for b in SARI_BAYRAKLAR if b in metin]
    puan = len(kirmizi) * 3 + len(sari) * 1
    bolum = _bolum_oner(metin)

    if kirmizi:
        return (
            "🔴 ACİL DURUM (puan: {puan})\n"
            "Belirtileriniz ciddi olabilir. Lütfen VAKİT KAYBETMEDEN 112'yi arayın "
            "veya en yakın acil servise gidin.\n"
            "Dikkat çeken ifadeler: {bulgular}\n"
            "İlgili bölüm: {bolum}\n"
            "Not: Bu bir ön değerlendirmedir, kesin tanı değildir."
        ).format(puan=puan, bulgular=", ".join(kirmizi), bolum=bolum)

    if sari:
        return (
            "🟠 BUGÜN DEĞERLENDİRİLMELİ (puan: {puan})\n"
            "Belirtileriniz bugün bir hekim tarafından görülmeyi gerektirebilir. "
            "Acil servise ya da ilgili polikliniğe başvurmanız önerilir. "
            "Belirtiler ağırlaşırsa (nefes darlığı, bilinç değişikliği vb.) 112'yi arayın.\n"
            "Dikkat çeken ifadeler: {bulgular}\n"
            "Önerilen bölüm: {bolum}\n"
            "Not: Bu bir ön değerlendirmedir, kesin tanı değildir."
        ).format(puan=puan, bulgular=", ".join(sari), bolum=bolum)

    return (
        "🟢 DÜŞÜK ACİLİYET (puan: {puan})\n"
        "Acil bir bulgu görünmüyor. Belirtiler birkaç günde geçmezse ya da "
        "ağırlaşırsa bir poliklinikten randevu almanız yeterli olacaktır. "
        "Bol sıvı ve dinlenme genellikle yardımcı olur.\n"
        "Önerilen bölüm: {bolum}\n"
        "Not: Bu bir ön değerlendirmedir, kesin tanı değildir. "
        "Şüphedeyseniz mutlaka bir hekime danışın."
    ).format(puan=puan, bolum=bolum)


# ---------------------------------------------------------------------------
# 2) RAG ARACI: bilgi tabanından tıbbi bilgi getir
# ---------------------------------------------------------------------------
def tibbi_bilgi_ara(soru: str) -> str:
    """Tıbbi soruyu SADECE indekslenmiş gerçek makalelere dayanarak cevaplar.

    Cevap burada bitmiş hâldedir; chat.py'deki model bunu aynen aktarmalıdır.
    """
    sonuc = triyaj_rag.answer_medical(soru)
    if not sonuc["grounded"]:
        return sonuc["answer"]
    kaynaklar = "\n".join(
        f"- {s['title']} (benzerlik {s['similarity']})\n  {s['url']}"
        for s in sonuc["sources"]
    )
    return f"{sonuc['answer']}\n\nKaynaklar:\n{kaynaklar}"


# ---------------------------------------------------------------------------
# 3) WEB ARAMASI: DuckDuckGo (anahtar gerektirmez)
# ---------------------------------------------------------------------------
def internet_arama(sorgu: str, sonuc_sayisi: int = 5) -> str:
    """DuckDuckGo'nun sade (lite) arayüzünde arama yapar. API anahtarı gerekmez."""
    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": sorgu},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text,
            flags=re.DOTALL,
        )
        results = []
        for url, raw_title in pairs[:sonuc_sayisi]:
            title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
            if title:
                results.append(f"{len(results) + 1}. {title}\n   {html.unescape(url)}")
        if results:
            return f"'{sorgu}' için internet sonuçları:\n" + "\n".join(results)
    except requests.RequestException:
        pass  # aşağıdaki Wikipedia yedeğine düş

    return _wikipedia_yedek(sorgu, sonuc_sayisi)


def _wikipedia_yedek(sorgu: str, sonuc_sayisi: int) -> str:
    """Yedek arama: Türkçe Wikipedia API'si."""
    try:
        data = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": sorgu,
                "srlimit": sonuc_sayisi, "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        items = data.get("query", {}).get("search", [])
        if not items:
            return f"'{sorgu}' için sonuç bulunamadı."
        lines = []
        for i, item in enumerate(items, start=1):
            snippet = html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
            slug = item["title"].replace(" ", "_")
            lines.append(f"{i}. {item['title']}\n   {snippet}\n   https://tr.wikipedia.org/wiki/{slug}")
        return f"'{sorgu}' için Wikipedia sonuçları:\n" + "\n".join(lines)
    except requests.RequestException as exc:
        return f"Arama yapılamadı: {exc}"


# ---------------------------------------------------------------------------
# 4) HARİCİ API: en yakın sağlık kuruluşu (OpenStreetMap — anahtar gerektirmez)
# ---------------------------------------------------------------------------
def yakin_saglik_kurulusu(sehir: str, tur: str = "hastane") -> str:
    """Bir şehirdeki hastane veya eczaneleri OpenStreetMap üzerinden listeler.

    tur: "hastane" ya da "eczane".
    Önce şehri Nominatim ile koordinata çevirir, sonra Overpass API ile
    yakındaki kurumları arar.  Hiçbir API anahtarı gerektirmez.
    """
    osm_etiket = "pharmacy" if tur.lower().startswith("ecz") else "hospital"
    okunur_tur = "eczane" if osm_etiket == "pharmacy" else "hastane"
    try:
        geo = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": sehir + ", Türkiye", "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        if not geo:
            return f"'{sehir}' konumu bulunamadı. Şehir adını kontrol edin."
        lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

        # Konumun ~8 km çevresindeki kurumları sorgula.
        query = (
            f'[out:json][timeout:20];'
            f'(node["amenity"="{osm_etiket}"](around:8000,{lat},{lon});'
            f' way["amenity"="{osm_etiket}"](around:8000,{lat},{lon}););'
            f'out center 8;'
        )
        data = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()
        kurumlar = []
        for el in data.get("elements", []):
            ad = el.get("tags", {}).get("name")
            if ad:
                kurumlar.append(ad)
            if len(kurumlar) >= 8:
                break
        if not kurumlar:
            return (
                f"{sehir} çevresinde OpenStreetMap üzerinde kayıtlı {okunur_tur} "
                f"bulunamadı. Güncel liste için internet_arama kullanabilirsiniz."
            )
        liste = "\n".join(f"- {ad}" for ad in kurumlar)
        return f"{sehir} çevresindeki bazı {okunur_tur}ler:\n{liste}"
    except (requests.RequestException, ValueError, KeyError) as exc:
        return f"{okunur_tur.capitalize()} bilgisi alınamadı: {exc}"


# ---------------------------------------------------------------------------
# 5) KOD YÜRÜTME: hesap makinesi (ayrı bir Python süreci -> subprocess)
# ---------------------------------------------------------------------------
# Modelin ürettiği aritmetik ifade, GÜVENLİK için önce katı bir beyaz listeden
# geçirilir (yalnızca sayı ve temel operatörler), sonra AYRI bir Python süreci
# içinde çalıştırılır. Böylece hem "kod yürütme (subprocess)" hem de "hesap
# makinesi" gereksinimi karşılanır. Sağlık bağlamında VKİ (kilo / boy^2), sıvı
# ihtiyacı veya kiloya göre doz gibi hesaplarda işe yarar.
_GUVENLI_IFADE = re.compile(r"^[0-9\.\+\-\*\/\%\(\)\s]+$")


def hesap_makinesi(islem: str) -> str:
    """Bir aritmetik ifadeyi ayrı bir Python süreci (subprocess) ile hesaplar."""
    ifade = (islem or "").strip()
    if not ifade:
        return "Hesaplanacak bir işlem verilmedi."
    # Güvenlik kapısı: yalnızca sayılar ve + - * / % ( ) . karakterlerine izin ver.
    if not _GUVENLI_IFADE.match(ifade):
        return (
            "Güvenlik nedeniyle yalnızca sayılar ve + - * / % ( ) işlemleri "
            "hesaplanabilir. Örnek: (72 / (1.75 * 1.75))"
        )
    kod = f"print(round(({ifade}), 4))"
    try:
        sonuc = subprocess.run(
            [sys.executable, "-c", kod],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return "Hesaplama zaman aşımına uğradı."
    if sonuc.returncode != 0:
        hata = (sonuc.stderr or "").strip().splitlines()
        return f"Hesaplama yapılamadı: {hata[-1] if hata else 'geçersiz ifade'}"
    return f"{ifade} = {sonuc.stdout.strip()}"


# ---------------------------------------------------------------------------
# Araç kayıt defteri ve modele sunulan JSON şemaları
# ---------------------------------------------------------------------------
TOOLS = {
    "aciliyet_degerlendir": aciliyet_degerlendir,
    "tibbi_bilgi_ara": tibbi_bilgi_ara,
    "internet_arama": internet_arama,
    "yakin_saglik_kurulusu": yakin_saglik_kurulusu,
    "hesap_makinesi": hesap_makinesi,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "aciliyet_degerlendir",
            "description": (
                "Kullanıcı bir SAĞLIK ŞİKÂYETİ / BELİRTİ anlattığında bu aracı çağır. "
                "Belirtileri kural tabanlı puanlayıp aciliyet düzeyini (acil / bugün / "
                "düşük) ve önerilen bölümü söyler. Kullanıcının cümlesini olduğu gibi "
                "'belirtiler' alanına ver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "belirtiler": {
                        "type": "string",
                        "description": "Kullanıcının anlattığı şikâyet/belirtiler (kendi cümlesi)",
                    },
                    "sure": {
                        "type": "string",
                        "description": "Belirtilerin ne kadar süredir olduğu (varsa), örn. '2 gündür'",
                    },
                },
                "required": ["belirtiler"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tibbi_bilgi_ara",
            "description": (
                "Bir hastalık, belirti, tahlil ya da durum hakkında BİLGİ sorulduğunda "
                "kullan (örn. 'inme belirtileri nelerdir', 'ateş neden olur'). Cevabı "
                "gerçek hastane makalelerinden üretir. Dönen metni aynen aktar, üzerine "
                "kendi tıbbi bilgini EKLEME."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "soru": {"type": "string", "description": "Kullanıcının tıbbi bilgi sorusu"},
                },
                "required": ["soru"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "internet_arama",
            "description": (
                "Güncel bilgi, haber ya da genel arama için internette arar. "
                "Tıbbi bilgi soruları için önce tibbi_bilgi_ara kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {"type": "string", "description": "Arama sorgusu"},
                    "sonuc_sayisi": {"type": "integer", "description": "Sonuç sayısı (varsayılan 5)"},
                },
                "required": ["sorgu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "yakin_saglik_kurulusu",
            "description": (
                "Kullanıcı bir şehirdeki hastane veya eczaneleri sorduğunda ya da acile "
                "yönlendirdiğinde en yakın kurumları listelemek için kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sehir": {"type": "string", "description": "Şehir adı, örn. 'Ankara'"},
                    "tur": {"type": "string", "description": "'hastane' ya da 'eczane' (varsayılan hastane)"},
                },
                "required": ["sehir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hesap_makinesi",
            "description": (
                "Sayısal bir hesap gerektiğinde kullan (örn. VKİ = kilo / (boy*boy), "
                "sıvı ihtiyacı, yüzde). Aritmetik ifadeyi 'islem' alanına ver; hesap "
                "ayrı bir Python süreciyle yapılır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "islem": {
                        "type": "string",
                        "description": "Aritmetik ifade, örn. '72 / (1.75 * 1.75)'",
                    },
                },
                "required": ["islem"],
            },
        },
    },
]
