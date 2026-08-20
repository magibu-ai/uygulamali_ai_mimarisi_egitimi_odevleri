from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import torch

from sentence_transformers import SentenceTransformer


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path(
    "data/chunks_parent_child.parquet"
)

OUTPUT_FILE = Path(
    "data/chunks_with_embeddings.parquet"
)


# ============================================================
# EMBEDDING MODELİ
# ============================================================

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

EXPECTED_EMBEDDING_DIMENSION = 1024


# ============================================================
# DEVICE / BATCH SIZE
# ============================================================

if torch.cuda.is_available():

    DEVICE = "cuda"

    # RTX 4050 Laptop 6 GB için güvenli değer.
    BATCH_SIZE = 8

else:

    DEVICE = "cpu"

    BATCH_SIZE = 4


# ============================================================
# INPUT KONTROLÜ
# ============================================================

if not INPUT_FILE.exists():

    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı.\n"
        "Önce 02_chunk_articles.py çalıştırılmalıdır."
    )


# ============================================================
# BAŞLANGIÇ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CHUNK EMBEDDING"
)

print(
    "=" * 70
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
    f"\nToplam child sayısı: "
    f"{len(df)}"
)


# ============================================================
# GEREKLİ KOLON KONTROLÜ
# ============================================================

required_columns = [
    "article_id",
    "parent_id",
    "child_id",
    "url",
    "title",
    "parent_text",
    "chunk_text",
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

duplicate_child_mask = (
    df["child_id"]
    .duplicated(
        keep=False
    )
)


if duplicate_child_mask.any():

    duplicated_ids = (
        df.loc[
            duplicate_child_mask,
            "child_id"
        ]
        .tolist()
    )

    raise ValueError(
        "Duplicate child_id bulundu:\n"
        + "\n".join(
            duplicated_ids[:20]
        )
    )


# ============================================================
# BOŞ CHUNK KONTROLÜ
# ============================================================

empty_chunk_mask = (
    df["chunk_text"]
    .fillna("")
    .astype(str)
    .str.strip()
    .eq("")
)


empty_chunk_count = int(
    empty_chunk_mask.sum()
)


if empty_chunk_count > 0:

    raise ValueError(
        f"{empty_chunk_count} adet "
        "boş chunk_text bulundu."
    )


# ============================================================
# METİNLERİ HAZIRLA
# ============================================================

texts = (
    df["chunk_text"]
    .astype(str)
    .tolist()
)


print(
    f"\nEmbed edilecek metin sayısı: "
    f"{len(texts)}"
)


# ============================================================
# DEVICE BİLGİSİ
# ============================================================

print(
    "\n"
    + "-" * 70
)


print(
    f"Device     : {DEVICE}"
)


if DEVICE == "cuda":

    gpu_name = (
        torch.cuda.get_device_name(0)
    )

    gpu_memory_gb = (
        torch.cuda.get_device_properties(
            0
        ).total_memory
        / (1024 ** 3)
    )

    print(
        f"GPU        : {gpu_name}"
    )

    print(
        f"GPU VRAM   : "
        f"{gpu_memory_gb:.2f} GB"
    )


print(
    f"Batch size : {BATCH_SIZE}"
)


# ============================================================
# MODELİ YÜKLE
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "MODEL YÜKLENİYOR"
)

print(
    "=" * 70
)


print(
    f"\nModel:\n"
    f"{MODEL_NAME}"
)


model_load_start = (
    time.perf_counter()
)


model = SentenceTransformer(
    MODEL_NAME,
    device=DEVICE
)


model_load_seconds = (
    time.perf_counter()
    - model_load_start
)


print(
    "\nModel yüklendi."
)


print(
    f"Model yükleme süresi: "
    f"{model_load_seconds:.2f} saniye"
)


# ============================================================
# EMBEDDING DIMENSION
# ============================================================

model_dimension = (
    model.get_embedding_dimension()
)


print(
    f"Model embedding dimension: "
    f"{model_dimension}"
)


if (
    model_dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Beklenmeyen embedding dimension.\n"
        f"Beklenen : "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen    : "
        f"{model_dimension}"
    )


# ============================================================
# EMBEDDING ÜRETİMİ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "EMBEDDING ÜRETİLİYOR"
)

print(
    "=" * 70
)


print(
    "\nDocument embedding üretiliyor..."
)


print(
    "Document tarafına query instruction "
    "eklenmiyor."
)


embedding_start = (
    time.perf_counter()
)


with torch.inference_mode():

    embeddings = model.encode(
        texts,

        batch_size=BATCH_SIZE,

        show_progress_bar=True,

        convert_to_numpy=True,

        normalize_embeddings=True,
    )


embedding_seconds = (
    time.perf_counter()
    - embedding_start
)


# ============================================================
# FLOAT32 GARANTİSİ
# ============================================================

embeddings = np.asarray(
    embeddings,
    dtype=np.float32
)


# ============================================================
# SHAPE KONTROLÜ
# ============================================================

expected_shape = (
    len(df),
    EXPECTED_EMBEDDING_DIMENSION
)


