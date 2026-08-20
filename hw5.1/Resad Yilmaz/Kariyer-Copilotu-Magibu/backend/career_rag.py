from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# =========================================================
# YOLLAR
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

CHROMA_DIR = BASE_DIR / "chroma_db"


# =========================================================
# AYARLAR
# =========================================================

COLLECTION_NAME = "kariyer_bilgileri"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

DEFAULT_TOP_K = 5

# rag_ara top_k kadar sonuç döndürür, fakat sıralamayı iyileştirmek
# için Chroma'dan bundan daha geniş bir aday havuzu istenir. Bu
# sayede en iyi eşleşmenin ait olduğu bölümdeki diğer alakalı
# parçalar da (ör. "SQL" sorusunda "Window Functions" alt başlığı)
# değerlendirmeye girebilir. Bkz. _en_iyi_sonuclari_sec.
ADAY_HAVUZU_CARPANI = 4
ADAY_HAVUZU_MIN = 15


# =========================================================
# LAZY LOAD DEĞİŞKENLERİ
# =========================================================

_embedding_model = None
_chroma_client = None
_collection = None


# =========================================================
# EMBEDDING MODELİ
# =========================================================

def embedding_modelini_getir():
    """
    Sentence Transformer modelini yalnızca gerektiğinde yükler.

    Böylece career_rag.py import edildiği anda model tekrar
    yüklenmez.
    """

    global _embedding_model

    if _embedding_model is None:

        print("🔎 RAG embedding modeli yükleniyor...")

        _embedding_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME
        )

        print("✅ RAG embedding modeli hazır.")

    return _embedding_model


# =========================================================
# CHROMA CLIENT
# =========================================================

def collection_getir():
    """
    ChromaDB collection'ını açar.
    """

    global _chroma_client
    global _collection

    if _collection is not None:
        return _collection

    if not CHROMA_DIR.exists():

        raise FileNotFoundError(
            "ChromaDB klasörü bulunamadı. "
            "Önce 'python index_career.py' çalıştırılmalıdır."
        )

    _chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    _collection = _chroma_client.get_collection(
        name=COLLECTION_NAME
    )

    return _collection


# =========================================================
# QUERY EMBEDDING
# =========================================================

def soru_embeddingi_olustur(soru):
    """
    Kullanıcının sorusunu embedding vektörüne dönüştürür.
    """

    model = embedding_modelini_getir()

    embedding = model.encode(
        [soru],
        normalize_embeddings=True
    )

    return embedding.tolist()


# =========================================================
# BÖLÜM BAZLI YENİDEN SIRALAMA
# =========================================================

def _en_iyi_sonuclari_sec(adaylar, top_k):
    """
    Chroma'dan gelen (mesafeye göre sıralı) aday havuzundan en iyi
    top_k sonucu seçer.

    Sadece ham semantik mesafeye göre sıralamak yerine, en iyi
    eşleşmenin ait olduğu ana bölümdeki ("major_section") diğer
    adaylara öncelik verilir. Böylece örneğin "SQL" ile ilgili bir
    soruda, SQL ana bölümü altındaki tüm alt başlıklar (CTE, Window
    Functions, ROW_NUMBER, RANK, LAG, LEAD gibi) ETL, Kafka, FastAPI
    gibi alakasız bölümlerin önüne geçebilir. Bu mantık herhangi bir
    bölüm adına özel değildir; hangi bölümün "baskın" olduğu her
    sorguda en iyi eşleşmeye göre dinamik olarak belirlenir.
    """

    if not adaylar:
        return []

    baskin_ana_bolum = adaylar[0].get("ana_bolum")

    if not baskin_ana_bolum:
        return adaylar[:top_k]

    ayni_bolum = [
        aday for aday in adaylar
        if aday.get("ana_bolum") == baskin_ana_bolum
    ]

    diger_bolumler = [
        aday for aday in adaylar
        if aday.get("ana_bolum") != baskin_ana_bolum
    ]

    # Her iki grup da Chroma'nın döndürdüğü sırayı (artan mesafe)
    # korur; yalnızca gruplar arası öncelik değişir.
    sirali_adaylar = ayni_bolum + diger_bolumler

    return sirali_adaylar[:top_k]


# =========================================================
# RAG ARAMA
# =========================================================

