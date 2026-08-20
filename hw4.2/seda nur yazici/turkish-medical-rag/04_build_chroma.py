from pathlib import Path
import time

import chromadb
import numpy as np
import pandas as pd


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path(
    "data/chunks_with_embeddings.parquet"
)

CHROMA_DIR = Path(
    "data/chroma_db"
)

COLLECTION_NAME = (
    "turkish_medical_chunks"
)


# ============================================================
# INDEX AYARLARI
# ============================================================

DISTANCE_METRIC = "cosine"

# Chroma'ya kaç kayıtlık batch'ler halinde veri gönderilecek?
INSERT_BATCH_SIZE = 250


# ============================================================
# COLLECTION YENİDEN OLUŞTURMA
# ============================================================

# True:
#   Script her çalıştırıldığında yalnızca bu collection
#   silinir ve baştan oluşturulur.
#
# Bu aşamada reproducibility açısından bunu istiyoruz.
#
# ChromaDB'nin tamamı silinmez.
# Yalnızca COLLECTION_NAME silinir.

RECREATE_COLLECTION = True


# ============================================================
# BAŞLANGIÇ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CHROMADB INDEX OLUŞTURMA"
)

print(
    "=" * 70
)


# ============================================================
# INPUT KONTROLÜ
# ============================================================

if not INPUT_FILE.exists():

    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı.\n"
        "Önce 03_embed_chunks.py çalıştırılmalıdır."
    )


# ============================================================
# VERİYİ OKU
# ============================================================

print(
    f"\nInput dosyası:\n"
    f"{INPUT_FILE}"
)


df = pd.read_parquet(
    INPUT_FILE
)


print(
    f"\nToplam kayıt sayısı: "
    f"{len(df)}"
)


if len(df) == 0:

    raise ValueError(
        "Input dosyasında hiç kayıt yok."
    )


# ============================================================
# GEREKLİ KOLONLAR
# ============================================================

required_columns = [
    "article_id",
    "parent_id",
    "parent_index",
    "child_id",
    "child_index",
    "url",
    "title",
    "parent_text",
    "chunk_text",
    "parent_token_count",
    "chunk_token_count",
    "embedding_model",
    "embedding_dimension",
    "chunk_vector",
]


missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]


if missing_columns:

    raise ValueError(
        "Eksik kolonlar bulundu:\n"
        + "\n".join(
            missing_columns
        )
    )


# ============================================================
# CHILD ID KONTROLÜ
# ============================================================

duplicate_mask = (
    df[
        "child_id"
    ]
    .duplicated(
        keep=False
    )
)


if duplicate_mask.any():

    duplicate_ids = (
        df.loc[
            duplicate_mask,
            "child_id"
        ]
        .tolist()
    )

    raise ValueError(
        "Duplicate child_id bulundu:\n"
        + "\n".join(
            duplicate_ids[:20]
        )
    )


print(
    "Child ID kontrolü: OK"
)


# ============================================================
# BOŞ DOCUMENT KONTROLÜ
# ============================================================

empty_document_mask = (
    df[
        "chunk_text"
    ]
    .fillna("")
    .astype(str)
    .str.strip()
    .eq("")
)


empty_document_count = int(
    empty_document_mask.sum()
)


if empty_document_count > 0:

    raise ValueError(
        f"{empty_document_count} adet "
        "boş chunk_text bulundu."
    )


print(
    "Boş document kontrolü: OK"
)


# ============================================================
# EMBEDDING MODEL KONTROLÜ
# ============================================================

embedding_models = (
    df[
        "embedding_model"
    ]
    .dropna()
    .astype(str)
    .unique()
)


if len(
    embedding_models
) != 1:

    raise ValueError(
        "Input içerisinde birden fazla "
        "embedding modeli bulundu:\n"
        f"{embedding_models}"
    )


EMBEDDING_MODEL = (
    embedding_models[0]
)


print(
    f"\nEmbedding modeli:\n"
    f"{EMBEDDING_MODEL}"
)


# ============================================================
# EMBEDDING DIMENSION KONTROLÜ
# ============================================================

embedding_dimensions = (
    df[
        "embedding_dimension"
    ]
    .dropna()
    .astype(int)
    .unique()
)


if len(
    embedding_dimensions
) != 1:

    raise ValueError(
        "Input içerisinde birden fazla "
        "embedding dimension bulundu:\n"
        f"{embedding_dimensions}"
    )


EMBEDDING_DIMENSION = int(
    embedding_dimensions[0]
)


print(
    f"Embedding dimension: "
    f"{EMBEDDING_DIMENSION}"
)


# ============================================================
# VECTORLERİ NUMPY ARRAY'E ÇEVİR
# ============================================================

