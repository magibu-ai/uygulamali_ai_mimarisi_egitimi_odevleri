import re
from pathlib import Path
import chromadb

from sentence_transformers import SentenceTransformer


# =========================================================
# YOLLAR
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

DATA_DIR = PROJECT_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

CV_PATH = DATA_DIR / "cv.txt"
MULAKAT_PATH = DATA_DIR / "mulakat_notlari.txt"


# =========================================================
# AYARLAR
# =========================================================

COLLECTION_NAME = "kariyer_bilgileri"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100

# Bir başlıktan önce bu sayıda veya daha fazla "\n" varsa
# (yani en az bir tam boş satır varsa) bu başlık yeni bir ANA
# bölüm başlangıcı sayılır. Tek boş satır ise mevcut ana bölümün
# alt başlığı olarak kabul edilir. (Bkz. data/mulakat_notlari.txt:
# "SQL" ile "WINDOW FUNCTIONS" arasında tek boş satır var ve bu
# yüzden aynı ana bölümün parçası sayılırlar; "DATA WAREHOUSE"
# öncesinde iki boş satır var ve bu yeni bir ana bölüm başlatır.)
ANA_BOLUM_AYIRICI_UZUNLUK = 3

# =========================================================
# MODEL
# =========================================================

print("Embedding modeli yükleniyor...")

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME
)

print("Embedding modeli hazır.")


# =========================================================
# DOSYA OKUMA
# =========================================================

def dosya_oku(dosya_yolu):
    """
    UTF-8 metin dosyasını okur.
    """

    if not dosya_yolu.exists():
        print(
            f"⚠️ Dosya bulunamadı: {dosya_yolu}"
        )
        return ""

    return dosya_yolu.read_text(
        encoding="utf-8"
    ).strip()


# =========================================================
# BÖLÜM / BAŞLIK TESPİTİ
# =========================================================

def _paragraflari_ayikla(metin):
    """
    Metni paragraflara ayırır. Her paragraf için, kendisinden önce
    kaç tane ardışık yeni satır karakteri bulunduğunu ("ana_gecis")
    da birlikte döndürür. Bu bilgi, bir başlığın yeni bir ana bölüm
    mü yoksa mevcut ana bölümün alt başlığı mı olduğunu anlamak
    için kullanılır.
    """

    parcalar = re.split(r"(\n{2,})", metin.strip())

    paragraflar = []

    for index in range(0, len(parcalar), 2):

        parca_metni = parcalar[index].strip()

        if not parca_metni:
            continue

        ayirici = parcalar[index - 1] if index > 0 else ""

        paragraflar.append(
            {
                "text": parca_metni,
                "ana_gecis": len(ayirici) >= ANA_BOLUM_AYIRICI_UZUNLUK,
            }
        )

    return paragraflar


def _baslik_mi(paragraf_metni):
    """
    Bir paragrafın bölüm başlığı olup olmadığını tespit eder.

    İki başlık biçimini destekler:
      - Markdown: "#" / "##" ile başlayan tek satırlık başlıklar
        (cv.txt bu biçimi kullanıyor)
      - Düz metin: tamamen büyük harflerden oluşan, ":" ile bitmeyen
        tek satırlık başlıklar, örn. "SQL", "ETL"
        (mulakat_notlari.txt bu biçimi kullanıyor)

    Başlık değilse None döner.
    """

    if "\n" in paragraf_metni:
        return None

    metin = paragraf_metni.strip()

    if not metin:
        return None

    if metin.startswith("#"):
        baslik = metin.lstrip("#").strip()
        return baslik or None

    if metin.endswith(":"):
        return None

    if len(metin) > 60:
        return None

    harfler = [karakter for karakter in metin if karakter.isalpha()]

    if not harfler:
        return None

    if all(karakter == karakter.upper() for karakter in harfler):
        return metin

    return None


def _markdown_seviyesi(paragraf_metni):
    """
    Markdown başlığının seviyesini döndürür ("#" -> 1, "##" -> 2).
    Markdown başlığı değilse None döner.
    """

    metin = paragraf_metni.strip()

    if not metin.startswith("#"):
        return None

    seviye = len(metin) - len(metin.lstrip("#"))

    return seviye if seviye > 0 else None