def rag_ara(
    soru,
    top_k=DEFAULT_TOP_K,
    kaynak=None
):
    """
    Kariyer verileri içerisinde semantic search yapar.

    Kaynak seçenekleri:
        None
        "cv"
        "mulakat_notlari"

    Args:
        soru (str):
            Kullanıcının sorusu.

        top_k (int):
            Kaç sonuç getirileceği.

        kaynak (str | None):
            Aramanın yalnızca belirli bir kaynakta
            yapılmasını sağlar.

    Returns:
        dict:
            Bulunan ilgili metin parçaları.
    """

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not soru or not soru.strip():

        return {
            "basarili": False,
            "bulundu": False,
            "mesaj": "RAG araması için soru boş olamaz.",
            "sonuclar": [],
        }

    if top_k < 1:
        top_k = 1

    # Tool şeması top_k için 10'a kadar izin verse de, burada daha
    # sıkı bir üst sınır uygulanır. Yerel modelle yapılan testlerde
    # top_k=10 gibi büyük bir tool sonucu payload'ı modelin nihai
    # cevabında tutarsız/uydurma içerik üretmesine yol açabiliyor;
    # top_k=5 civarında ise tutarlı cevaplar alınıyor. 7, kapsamlı
    # sorular için biraz pay bırakırken bu riski sınırlıyor.
    if top_k > 7:
        top_k = 7

    try:

        collection = collection_getir()

        collection_count = collection.count()

        if collection_count == 0:

            return {
                "basarili": False,
                "bulundu": False,
                "mesaj": (
                    "RAG veritabanında herhangi bir "
                    "doküman bulunmuyor."
                ),
                "sonuclar": [],
            }

        # Sıralamayı iyileştirmek için top_k'dan daha geniş bir
        # aday havuzu istenir (bkz. _en_iyi_sonuclari_sec).
        # Collection'da bulunan kayıt sayısından fazlası
        # istenemez.
        aday_havuzu = min(
            collection_count,
            max(top_k * ADAY_HAVUZU_CARPANI, ADAY_HAVUZU_MIN)
        )

        query_embedding = (
            soru_embeddingi_olustur(
                soru.strip()
            )
        )

        # -------------------------------------------------
        # CHROMA QUERY
        # -------------------------------------------------

        query_args = {
            "query_embeddings":
                query_embedding,

            "n_results":
                aday_havuzu,

            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        # Kullanıcı yalnızca CV veya yalnızca
        # mülakat notlarında aramak isterse.
        if kaynak:

            if kaynak not in [
                "cv",
                "mulakat_notlari"
            ]:

                return {
                    "basarili": False,
                    "bulundu": False,
                    "mesaj": (
                        "Geçersiz kaynak. "
                        "Kaynak 'cv' veya "
                        "'mulakat_notlari' olmalıdır."
                    ),
                    "sonuclar": [],
                }

            query_args["where"] = {
                "source": kaynak
            }

        results = collection.query(
            **query_args
        )

        # -------------------------------------------------
        # SONUÇLARI AYIKLA
        # -------------------------------------------------

        documents = (
            results.get("documents", [[]])[0]
            or []
        )

        metadatas = (
            results.get("metadatas", [[]])[0]
            or []
        )

        distances = (
            results.get("distances", [[]])[0]
            or []
        )

        if not documents:

            return {
                "basarili": True,
                "bulundu": False,
                "soru": soru,
                "mesaj": (
                    "Bu soruyla ilgili RAG verisinde "
                    "uygun içerik bulunamadı."
                ),
                "sonuclar": [],
            }

        adaylar = []

        for index, document in enumerate(
            documents
        ):

            metadata = {}

            if index < len(metadatas):
                metadata = (
                    metadatas[index] or {}
                )

            distance = None

            if index < len(distances):
                distance = distances[index]

            adaylar.append(
                {
                    "kaynak": metadata.get(
                        "source",
                        "bilinmiyor"
                    ),
                    "ana_bolum": metadata.get(
                        "major_section"
                    ),
                    "mesafe": distance,
                    "icerik": document,
                }
            )

        secilenler = _en_iyi_sonuclari_sec(
            adaylar, top_k
        )

        sonuclar = []

        for index, aday in enumerate(
            secilenler
        ):

            sonuclar.append(
                {
                    "sira": index + 1,
                    "kaynak": aday["kaynak"],
                    "mesafe": aday["mesafe"],
                    "icerik": aday["icerik"],
                }
            )

        # -------------------------------------------------
        # LLM İÇİN CONTEXT
        # -------------------------------------------------

        context_parcalari = []

        for sonuc in sonuclar:

            context_parcalari.append(
                (
                    f"[Kaynak: "
                    f"{sonuc['kaynak']}]\n"
                    f"{sonuc['icerik']}"
                )
            )

        context = "\n\n---\n\n".join(
            context_parcalari
        )

        en_iyi_mesafe = None

        if sonuclar:
            en_iyi_mesafe = sonuclar[0]["mesafe"]

        return {
            "basarili": True,
            "bulundu": True,
            "soru": soru,
            "adet": len(sonuclar),
            "en_iyi_mesafe":
                en_iyi_mesafe,
            "sonuclar": sonuclar,
            "context": context,
        }

    except Exception as hata:

        return {
            "basarili": False,
            "bulundu": False,
            "mesaj": (
                "RAG araması sırasında hata oluştu: "
                f"{str(hata)}"
            ),
            "sonuclar": [],
        }


# =========================================================
# MANUEL TEST
# =========================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("🔎 KARİYER RAG TESTİ")
    print("=" * 60)

    soru = (
        "Adayın Data Engineering alanında "
        "hangi deneyimleri var?"
    )

    print(
        f"\nSoru: {soru}\n"
    )

    sonuc = rag_ara(
        soru=soru,
        top_k=5
    )

    if not sonuc.get("basarili"):

        print(
            "❌ Hata:",
            sonuc.get("mesaj")
        )

    elif not sonuc.get("bulundu"):

        print(
            "⚠️ Sonuç bulunamadı."
        )

    else:

        print(
            f"✅ {sonuc['adet']} "
            "ilgili parça bulundu.\n"
        )

        for item in sonuc["sonuclar"]:

            print(
                "-" * 60
            )

            print(
                f"Sıra: {item['sira']}"
            )

            print(
                f"Kaynak: {item['kaynak']}"
            )

            print(
                f"Mesafe: {item['mesafe']}"
            )

            print(
                "\nİçerik:"
            )

            print(
                item["icerik"]
            )

            print()