print(
    "\nEmbedding vectorleri hazırlanıyor..."
)


try:

    embeddings = np.stack(
        [
            np.asarray(
                vector,
                dtype=np.float32
            )
            for vector in df[
                "chunk_vector"
            ]
        ]
    )

except Exception as error:

    raise ValueError(
        "chunk_vector kolonundaki "
        "embedding'ler numpy array'e "
        "çevrilemedi."
    ) from error


print(
    f"Embedding matrix shape: "
    f"{embeddings.shape}"
)


# ============================================================
# SHAPE KONTROLÜ
# ============================================================

expected_shape = (
    len(df),
    EMBEDDING_DIMENSION
)


if (
    embeddings.shape
    != expected_shape
):

    raise ValueError(
        "Embedding matrix shape hatalı.\n"
        f"Beklenen : {expected_shape}\n"
        f"Gelen    : {embeddings.shape}"
    )


print(
    "Embedding shape kontrolü: OK"
)


# ============================================================
# NaN / INF KONTROLÜ
# ============================================================

if not np.isfinite(
    embeddings
).all():

    raise ValueError(
        "Embedding vectorlerinde "
        "NaN veya Inf bulundu."
    )


print(
    "NaN / Inf kontrolü: OK"
)


# ============================================================
# L2 NORM KONTROLÜ
# ============================================================

embedding_norms = np.linalg.norm(
    embeddings,
    axis=1
)


print(
    "\nEmbedding norm istatistikleri:"
)


print(
    f"Ortalama : "
    f"{embedding_norms.mean():.8f}"
)


print(
    f"Minimum  : "
    f"{embedding_norms.min():.8f}"
)


print(
    f"Maksimum : "
    f"{embedding_norms.max():.8f}"
)


if not np.allclose(
    embedding_norms,
    1.0,
    atol=1e-5
):

    raise ValueError(
        "Embedding'lerin tamamı "
        "L2-normalize değil."
    )


print(
    "L2 normalization kontrolü: OK"
)


# ============================================================
# CHROMA KLASÖRÜ
# ============================================================

CHROMA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


print(
    "\n"
    + "=" * 70
)

print(
    "CHROMADB CLIENT"
)

print(
    "=" * 70
)


print(
    f"\nDatabase dizini:\n"
    f"{CHROMA_DIR}"
)


# ============================================================
# PERSISTENT CLIENT
# ============================================================

client = chromadb.PersistentClient(
    path=str(
        CHROMA_DIR
    )
)


print(
    "\nPersistentClient oluşturuldu."
)


# ============================================================
# CHROMA VERSION
# ============================================================

try:

    chroma_version = (
        client.get_version()
    )

    print(
        f"Chroma version: "
        f"{chroma_version}"
    )

except Exception:

    print(
        "Chroma version bilgisi "
        "alınamadı."
    )


# ============================================================
# MEVCUT COLLECTION'LAR
# ============================================================

existing_collections = (
    client.list_collections()
)


existing_collection_names = {
    collection.name
    for collection in existing_collections
}


print(
    "\nMevcut collection sayısı: "
    f"{len(existing_collection_names)}"
)


# ============================================================
# COLLECTION VARSA SİL
# ============================================================

if (
    COLLECTION_NAME
    in existing_collection_names
):

    if RECREATE_COLLECTION:

        print(
            f"\n'{COLLECTION_NAME}' "
            "zaten mevcut."
        )

        print(
            "Eski collection siliniyor..."
        )

        client.delete_collection(
            name=COLLECTION_NAME
        )

        print(
            "Eski collection silindi."
        )

    else:

        raise RuntimeError(
            f"'{COLLECTION_NAME}' "
            "collection'ı zaten mevcut.\n"
            "RECREATE_COLLECTION=True yapabilir "
            "veya farklı bir collection adı "
            "kullanabilirsin."
        )


# ============================================================
# COLLECTION OLUŞTUR
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "COLLECTION OLUŞTURULUYOR"
)

print(
    "=" * 70
)


print(
    f"\nCollection adı : "
    f"{COLLECTION_NAME}"
)


print(
    f"Distance metric: "
    f"{DISTANCE_METRIC}"
)


collection = client.create_collection(

    name=COLLECTION_NAME,

    # Embeddingleri zaten Qwen3 ile kendimiz ürettik.
    # Chroma'nın tekrar embedding üretmesini istemiyoruz.
    embedding_function=None,

    configuration={
        "hnsw": {
            "space": DISTANCE_METRIC
        }
    },

    metadata={
        "description": (
            "Turkish medical RAG child chunks"
        ),

        "embedding_model": (
            EMBEDDING_MODEL
        ),

        "embedding_dimension": (
            EMBEDDING_DIMENSION
        ),

        "distance_metric": (
            DISTANCE_METRIC
        ),

        "source_file": (
            str(INPUT_FILE)
        ),
    }
)