if embeddings.shape != expected_shape:

    raise ValueError(
        "Embedding shape beklenenden farklı.\n"
        f"Beklenen : {expected_shape}\n"
        f"Gelen    : {embeddings.shape}"
    )


# ============================================================
# NaN / INF KONTROLÜ
# ============================================================

if not np.isfinite(
    embeddings
).all():

    raise ValueError(
        "Embedding içerisinde "
        "NaN veya Inf bulundu."
    )


# ============================================================
# MODEL ÇIKTISININ İLK NORM KONTROLÜ
# ============================================================

norms_before = np.linalg.norm(
    embeddings,
    axis=1
)


print(
    "\nModel çıktısı norm değerleri:"
)


print(
    f"Ortalama norm : "
    f"{norms_before.mean():.6f}"
)


print(
    f"Min norm      : "
    f"{norms_before.min():.6f}"
)


print(
    f"Max norm      : "
    f"{norms_before.max():.6f}"
)


# ============================================================
# SIFIR NORMLU VECTOR KONTROLÜ
# ============================================================

if np.any(
    norms_before == 0
):

    zero_norm_count = int(
        np.sum(
            norms_before == 0
        )
    )

    raise ValueError(
        f"{zero_norm_count} adet "
        "sıfır normlu embedding bulundu."
    )


# ============================================================
# KESİN FLOAT32 L2 NORMALIZATION
# ============================================================

# Model normalize_embeddings=True ile zaten normalize ediyor.
#
# Fakat GPU / düşük precision hesaplamaları nedeniyle:
#
# 0.998
# 1.003
#
# gibi çok küçük sapmalar oluşabiliyor.
#
# Cosine retrieval öncesinde tüm vectorleri float32
# seviyesinde tekrar unit norm yapıyoruz.

norms_before_2d = np.linalg.norm(
    embeddings,
    axis=1,
    keepdims=True
)


embeddings = (
    embeddings
    / norms_before_2d
).astype(
    np.float32
)


# ============================================================
# FINAL NORMALIZATION KONTROLÜ
# ============================================================

norms_after = np.linalg.norm(
    embeddings,
    axis=1
)


print(
    "\nFloat32 L2 normalization sonrası:"
)


print(
    f"Ortalama norm : "
    f"{norms_after.mean():.8f}"
)


print(
    f"Min norm      : "
    f"{norms_after.min():.8f}"
)


print(
    f"Max norm      : "
    f"{norms_after.max():.8f}"
)


# Float32 için yeterince sıkı kontrol.
if not np.allclose(
    norms_after,
    1.0,
    atol=1e-5
):

    max_deviation = float(
        np.max(
            np.abs(
                norms_after
                - 1.0
            )
        )
    )

    raise ValueError(
        "Embedding'ler float32 normalization "
        "sonrasında unit norm değil.\n"
        f"Maksimum sapma: "
        f"{max_deviation}"
    )


# ============================================================
# EMBEDDING SONUÇLARI
# ============================================================

print(
    "\nEmbedding üretimi tamamlandı."
)


print(
    f"Shape      : "
    f"{embeddings.shape}"
)


print(
    f"Data type  : "
    f"{embeddings.dtype}"
)


print(
    f"Süre       : "
    f"{embedding_seconds:.2f} saniye"
)


# ============================================================
# PERFORMANS
# ============================================================

chunks_per_second = (
    len(df)
    / embedding_seconds
)


milliseconds_per_chunk = (
    embedding_seconds
    / len(df)
    * 1000
)


print(
    f"\nChunk / saniye : "
    f"{chunks_per_second:.2f}"
)


print(
    f"ms / chunk     : "
    f"{milliseconds_per_chunk:.2f}"
)


# ============================================================
# OUTPUT DATAFRAME
# ============================================================

output_df = (
    df.copy()
)


# ============================================================
# EMBEDDING METADATA
# ============================================================

output_df[
    "embedding_model"
] = MODEL_NAME


output_df[
    "embedding_dimension"
] = (
    EXPECTED_EMBEDDING_DIMENSION
)


# ============================================================
# OUTPUT DİZİNİ
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PYARROW TABLE
# ============================================================

# Önce embedding haricindeki kolonları
# Arrow Table'a çeviriyoruz.

table = pa.Table.from_pandas(
    output_df,
    preserve_index=False
)


# ============================================================
# EMBEDDING VECTOR -> LIST<FLOAT32>
# ============================================================

# Parquet içerisinde vectorün açık biçimde
# float32 listesi olarak saklanmasını istiyoruz.

vector_array = pa.array(
    embeddings.tolist(),

    type=pa.list_(
        pa.float32()
    )
)


table = table.append_column(
    "chunk_vector",
    vector_array
)


# ============================================================
# PARQUET KAYDET
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "PARQUET KAYDEDİLİYOR"
)

print(
    "=" * 70
)


pq.write_table(
    table,
    OUTPUT_FILE,
    compression="snappy"
)


print(
    f"\nKaydedildi:\n"
    f"{OUTPUT_FILE}"
)