def _parca_olustur(parcalar, tampon, alt_gecmisi, ana_baslik):
    """
    Tamponda biriken paragrafları tek bir parça (chunk) olarak
    `parcalar` listesine ekler. Parça metninin başına, hangi
    bölüme ait olduğunu belirten "[BÖLÜM: ...]" etiketini ekler.
    Bu etiket embedding'e de dahil olur; böylece örneğin "Window
    Functions" içeriği geçen bir parça, "SQL" ana bölümüne ait
    olduğunu embedding seviyesinde de taşımış olur.
    """

    if not tampon:
        return

    icerik = "\n\n".join(tampon)

    alt_basliklar = list(
        dict.fromkeys(
            baslik for baslik in alt_gecmisi if baslik
        )
    )

    if not alt_basliklar:
        bolum = ana_baslik or "Genel"
        etiket = bolum

    elif len(alt_basliklar) == 1 and alt_basliklar[0] == ana_baslik:
        bolum = ana_baslik
        etiket = bolum

    else:
        bolum = alt_basliklar[-1]

        if ana_baslik and ana_baslik not in alt_basliklar:
            etiket = f"{ana_baslik} > {', '.join(alt_basliklar)}"
        else:
            etiket = ", ".join(alt_basliklar)

    parcalar.append(
        {
            "text": f"[BÖLÜM: {etiket}]\n{icerik}",
            "section": bolum,
            "major_section": ana_baslik or bolum,
        }
    )


# =========================================================
# METİN PARÇALAMA
# =========================================================

def belgeyi_parcala(
    metin,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):
    """
    Metni, bölüm/alt bölüm başlıklarını koruyarak parçalara böler.

    Orijinal paragraf tabanlı gruplama mantığı korunur (parçalar
    chunk_size'ı aşmayacak şekilde paragraflar biriktirilir), ancak
    ek olarak:

      - Her parça hangi ana bölüme ("major_section") ve hangi alt
        başlığa ("section") ait olduğunu bilir.
      - Bir parça, farklı bir ANA bölümün içeriğini asla içermez
        (ana bölüm değiştiğinde tampon her zaman boşaltılır).
      - Aynı ana bölüm altındaki alt başlıklar (örn. SQL ana
        bölümündeki "Window Functions" alt başlığı) chunk_size
        izin verdiği sürece aynı ana bölüm etrafında toplanabilir.
      - Parça metninin başına "[BÖLÜM: ...]" etiketi eklenir.
    """

    paragraflar = _paragraflari_ayikla(metin)

    if not paragraflar:
        return []

    parcalar = []

    ana_baslik = None
    alt_baslik = None

    tampon = []
    alt_gecmisi = []
    tampon_uzunluk = 0

    for index, paragraf in enumerate(paragraflar):

        metin_parcasi = paragraf["text"]
        baslik_metni = _baslik_mi(metin_parcasi)

        if baslik_metni:

            if index == 0:
                # Belgenin ilk paragrafı genellikle doküman
                # başlığıdır (örn. "DATA ENGINEER MÜLAKAT
                # NOTLARI"), bir bölüm başlığı olarak kullanılmaz.
                continue

            seviye = _markdown_seviyesi(metin_parcasi)

            yeni_ana_mi = (
                ana_baslik is None
                or seviye == 1
                or (seviye is None and paragraf["ana_gecis"])
            )

            if yeni_ana_mi:

                _parca_olustur(
                    parcalar, tampon, alt_gecmisi, ana_baslik
                )

                tampon = []
                alt_gecmisi = []
                tampon_uzunluk = 0

                ana_baslik = baslik_metni
                alt_baslik = baslik_metni

            else:
                alt_baslik = baslik_metni

            continue

        # Paragraf mevcut tampona sığıyorsa ekle
        if tampon_uzunluk + len(metin_parcasi) + 2 <= chunk_size:

            tampon.append(metin_parcasi)
            alt_gecmisi.append(alt_baslik)
            tampon_uzunluk += len(metin_parcasi) + 2

            continue

        # Sığmıyorsa mevcut tamponu parça olarak kapat
        _parca_olustur(
            parcalar, tampon, alt_gecmisi, ana_baslik
        )

        tampon = []
        alt_gecmisi = []
        tampon_uzunluk = 0

        # Çok uzun tek paragraf varsa ayrıca böl
        if len(metin_parcasi) > chunk_size:

            baslangic = 0

            while baslangic < len(metin_parcasi):

                bitis = min(
                    baslangic + chunk_size,
                    len(metin_parcasi)
                )

                parca = metin_parcasi[baslangic:bitis].strip()

                if parca:
                    _parca_olustur(
                        parcalar, [parca], [alt_baslik], ana_baslik
                    )

                if bitis >= len(metin_parcasi):
                    break

                baslangic = bitis - overlap

        else:
            tampon = [metin_parcasi]
            alt_gecmisi = [alt_baslik]
            tampon_uzunluk = len(metin_parcasi) + 2

    _parca_olustur(
        parcalar, tampon, alt_gecmisi, ana_baslik
    )

    return parcalar