print(
    "\nCollection oluşturuldu."
)


# ============================================================
# BATCH SIZE
# ============================================================

batch_size = (
    INSERT_BATCH_SIZE
)


try:

    max_batch_size = (
        client.get_max_batch_size()
    )

    print(
        f"\nChroma max batch size: "
        f"{max_batch_size}"
    )

    batch_size = min(
        batch_size,
        max_batch_size
    )

except (AttributeError, NotImplementedError):

    print(
        "\nChroma max batch size "
        "bilgisi alınamadı."
    )


print(
    f"Kullanılacak insert batch size: "
    f"{batch_size}"
)


# ============================================================
# METADATA HAZIRLAMA YARDIMCILARI
# ============================================================

def safe_string(value):
    """
    Chroma metadata için None / NaN değerlerini
    güvenli string'e çevirir.
    """

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(
        value
    )


def safe_int(value):
    """
    Metadata için integer dönüşümü.
    """

    if value is None:
        return -1

    try:
        if pd.isna(value):
            return -1
    except (TypeError, ValueError):
        pass

    return int(
        value
    )


# ============================================================
# CHROMA METADATA
# ============================================================

print(
    "\nMetadata hazırlanıyor..."
)


metadatas = []


for _, row in df.iterrows():

    metadata = {

        # ----------------------------------------------------
        # ARTICLE
        # ----------------------------------------------------

        "article_id": (
            safe_string(
                row[
                    "article_id"
                ]
            )
        ),

        # ----------------------------------------------------
        # PARENT
        # ----------------------------------------------------

        "parent_id": (
            safe_string(
                row[
                    "parent_id"
                ]
            )
        ),

        "parent_index": (
            safe_int(
                row[
                    "parent_index"
                ]
            )
        ),

        # ----------------------------------------------------
        # CHILD
        # ----------------------------------------------------

        "child_index": (
            safe_int(
                row[
                    "child_index"
                ]
            )
        ),

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        "title": (
            safe_string(
                row[
                    "title"
                ]
            )
        ),

        "url": (
            safe_string(
                row[
                    "url"
                ]
            )
        ),

        # ----------------------------------------------------
        # TOKEN COUNTS
        # ----------------------------------------------------

        "parent_token_count": (
            safe_int(
                row[
                    "parent_token_count"
                ]
            )
        ),

        "chunk_token_count": (
            safe_int(
                row[
                    "chunk_token_count"
                ]
            )
        ),

        # ----------------------------------------------------
        # EMBEDDING
        # ----------------------------------------------------

        "embedding_model": (
            safe_string(
                row[
                    "embedding_model"
                ]
            )
        ),

        "embedding_dimension": (
            safe_int(
                row[
                    "embedding_dimension"
                ]
            )
        ),
    }


    # __source varsa ekle.
    if "__source" in df.columns:

        metadata[
            "source"
        ] = safe_string(
            row[
                "__source"
            ]
        )


    metadatas.append(
        metadata
    )


print(
    f"Metadata sayısı: "
    f"{len(metadatas)}"
)


# ============================================================
# IDS
# ============================================================

ids = (
    df[
        "child_id"
    ]
    .astype(str)
    .tolist()
)


# ============================================================
# DOCUMENTS
# ============================================================

documents = (
    df[
        "chunk_text"
    ]
    .astype(str)
    .tolist()
)


# ============================================================
# CHROMADB'YE EKLE
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CHROMADB'YE VERİ EKLENİYOR"
)

print(
    "=" * 70
)


insert_start = (
    time.perf_counter()
)


total_records = len(
    df
)


for start in range(
    0,
    total_records,
    batch_size
):

    end = min(
        start + batch_size,
        total_records
    )


    batch_ids = (
        ids[
            start:end
        ]
    )


    batch_documents = (
        documents[
            start:end
        ]
    )


    batch_metadatas = (
        metadatas[
            start:end
        ]
    )


    batch_embeddings = (
        embeddings[
            start:end
        ]
        .tolist()
    )


    collection.add(

        ids=batch_ids,

        embeddings=batch_embeddings,

        documents=batch_documents,

        metadatas=batch_metadatas,
    )


    print(
        f"{end}/{total_records} "
        "kayıt eklendi."
    )


insert_seconds = (
    time.perf_counter()
    - insert_start
)


# ============================================================
# COLLECTION COUNT
# ============================================================

stored_count = (
    collection.count()
)


print(
    "\n"
    + "=" * 70
)

print(
    "INDEX VALIDATION"
)

print(
    "=" * 70
)