# ============================================================
# DOSYAYI GERİ OKUYARAK VALIDATION
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "OUTPUT VALIDATION"
)

print(
    "=" * 70
)


check_df = pd.read_parquet(
    OUTPUT_FILE
)


# ============================================================
# SATIR SAYISI KONTROLÜ
# ============================================================

if len(check_df) != len(df):

    raise ValueError(
        "Kaydedilen satır sayısı "
        "input ile eşleşmiyor.\n"
        f"Input : {len(df)}\n"
        f"Output: {len(check_df)}"
    )


# ============================================================
# VECTOR KOLONU KONTROLÜ
# ============================================================

if (
    "chunk_vector"
    not in check_df.columns
):

    raise ValueError(
        "chunk_vector kolonu "
        "output dosyasında bulunamadı."
    )


# ============================================================
# İLK VECTOR KONTROLÜ
# ============================================================

first_vector = np.asarray(
    check_df.iloc[0][
        "chunk_vector"
    ],
    dtype=np.float32
)


if (
    len(first_vector)
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Kaydedilen embedding dimension yanlış.\n"
        f"Beklenen : "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen    : "
        f"{len(first_vector)}"
    )


# ============================================================
# OUTPUT VECTOR NORM KONTROLÜ
# ============================================================

first_vector_norm = (
    np.linalg.norm(
        first_vector
    )
)


if not np.isclose(
    first_vector_norm,
    1.0,
    atol=1e-5
):

    raise ValueError(
        "Parquet'ten okunan embedding "
        "unit norm değil.\n"
        f"Norm: {first_vector_norm}"
    )


# ============================================================
# ÖDEVDE ZORUNLU KOLONLAR
# ============================================================

homework_required_columns = [
    "url",
    "chunk_text",
    "chunk_vector",
]


missing_homework_columns = [
    column
    for column in homework_required_columns
    if column not in check_df.columns
]


if missing_homework_columns:

    raise ValueError(
        "Ödev için gerekli kolonlar eksik:\n"
        + "\n".join(
            missing_homework_columns
        )
    )


# ============================================================
# VECTOR UZUNLUKLARINI KONTROL ET
# ============================================================

print(
    "\nTüm vector dimension değerleri "
    "kontrol ediliyor..."
)


vector_lengths = (
    check_df[
        "chunk_vector"
    ]
    .apply(len)
)


invalid_vector_count = int(
    (
        vector_lengths
        != EXPECTED_EMBEDDING_DIMENSION
    ).sum()
)


if invalid_vector_count > 0:

    raise ValueError(
        f"{invalid_vector_count} adet "
        "hatalı dimension'a sahip vector bulundu."
    )


print(
    "Tüm vector dimension değerleri doğru."
)


# ============================================================
# DOSYA BOYUTU
# ============================================================

file_size_mb = (
    OUTPUT_FILE.stat().st_size
    / (1024 ** 2)
)


# ============================================================
# OUTPUT ŞEMASI
# ============================================================

print(
    "\nOutput kolonları:"
)


for column in check_df.columns:

    print(
        f"  - {column}"
    )


# ============================================================
# ÖDEV KOLONLARI
# ============================================================

print(
    "\nÖdev için gerekli kolonlar:"
)


for column in homework_required_columns:

    print(
        f"  ✓ {column}"
    )


# ============================================================
# ÖRNEK
# ============================================================

example = (
    check_df.iloc[0]
)


example_vector = np.asarray(
    example[
        "chunk_vector"
    ],
    dtype=np.float32
)


# ============================================================
# FINAL SONUÇ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "EMBEDDING SONUÇLARI"
)

print(
    "=" * 70
)


print(
    f"\nOutput dosyası:\n"
    f"{OUTPUT_FILE}"
)


print(
    f"\nDosya boyutu : "
    f"{file_size_mb:.2f} MB"
)


print(
    f"Satır sayısı : "
    f"{len(check_df)}"
)


print(
    f"Model        : "
    f"{MODEL_NAME}"
)


print(
    f"Dimension    : "
    f"{len(example_vector)}"
)


print(
    f"Vector dtype : "
    f"{example_vector.dtype}"
)


print(
    f"Vector norm  : "
    f"{np.linalg.norm(example_vector):.8f}"
)


# ============================================================
# ÖRNEK EMBEDDING
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "ÖRNEK EMBEDDING"
)

print(
    "=" * 70
)


print(
    f"""
Article ID : {example['article_id']}
Parent ID  : {example['parent_id']}
Child ID   : {example['child_id']}
Başlık     : {example['title']}

Chunk:

{example['chunk_text']}

Vector dimension:
{len(example_vector)}

Vector norm:
{np.linalg.norm(example_vector):.8f}

Vector'ın ilk 10 değeri:
{example_vector[:10]}
"""
)


# ============================================================
# TAMAMLANDI
# ============================================================

print(
    "=" * 70
)

print(
    "EMBEDDING AŞAMASI TAMAMLANDI"
)

print(
    "=" * 70
)