# =========================================================
# EMBEDDING
# =========================================================

def embedding_olustur(metinler):
    """
    Metin listesini embedding vektörlerine çevirir.
    """

    if not metinler:
        return []

    embeddings = embedding_model.encode(
        metinler,
        normalize_embeddings=True
    )

    return embeddings.tolist()


# =========================================================
# CHROMA INDEX
# =========================================================

def index_olustur():

    print("\nCV okunuyor...")
    cv_metni = dosya_oku(CV_PATH)

    print("Mülakat notları okunuyor...")
    mulakat_metni = dosya_oku(
        MULAKAT_PATH
    )

    dokumanlar = []

    # -----------------------------------------------------
    # CV
    # -----------------------------------------------------

    cv_parcalari = belgeyi_parcala(
        cv_metni
    )

    for index, parca in enumerate(
        cv_parcalari
    ):

        dokumanlar.append(
            {
                "id": f"cv_{index}",
                "text": parca["text"],
                "source": "cv",
                "section": parca["section"],
                "major_section": parca["major_section"],
            }
        )

    # -----------------------------------------------------
    # MÜLAKAT NOTLARI
    # -----------------------------------------------------

    mulakat_parcalari = belgeyi_parcala(
        mulakat_metni
    )

    for index, parca in enumerate(
        mulakat_parcalari
    ):

        dokumanlar.append(
            {
                "id": f"mulakat_{index}",
                "text": parca["text"],
                "source": "mulakat_notlari",
                "section": parca["section"],
                "major_section": parca["major_section"],
            }
        )

    if not dokumanlar:

        print(
            "❌ Indexlenecek içerik bulunamadı."
        )

        return

    print(
        f"\nToplam {len(dokumanlar)} "
        "parça oluşturuldu."
    )

    # -----------------------------------------------------
    # EMBEDDING
    # -----------------------------------------------------

    metinler = [
        dokuman["text"]
        for dokuman in dokumanlar
    ]

    print(
        "Embedding'ler oluşturuluyor..."
    )

    embeddings = embedding_olustur(
        metinler
    )

    # -----------------------------------------------------
    # CHROMA
    # -----------------------------------------------------

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    # Eski index varsa sil
    try:
        client.delete_collection(
            name=COLLECTION_NAME
        )

        print(
            "Eski collection silindi."
        )

    except Exception:
        pass

    collection = (
        client.create_collection(
            name=COLLECTION_NAME,
            metadata={
                "description":
                    "Kariyer Copilotu RAG verileri"
            }
        )
    )

    ids = [
        dokuman["id"]
        for dokuman in dokumanlar
    ]

    metadatas = [
        {
            "source":
                dokuman["source"],
            "section":
                dokuman["section"],
            "major_section":
                dokuman["major_section"],
        }
        for dokuman in dokumanlar
    ]

    collection.add(
        ids=ids,
        documents=metinler,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    print(
        "\n✅ RAG index başarıyla oluşturuldu."
    )

    print(
        f"📁 ChromaDB: {CHROMA_DIR}"
    )

    print(
        f"📚 Collection: {COLLECTION_NAME}"
    )

    print(
        f"📄 Parça sayısı: {len(dokumanlar)}"
    )


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":
    index_olustur()
