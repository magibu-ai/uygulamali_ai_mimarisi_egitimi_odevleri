from pathlib import Path
import re

import pandas as pd


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path("data/chunks_parent_child.parquet")

ANALYSIS_DIR = Path("analysis")
ANALYSIS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    ANALYSIS_DIR
    / "content_quality_suspects.csv"
)

MIN_QUESTION_COUNT = 3


# ============================================================
# VERİYİ OKU
# ============================================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı."
    )


df = pd.read_parquet(
    INPUT_FILE
)


print(
    f"Toplam child sayısı: {len(df)}"
)


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def count_questions(text):
    """
    Chunk içerisindeki soru işareti sayısını hesaplar.
    """

    if not isinstance(text, str):
        return 0

    return text.count("?")


def count_dash_questions(text):
    """
    '- ...?' biçimindeki soru/list item sayısını bulur.

    Örnek:
        - Angelman sendromu nedir?
        - Angelman sendromu riskleri nelerdir?
    """

    if not isinstance(text, str):
        return 0

    matches = re.findall(
        r"(?:^|\s)-\s+[^?]{2,150}\?",
        text
    )

    return len(matches)


def extract_questions(text):
    """
    Chunk içerisindeki soru cümlelerini çıkarır.
    Analiz için kullanılır.
    """

    if not isinstance(text, str):
        return []

    matches = re.findall(
        r"[^?.!]{2,180}\?",
        text
    )

    questions = []

    for match in matches:

        question = (
            match
            .strip()
            .lstrip("-•* ")
            .strip()
        )

        if question:
            questions.append(
                question
            )

    return questions


def normalize_text(text):
    """
    Basit tekrar kontrolü için normalize eder.
    """

    text = str(text).casefold()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def has_repeated_short_phrase(text):
    """
    Aynı kısa ifadenin hâlâ açık biçimde art arda
    bulunup bulunmadığını kontrol eder.

    Bu sadece kalite analizi içindir.
    """

    if not isinstance(text, str):
        return False

    normalized = normalize_text(
        text
    )

    # 2-10 kelimelik phrase'in hemen iki kez
    # art arda gelmesi.
    pattern = re.compile(
        r"\b"
        r"((?:[\wçğıöşüİÇĞÖŞÜ'-]+\s+){1,9}"
        r"[\wçğıöşüİÇĞÖŞÜ'-]+)"
        r"[\s;,:-]+"
        r"\1\b",
        flags=re.IGNORECASE
    )

    return bool(
        pattern.search(
            normalized
        )
    )


# ============================================================
# ANALİZ KOLONLARI
# ============================================================

analysis_df = df.copy()


analysis_df[
    "question_count"
] = (
    analysis_df[
        "chunk_text"
    ]
    .apply(
        count_questions
    )
)


analysis_df[
    "dash_question_count"
] = (
    analysis_df[
        "chunk_text"
    ]
    .apply(
        count_dash_questions
    )
)


analysis_df[
    "questions"
] = (
    analysis_df[
        "chunk_text"
    ]
    .apply(
        extract_questions
    )
)


analysis_df[
    "possible_internal_duplicate"
] = (
    analysis_df[
        "chunk_text"
    ]
    .apply(
        has_repeated_short_phrase
    )
)


# ============================================================
# ŞÜPHELİ CHUNK'LARI SEÇ
# ============================================================

suspects = (
    analysis_df[
        (
            analysis_df[
                "question_count"
            ]
            >= MIN_QUESTION_COUNT
        )
        |
        (
            analysis_df[
                "dash_question_count"
            ]
            >= 2
        )
        |
        (
            analysis_df[
                "possible_internal_duplicate"
            ]
        )
    ]
    .copy()
)


# ============================================================
# GENEL İSTATİSTİKLER
# ============================================================

three_plus_questions = (
    analysis_df[
        analysis_df[
            "question_count"
        ]
        >= MIN_QUESTION_COUNT
    ]
)


two_plus_dash_questions = (
    analysis_df[
        analysis_df[
            "dash_question_count"
        ]
        >= 2
    ]
)


internal_duplicates = (
    analysis_df[
        analysis_df[
            "possible_internal_duplicate"
        ]
    ]
)


print(
    "\n"
    + "=" * 80
)

print(
    "CONTENT QUALITY ANALİZİ"
)

print(
    "=" * 80
)


print(
    "\n3+ soru işareti bulunan child sayısı:"
)

print(
    len(
        three_plus_questions
    )
)


print(
    "\n2+ '- ...?' biçiminde soru bulunan child sayısı:"
)

print(
    len(
        two_plus_dash_questions
    )
)


print(
    "\nOlası ardışık phrase tekrarı bulunan child sayısı:"
)

print(
    len(
        internal_duplicates
    )
)


print(
    "\nToplam şüpheli unique child sayısı:"
)

print(
    len(
        suspects
    )
)


print(
    "\nŞüpheli child oranı:"
)

print(
    f"%{len(suspects) / len(df) * 100:.2f}"
)


# ============================================================
# EN FAZLA SORU İÇEREN CHUNK'LAR
# ============================================================

question_suspects = (
    analysis_df[
        analysis_df[
            "question_count"
        ]
        >= MIN_QUESTION_COUNT
    ]
    .sort_values(
        "question_count",
        ascending=False
    )
)


print(
    "\n"
    + "=" * 80
)

print(
    "EN FAZLA SORU İÇEREN CHUNK'LAR"
)

print(
    "=" * 80
)


for i, (_, row) in enumerate(
    question_suspects
    .head(20)
    .iterrows(),
    start=1
):

    print(
        "\n"
        + "-" * 80
    )

    print(
        f"#{i}"
    )

    print(
        f"Makale     : {row['article_id']}"
    )

    print(
        f"Başlık     : {row['title']}"
    )

    print(
        f"Parent     : {row['parent_id']}"
    )

    print(
        f"Child      : {row['child_id']}"
    )

    print(
        f"Token      : {row['chunk_token_count']}"
    )

    print(
        f"Soru sayısı: {row['question_count']}"
    )

    print(
        f"Dash soru  : {row['dash_question_count']}"
    )

    print(
        "\nSorular:"
    )

    for question in row[
        "questions"
    ]:

        print(
            f" - {question}"
        )

    print(
        "\nCHUNK TEXT:"
    )

    print(
        row[
            "chunk_text"
        ]
    )


# ============================================================
# OLASI DUPLICATE CHUNK'LAR
# ============================================================

print(
    "\n\n"
    + "=" * 80
)

print(
    "OLASI INTERNAL DUPLICATE ÖRNEKLERİ"
)

print(
    "=" * 80
)


for i, (_, row) in enumerate(
    internal_duplicates
    .head(20)
    .iterrows(),
    start=1
):

    print(
        "\n"
        + "-" * 80
    )

    print(
        f"#{i}"
    )

    print(
        f"Başlık : {row['title']}"
    )

    print(
        f"Child  : {row['child_id']}"
    )

    print(
        "\nCHUNK TEXT:"
    )

    print(
        row[
            "chunk_text"
        ]
    )


# ============================================================
# CSV KAYDET
# ============================================================

columns_to_save = [
    "article_id",
    "parent_id",
    "child_id",
    "title",
    "url",
    "chunk_token_count",
    "question_count",
    "dash_question_count",
    "possible_internal_duplicate",
    "questions",
    "chunk_text"
]


suspects[
    columns_to_save
].to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)


print(
    "\n"
    + "=" * 80
)

print(
    "ANALİZ TAMAMLANDI"
)

print(
    "=" * 80
)


print(
    f"\nSonuç dosyası:"
)

print(
    OUTPUT_FILE
)