from pathlib import Path
import pandas as pd


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path("data/chunks_parent_child.parquet")

# Bunlar silme/birleştirme sınırları değil.
# Sadece incelemek istediğimiz küçük chunkları bulmak için.
SMALL_CHILD_THRESHOLD = 100
SMALL_PARENT_THRESHOLD = 200

SHOW_COUNT = 30


# ============================================================
# DOSYAYI OKU
# ============================================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı."
    )

df = pd.read_parquet(INPUT_FILE)

print(f"Toplam child sayısı : {len(df)}")
print(f"Toplam parent sayısı: {df['parent_id'].nunique()}")
print(f"Toplam makale sayısı: {df['article_id'].nunique()}")


# ============================================================
# CHILD SIRA BİLGİSİ
# ============================================================

# Her parent içerisinde kaç child olduğunu hesapla
df["child_count_in_parent"] = (
    df.groupby("parent_id")["child_id"]
    .transform("count")
)


# Child id'nin sonundaki sıra numarasını al
df["child_order"] = (
    df["child_id"]
    .str.extract(r"_child_(\d+)$")[0]
    .astype(int)
)


# Bu child parent'ın son child'ı mı?
df["is_last_child"] = (
    df["child_order"]
    == df["child_count_in_parent"]
)


# ============================================================
# PARENT SIRA BİLGİSİ
# ============================================================

parents = (
    df[
        [
            "article_id",
            "parent_id",
            "title",
            "url",
            "parent_text",
            "parent_token_count"
        ]
    ]
    .drop_duplicates("parent_id")
    .copy()
)


parents["parent_order"] = (
    parents["parent_id"]
    .str.extract(r"_parent_(\d+)$")[0]
    .astype(int)
)


parents["parent_count_in_article"] = (
    parents.groupby("article_id")["parent_id"]
    .transform("count")
)


parents["is_last_parent"] = (
    parents["parent_order"]
    == parents["parent_count_in_article"]
)


# ============================================================
# KÜÇÜK CHILD'LAR
# ============================================================

small_children = (
    df[
        df["chunk_token_count"]
        < SMALL_CHILD_THRESHOLD
    ]
    .sort_values("chunk_token_count")
    .copy()
)


print("\n" + "=" * 80)
print("KÜÇÜK CHILD ANALİZİ")
print("=" * 80)

print(
    f"\n{SMALL_CHILD_THRESHOLD} tokendan küçük child sayısı: "
    f"{len(small_children)}"
)

print(
    "Toplam child içindeki oranı: "
    f"%{len(small_children) / len(df) * 100:.2f}"
)


if len(small_children) > 0:

    print(
        "\nBunların kaç tanesi parent'ın son child'ı?"
    )

    print(
        small_children["is_last_child"]
        .value_counts()
    )

    print("\nToken dağılımı:")

    print(
        small_children["chunk_token_count"]
        .describe()
        .round(2)
    )


# ============================================================
# EN KÜÇÜK CHILD'LARI TAM METİN İLE GÖSTER
# ============================================================

print("\n" + "=" * 80)
print(f"EN KÜÇÜK {min(SHOW_COUNT, len(small_children))} CHILD")
print("=" * 80)


for i, (_, row) in enumerate(
    small_children.head(SHOW_COUNT).iterrows(),
    start=1
):

    print("\n" + "-" * 80)

    print(f"#{i}")
    print(f"Makale        : {row['article_id']}")
    print(f"Başlık        : {row['title']}")
    print(f"Parent        : {row['parent_id']}")
    print(f"Child         : {row['child_id']}")
    print(f"Token         : {row['chunk_token_count']}")
    print(f"Son child mı? : {row['is_last_child']}")

    print("\nCHUNK TEXT:")
    print(row["chunk_text"])


# ============================================================
# KÜÇÜK PARENT'LAR
# ============================================================

small_parents = (
    parents[
        parents["parent_token_count"]
        < SMALL_PARENT_THRESHOLD
    ]
    .sort_values("parent_token_count")
    .copy()
)


print("\n\n" + "=" * 80)
print("KÜÇÜK PARENT ANALİZİ")
print("=" * 80)

print(
    f"\n{SMALL_PARENT_THRESHOLD} tokendan küçük parent sayısı: "
    f"{len(small_parents)}"
)

print(
    "Toplam parent içindeki oranı: "
    f"%{len(small_parents) / len(parents) * 100:.2f}"
)


if len(small_parents) > 0:

    print(
        "\nBunların kaç tanesi makalenin son parent'ı?"
    )

    print(
        small_parents["is_last_parent"]
        .value_counts()
    )

    print("\nToken dağılımı:")

    print(
        small_parents["parent_token_count"]
        .describe()
        .round(2)
    )


# ============================================================
# EN KÜÇÜK PARENT'LARI TAM METİN İLE GÖSTER
# ============================================================

print("\n" + "=" * 80)
print(f"EN KÜÇÜK {min(SHOW_COUNT, len(small_parents))} PARENT")
print("=" * 80)


for i, (_, row) in enumerate(
    small_parents.head(SHOW_COUNT).iterrows(),
    start=1
):

    print("\n" + "-" * 80)

    print(f"#{i}")
    print(f"Makale         : {row['article_id']}")
    print(f"Başlık         : {row['title']}")
    print(f"Parent         : {row['parent_id']}")
    print(f"Token          : {row['parent_token_count']}")
    print(f"Son parent mı? : {row['is_last_parent']}")

    print("\nPARENT TEXT:")
    print(row["parent_text"])


# ============================================================
# CSV OLARAK DA KAYDET
# ============================================================

analysis_dir = Path("analysis")
analysis_dir.mkdir(exist_ok=True)

small_children.to_csv(
    analysis_dir / "small_children.csv",
    index=False,
    encoding="utf-8-sig"
)

small_parents.to_csv(
    analysis_dir / "small_parents.csv",
    index=False,
    encoding="utf-8-sig"
)


print("\n" + "=" * 80)
print("ANALİZ TAMAMLANDI")
print("=" * 80)

print(
    "\nAyrıntılı listeler:"
)

print(
    "analysis/small_children.csv"
)

print(
    "analysis/small_parents.csv"
)