print(
    f"\nInput kayıt sayısı : "
    f"{total_records}"
)


print(
    f"Chroma kayıt sayısı: "
    f"{stored_count}"
)


if (
    stored_count
    != total_records
):

    raise ValueError(
        "Chroma collection kayıt sayısı "
        "input ile eşleşmiyor."
    )


print(
    "\nCollection count kontrolü: OK"
)


# ============================================================
# KAYIT GERİ OKUMA TESTİ
# ============================================================

sample_id = (
    ids[0]
)


print(
    f"\nTest kaydı:\n"
    f"{sample_id}"
)


stored_sample = collection.get(

    ids=[
        sample_id
    ],

    include=[
        "documents",
        "metadatas",
        "embeddings",
    ],
)


if not stored_sample[
    "ids"
]:

    raise ValueError(
        "Test kaydı ChromaDB'den "
        "geri okunamadı."
    )


stored_vector = np.asarray(
    stored_sample[
        "embeddings"
    ][0],
    dtype=np.float32
)


if (
    len(stored_vector)
    != EMBEDDING_DIMENSION
):

    raise ValueError(
        "ChromaDB'den geri okunan "
        "embedding dimension hatalı."
    )


print(
    "Stored embedding dimension: "
    f"{len(stored_vector)}"
)


print(
    "Kayıt geri okuma kontrolü: OK"
)


# ============================================================
# SELF-SIMILARITY QUERY
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "COSINE SELF-QUERY TEST"
)

print(
    "=" * 70
)


sample_embedding = (
    embeddings[0]
)


self_query = collection.query(

    query_embeddings=[
        sample_embedding.tolist()
    ],

    n_results=min(
        10,
        total_records
    ),

    include=[
        "documents",
        "metadatas",
        "distances",
    ],
)


result_ids = (
    self_query[
        "ids"
    ][0]
)


result_distances = (
    self_query[
        "distances"
    ][0]
)


if not result_ids:

    raise ValueError(
        "Self-query herhangi bir "
        "sonuç döndürmedi."
    )


# ============================================================
# TEST DOCUMENT SONUÇLARDA MI?
# ============================================================

if (
    sample_id
    not in result_ids
):

    raise ValueError(
        "Self-query sonucunda kendi "
        "child_id'si ilk 10 içerisinde bulunamadı."
    )


sample_result_index = (
    result_ids.index(
        sample_id
    )
)


sample_distance = float(
    result_distances[
        sample_result_index
    ]
)


# Cosine distance:
#
# distance = 1 - cosine_similarity
#
# Dolayısıyla:
#
# similarity = 1 - distance

sample_similarity = (
    1.0
    - sample_distance
)


print(
    f"\nSample child ID:"
    f"\n{sample_id}"
)


print(
    f"\nSelf cosine distance:"
    f"\n{sample_distance:.8f}"
)


print(
    f"\nSelf cosine similarity:"
    f"\n{sample_similarity:.8f}"
)


print(
    "\nSelf-query kontrolü: OK"
)


# ============================================================
# TOP 5 SELF QUERY SONUCU
# ============================================================

print(
    "\n"
    + "-" * 70
)

print(
    "SELF-QUERY TOP 5"
)

print(
    "-" * 70
)


top_count = min(
    5,
    len(result_ids)
)


for rank in range(
    top_count
):

    result_id = (
        result_ids[
            rank
        ]
    )

    distance = float(
        result_distances[
            rank
        ]
    )

    similarity = (
        1.0
        - distance
    )


    result_metadata = (
        self_query[
            "metadatas"
        ][0][rank]
    )


    title = ""

    if result_metadata:

        title = (
            result_metadata.get(
                "title",
                ""
            )
        )


    print(
        f"""
#{rank + 1}

Child ID   : {result_id}
Başlık     : {title}
Distance   : {distance:.6f}
Similarity : {similarity:.6f}
"""
    )


# ============================================================
# PERFORMANS
# ============================================================

records_per_second = (
    total_records
    / insert_seconds
)


# ============================================================
# FINAL SONUÇ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CHROMADB INDEX TAMAMLANDI"
)

print(
    "=" * 70
)


print(
    f"""
Collection       : {COLLECTION_NAME}

Database path    : {CHROMA_DIR}

Kayıt sayısı     : {stored_count}

Embedding model  : {EMBEDDING_MODEL}

Embedding dim    : {EMBEDDING_DIMENSION}

Distance metric  : {DISTANCE_METRIC}

Indexleme süresi : {insert_seconds:.2f} saniye

Kayıt / saniye   : {records_per_second:.2f}
"""
)


print(
    "=" * 70
)

print(
    "04_BUILD_CHROMADB BAŞARILI"
)

print(
    "=" * 70
)