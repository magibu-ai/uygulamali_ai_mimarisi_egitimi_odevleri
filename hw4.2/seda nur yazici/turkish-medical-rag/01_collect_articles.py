from huggingface_hub import hf_hub_download
import pandas as pd
from pathlib import Path


# ============================================================
# AYARLAR
# ============================================================

DATASET_ID = "umutertugrul/turkish-hospital-medical-articles"
SOURCE_FILE = "memorial.parquet"

ARTICLE_COUNT = 500
RANDOM_SEED = 42

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "articles_500.parquet"


# ============================================================
# OUTPUT KLASÖRÜ
# ============================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# PARQUET DOSYASINI HUGGING FACE'TEN İNDİR
# ============================================================

print("Memorial makale dosyası Hugging Face'ten indiriliyor...")

parquet_path = hf_hub_download(
    repo_id=DATASET_ID,
    filename=SOURCE_FILE,
    repo_type="dataset"
)

print("Dosya başarıyla indirildi.")
print(f"Cache konumu: {parquet_path}")


# ============================================================
# PARQUET DOSYASINI PANDAS İLE OKU
# ============================================================

print("\nParquet dosyası okunuyor...")

df = pd.read_parquet(parquet_path)

print("Parquet başarıyla okundu.")

print(f"\nToplam makale sayısı: {len(df)}")

print("\nDataset kolonları:")
for column in df.columns:
    print(f" - {column}")


# ============================================================
# ZORUNLU KOLON KONTROLÜ
# ============================================================

required_columns = [
    "url",
    "title",
    "text"
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Eksik zorunlu kolonlar: {missing_columns}"
    )


# ============================================================
# VERİ TEMİZLEME
# ============================================================

print("\nVeri temizleniyor...")


# URL veya text boş olan kayıtları kaldır
df = df.dropna(
    subset=[
        "url",
        "text"
    ]
).copy()


# String alanlarını temizle
df["url"] = (
    df["url"]
    .astype(str)
    .str.strip()
)

df["title"] = (
    df["title"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df["text"] = (
    df["text"]
    .astype(str)
    .str.strip()
)


# Tamamen boş URL veya text varsa çıkar
df = df[
    (df["url"] != "")
    &
    (df["text"] != "")
].copy()


# Çok kısa içerikleri çıkar
df = df[
    df["text"].str.len() >= 500
].copy()


# Aynı URL tekrar ediyorsa tek kayıt bırak
df = df.drop_duplicates(
    subset=["url"]
).reset_index(drop=True)


print(
    f"Temizlik sonrası kullanılabilir makale sayısı: {len(df)}"
)


# ============================================================
# 500 MAKALE RASTGELE SEÇ
# ============================================================

if len(df) < ARTICLE_COUNT:
    raise ValueError(
        f"{ARTICLE_COUNT} makale isteniyor ancak "
        f"temizlik sonrasında yalnızca {len(df)} makale kaldı."
    )


df_sample = df.sample(
    n=ARTICLE_COUNT,
    random_state=RANDOM_SEED
).reset_index(drop=True)


# ============================================================
# HER MAKALEYE ID VER
# ============================================================

df_sample.insert(
    0,
    "parent_id",
    [
        f"doc_{i:04d}"
        for i in range(1, ARTICLE_COUNT + 1)
    ]
)


# ============================================================
# SAKLANACAK KOLONLAR
# ============================================================

columns_to_keep = [
    "parent_id",
    "url",
    "title",
    "text",
    "publish_date",
    "update_date",
    "scrape_date",
    "__source"
]


# Dataset'te gerçekten var olan kolonları seç
columns_to_keep = [
    column
    for column in columns_to_keep
    if column in df_sample.columns
]


df_sample = df_sample[
    columns_to_keep
].copy()


# ============================================================
# PARQUET OLARAK KAYDET
# ============================================================

df_sample.to_parquet(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# KONTROL BİLGİLERİ
# ============================================================

print("\n" + "=" * 70)
print("VERİ TOPLAMA TAMAMLANDI")
print("=" * 70)

print(f"\nKaynak dataset : {DATASET_ID}")
print(f"Kaynak hastane : Memorial")
print(f"Makale sayısı  : {len(df_sample)}")
print(f"Çıktı dosyası  : {OUTPUT_FILE}")


print("\nKaydedilen kolonlar:")

for column in df_sample.columns:
    print(f" - {column}")


print("\nİlk 5 makale:\n")

print(
    df_sample[
        [
            "parent_id",
            "title",
            "url"
        ]
    ].head().to_string(index=False)
)


# ============================================================
# BASİT İSTATİSTİKLER
# ============================================================

df_sample["text_length"] = (
    df_sample["text"]
    .str.len()
)

print("\nMetin uzunluğu istatistikleri:")

print(
    df_sample["text_length"]
    .describe()
    .round(2)
)


print("\nTamamlandı.")