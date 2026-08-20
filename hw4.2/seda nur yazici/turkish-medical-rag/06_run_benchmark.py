from pathlib import Path
import re
import time

import chromadb
import numpy as np
import pandas as pd
import torch

from sentence_transformers import SentenceTransformer


# ============================================================
# AYARLAR
# ============================================================

QUESTIONS_FILE = Path(
    "data/benchmark_questions.txt"
)

SOURCE_FILE = Path(
    "data/chunks_with_embeddings.parquet"
)

CHROMA_DIR = Path(
    "data/chroma_db"
)

COLLECTION_NAME = (
    "turkish_medical_chunks"
)


# ============================================================
# OUTPUT
# ============================================================

SUMMARY_OUTPUT_FILE = Path(
    "analysis/benchmark_results.csv"
)

DETAIL_OUTPUT_FILE = Path(
    "analysis/benchmark_detailed_results.csv"
)

PARENT_OUTPUT_FILE = Path(
    "analysis/benchmark_parent_results.csv"
)


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = (
    "Qwen/Qwen3-Embedding-0.6B"
)

EXPECTED_EMBEDDING_DIMENSION = 1024


# ============================================================
# BENCHMARK AYARLARI
# ============================================================

EXPECTED_TOTAL_QUESTIONS = 30
EXPECTED_POSITIVE_QUESTIONS = 20
EXPECTED_NEGATIVE_QUESTIONS = 10

TOP_K_CHILDREN = 10
TOP_K_PARENTS = 5

QUERY_BATCH_SIZE = 8


# ============================================================
# DEVICE
# ============================================================

if torch.cuda.is_available():

    DEVICE = "cuda"

else:

    DEVICE = "cpu"


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def cosine_distance_to_similarity(
    distance
):
    """
    Chroma cosine distance:
        distance = 1 - cosine_similarity

    Dolayısıyla:
        similarity = 1 - distance
    """

    similarity = (
        1.0
        - float(distance)
    )

    # Floating point sapmalarına karşı.
    similarity = max(
        -1.0,
        min(
            1.0,
            similarity
        )
    )

    return similarity


def normalize_embeddings(
    embeddings
):
    """
    Embedding matrixini float32 seviyesinde
    kesin L2 normalize eder.
    """

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32
    )


    if embeddings.ndim != 2:

        raise ValueError(
            "Embedding matrix 2 boyutlu olmalıdır.\n"
            f"Gelen shape: {embeddings.shape}"
        )


    if not np.isfinite(
        embeddings
    ).all():

        raise ValueError(
            "Query embedding içerisinde "
            "NaN veya Inf bulundu."
        )


    norms = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True
    )


    if np.any(
        norms == 0
    ):

        raise ValueError(
            "Sıfır normlu query embedding bulundu."
        )


    normalized = (
        embeddings
        / norms
    ).astype(
        np.float32
    )


    return normalized


def preview_text(
    text,
    max_chars=500
):
    """
    CSV ve console çıktılarında çok uzun
    metinleri kısaltmak için kullanılır.
    """

    if text is None:
        return ""

    text = str(
        text
    ).strip()


    if len(text) <= max_chars:

        return text


    return (
        text[:max_chars]
        .rstrip()
        + " ..."
    )


# ============================================================
# BENCHMARK TXT OKUMA
# ============================================================

def parse_benchmark_questions(
    file_path
):
    """
    benchmark_questions.txt dosyasını okuyup:

        positive
        negative

    etiketlerini otomatik çıkarır.

    Beklenen yapı:

        POZİTİF SORULAR
        1. ...
        2. ...

        NEGATİF SORULAR
        21. ...
        22. ...
    """

    text = file_path.read_text(
        encoding="utf-8"
    )


    lines = text.splitlines()


    question_pattern = re.compile(
        r"^\s*(\d+)\.\s*(.+?)\s*$"
    )


    current_type = None

    questions = []

    current_question_number = None

    current_question_parts = []


    def save_current_question():

        nonlocal current_question_number
        nonlocal current_question_parts


        if (
            current_question_number
            is None
        ):

            return


        question_text = (
            " ".join(
                current_question_parts
            )
            .strip()
        )


        if not question_text:

            raise ValueError(
                "Boş benchmark sorusu bulundu:\n"
                f"{current_question_number}"
            )


        questions.append(
            {
                "question_number": (
                    current_question_number
                ),

                "question_type": (
                    current_type
                ),

                "question": (
                    question_text
                ),
            }
        )


        current_question_number = None
        current_question_parts = []


    for raw_line in lines:

        line = raw_line.strip()


        # ----------------------------------------------------
        # SECTION
        # ----------------------------------------------------

        upper_line = (
            line.upper()
        )


        if (
            "POZİTİF SORULAR"
            in upper_line
        ):

            save_current_question()

            current_type = (
                "positive"
            )

            continue


        if (
            "NEGATİF SORULAR"
            in upper_line
        ):

            save_current_question()

            current_type = (
                "negative"
            )

            continue


        # ----------------------------------------------------
        # SECTION BAŞLAMADIYSA IGNORE
        # ----------------------------------------------------

        if current_type is None:

            continue


        # ----------------------------------------------------
        # BOŞ / SEPARATOR
        # ----------------------------------------------------

        if not line:

            continue


        if set(line) == {"="}:

            continue


        # ----------------------------------------------------
        # SORU
        # ----------------------------------------------------

        match = (
            question_pattern.match(
                line
            )
        )


        if match:

            save_current_question()


            current_question_number = int(
                match.group(1)
            )


            current_question_parts = [
                match.group(2)
            ]


            continue


        # ----------------------------------------------------
        # ÇOK SATIRLI SORU DESTEĞİ
        # ----------------------------------------------------

        if (
            current_question_number
            is not None
        ):

            current_question_parts.append(
                line
            )


    save_current_question()


    return questions


# ============================================================
# BAŞLANGIÇ
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "06 - 30 SORULUK RETRIEVAL BENCHMARK"
)

print(
    "=" * 80
)


# ============================================================
# DOSYA KONTROLLERİ
# ============================================================

if not QUESTIONS_FILE.exists():

    raise FileNotFoundError(
        f"{QUESTIONS_FILE} bulunamadı."
    )


if not SOURCE_FILE.exists():

    raise FileNotFoundError(
        f"{SOURCE_FILE} bulunamadı.\n"
        "Önce 03_embed_chunks.py çalıştırılmalıdır."
    )


if not CHROMA_DIR.exists():

    raise FileNotFoundError(
        f"{CHROMA_DIR} bulunamadı.\n"
        "Önce 04_build_chroma.py çalıştırılmalıdır."
    )


# ============================================================
# SORULARI OKU
# ============================================================

print(
    f"\nBenchmark dosyası:\n"
    f"{QUESTIONS_FILE}"
)


questions = (
    parse_benchmark_questions(
        QUESTIONS_FILE
    )
)


questions_df = pd.DataFrame(
    questions
)


# ============================================================
# BENCHMARK VALIDATION
# ============================================================

total_count = len(
    questions_df
)


positive_count = int(
    (
        questions_df[
            "question_type"
        ]
        == "positive"
    ).sum()
)


negative_count = int(
    (
        questions_df[
            "question_type"
        ]
        == "negative"
    ).sum()
)


print(
    f"\nToplam soru   : "
    f"{total_count}"
)


print(
    f"Pozitif soru  : "
    f"{positive_count}"
)


print(
    f"Negatif soru  : "
    f"{negative_count}"
)


if (
    total_count
    != EXPECTED_TOTAL_QUESTIONS
):

    raise ValueError(
        "Benchmark toplam soru sayısı yanlış.\n"
        f"Beklenen: "
        f"{EXPECTED_TOTAL_QUESTIONS}\n"
        f"Gelen   : "
        f"{total_count}"
    )


if (
    positive_count
    != EXPECTED_POSITIVE_QUESTIONS
):

    raise ValueError(
        "Pozitif soru sayısı yanlış.\n"
        f"Beklenen: "
        f"{EXPECTED_POSITIVE_QUESTIONS}\n"
        f"Gelen   : "
        f"{positive_count}"
    )


if (
    negative_count
    != EXPECTED_NEGATIVE_QUESTIONS
):

    raise ValueError(
        "Negatif soru sayısı yanlış.\n"
        f"Beklenen: "
        f"{EXPECTED_NEGATIVE_QUESTIONS}\n"
        f"Gelen   : "
        f"{negative_count}"
    )


# ============================================================
# SORU NUMARASI KONTROLÜ
# ============================================================

expected_numbers = list(
    range(
        1,
        EXPECTED_TOTAL_QUESTIONS + 1
    )
)


actual_numbers = (
    questions_df[
        "question_number"
    ]
    .astype(int)
    .tolist()
)


if (
    actual_numbers
    != expected_numbers
):

    raise ValueError(
        "Benchmark soru numaraları "
        "1-30 şeklinde sıralı değil.\n"
        f"Gelen:\n{actual_numbers}"
    )


print(
    "\nBenchmark TXT validation: OK"
)


# ============================================================
# SORULARI GÖSTER
# ============================================================

print(
    "\n"
    + "-" * 80
)

print(
    "BENCHMARK SORULARI"
)

print(
    "-" * 80
)


for _, row in (
    questions_df.iterrows()
):

    print(
        f"{row['question_number']:>2}. "
        f"[{row['question_type'].upper():8}] "
        f"{row['question']}"
    )


# ============================================================
# SOURCE PARQUET
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "SOURCE VERİ YÜKLENİYOR"
)

print(
    "=" * 80
)


df = pd.read_parquet(
    SOURCE_FILE
)


print(
    f"\nToplam child: "
    f"{len(df)}"
)


# ============================================================
# GEREKLİ KOLONLAR
# ============================================================

required_columns = [
    "article_id",
    "parent_id",
    "child_id",
    "title",
    "url",
    "parent_text",
    "chunk_text",
    "parent_token_count",
    "chunk_token_count",
    "embedding_model",
    "embedding_dimension",
]


missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]


if missing_columns:

    raise ValueError(
        "Source parquet içerisinde "
        "eksik kolonlar bulundu:\n"
        + "\n".join(
            missing_columns
        )
    )


# ============================================================
# MODEL KONTROLÜ
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
        "Birden fazla document "
        "embedding modeli bulundu."
    )


DOCUMENT_MODEL = (
    embedding_models[0]
)


if (
    DOCUMENT_MODEL
    != MODEL_NAME
):

    raise ValueError(
        "Document ve query modeli eşleşmiyor.\n"
        f"Document: {DOCUMENT_MODEL}\n"
        f"Query   : {MODEL_NAME}"
    )


# ============================================================
# DIMENSION KONTROLÜ
# ============================================================

dimensions = (
    df[
        "embedding_dimension"
    ]
    .dropna()
    .astype(int)
    .unique()
)


if len(
    dimensions
) != 1:

    raise ValueError(
        "Birden fazla embedding "
        "dimension bulundu."
    )


DOCUMENT_DIMENSION = int(
    dimensions[0]
)


if (
    DOCUMENT_DIMENSION
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Document embedding dimension yanlış.\n"
        f"Beklenen: "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen   : "
        f"{DOCUMENT_DIMENSION}"
    )


print(
    f"\nEmbedding model:"
    f"\n{DOCUMENT_MODEL}"
)


print(
    f"Embedding dimension: "
    f"{DOCUMENT_DIMENSION}"
)


# ============================================================
# PARENT CONSISTENCY
# ============================================================

parent_text_counts = (
    df
    .groupby(
        "parent_id"
    )[
        "parent_text"
    ]
    .nunique(
        dropna=False
    )
)


invalid_parents = (
    parent_text_counts[
        parent_text_counts > 1
    ]
)


if len(
    invalid_parents
) > 0:

    raise ValueError(
        f"{len(invalid_parents)} parent_id için "
        "birden fazla parent_text bulundu."
    )


# ============================================================
# PARENT LOOKUP
# ============================================================

parent_df = (
    df[
        [
            "parent_id",
            "article_id",
            "title",
            "url",
            "parent_text",
            "parent_token_count",
        ]
    ]
    .drop_duplicates(
        subset=[
            "parent_id"
        ]
    )
    .copy()
)


parent_lookup = (
    parent_df
    .set_index(
        "parent_id"
    )
    .to_dict(
        orient="index"
    )
)


print(
    f"Unique parent: "
    f"{len(parent_lookup)}"
)


# ============================================================
# CHROMADB
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "CHROMADB YÜKLENİYOR"
)

print(
    "=" * 80
)


client = chromadb.PersistentClient(
    path=str(
        CHROMA_DIR
    )
)


collection = client.get_collection(
    name=COLLECTION_NAME,
    embedding_function=None,
)


collection_count = (
    collection.count()
)


print(
    f"\nCollection:"
    f"\n{COLLECTION_NAME}"
)


print(
    f"Chroma kayıt sayısı: "
    f"{collection_count}"
)


if (
    collection_count
    != len(df)
):

    raise ValueError(
        "Chroma ve parquet kayıt "
        "sayıları eşleşmiyor.\n"
        f"Chroma : "
        f"{collection_count}\n"
        f"Parquet: "
        f"{len(df)}"
    )


print(
    "Chroma validation: OK"
)


# ============================================================
# QUERY MODEL
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "QUERY EMBEDDING MODELİ"
)

print(
    "=" * 80
)


print(
    f"\nDevice: "
    f"{DEVICE}"
)


if DEVICE == "cuda":

    print(
        f"GPU   : "
        f"{torch.cuda.get_device_name(0)}"
    )


model_start = (
    time.perf_counter()
)


model = SentenceTransformer(
    MODEL_NAME,
    device=DEVICE,
)


model_load_seconds = (
    time.perf_counter()
    - model_start
)


print(
    f"\nModel yüklendi: "
    f"{model_load_seconds:.2f} saniye"
)


model_dimension = (
    model.get_embedding_dimension()
)


if (
    model_dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Query model embedding "
        "dimension yanlış."
    )


# ============================================================
# TÜM SORULARI EMBED ET
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "30 QUERY EMBEDDING ÜRETİLİYOR"
)

print(
    "=" * 80
)


question_texts = (
    questions_df[
        "question"
    ]
    .astype(str)
    .tolist()
)


embedding_start = (
    time.perf_counter()
)


with torch.inference_mode():

    query_embeddings = model.encode(

        question_texts,

        prompt_name="query",

        batch_size=QUERY_BATCH_SIZE,

        show_progress_bar=True,

        convert_to_numpy=True,

        normalize_embeddings=True,
    )


embedding_seconds = (
    time.perf_counter()
    - embedding_start
)


# ============================================================
# FLOAT32 NORMALIZATION
# ============================================================

query_embeddings = (
    normalize_embeddings(
        query_embeddings
    )
)


# ============================================================
# SHAPE VALIDATION
# ============================================================

expected_query_shape = (
    EXPECTED_TOTAL_QUESTIONS,
    EXPECTED_EMBEDDING_DIMENSION,
)


if (
    query_embeddings.shape
    != expected_query_shape
):

    raise ValueError(
        "Query embedding matrix "
        "shape hatalı.\n"
        f"Beklenen: "
        f"{expected_query_shape}\n"
        f"Gelen   : "
        f"{query_embeddings.shape}"
    )


# ============================================================
# NORM VALIDATION
# ============================================================

query_norms = np.linalg.norm(
    query_embeddings,
    axis=1
)


print(
    f"\nQuery embedding shape: "
    f"{query_embeddings.shape}"
)


print(
    f"Embedding süresi: "
    f"{embedding_seconds:.2f} saniye"
)


print(
    f"Ortalama norm: "
    f"{query_norms.mean():.8f}"
)


print(
    f"Min norm     : "
    f"{query_norms.min():.8f}"
)


print(
    f"Max norm     : "
    f"{query_norms.max():.8f}"
)


if not np.allclose(
    query_norms,
    1.0,
    atol=1e-5
):

    raise ValueError(
        "Query embeddingleri "
        "L2-normalize değil."
    )


# ============================================================
# CHROMA BATCH QUERY
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "CHROMA BENCHMARK SEARCH"
)

print(
    "=" * 80
)


search_start = (
    time.perf_counter()
)


results = collection.query(

    query_embeddings=(
        query_embeddings.tolist()
    ),

    n_results=TOP_K_CHILDREN,

    include=[
        "documents",
        "metadatas",
        "distances",
    ],
)


search_seconds = (
    time.perf_counter()
    - search_start
)


print(
    f"\n30 soru Chroma search süresi: "
    f"{search_seconds:.3f} saniye"
)


print(
    f"Ortalama search / soru: "
    f"{search_seconds / total_count * 1000:.2f} ms"
)


# ============================================================
# RESULT SHAPE KONTROLÜ
# ============================================================

if (
    len(
        results[
            "ids"
        ]
    )
    != total_count
):

    raise ValueError(
        "Chroma tüm sorular için "
        "sonuç döndürmedi."
    )


# ============================================================
# SONUÇ TABLOLARI
# ============================================================

summary_rows = []

detail_rows = []

parent_rows = []


# ============================================================
# HER SORUYU İŞLE
# ============================================================

for query_index in range(
    total_count
):

    question_row = (
        questions_df.iloc[
            query_index
        ]
    )


    question_number = int(
        question_row[
            "question_number"
        ]
    )


    question_type = str(
        question_row[
            "question_type"
        ]
    )


    question = str(
        question_row[
            "question"
        ]
    )


    result_ids = (
        results[
            "ids"
        ][
            query_index
        ]
    )


    result_documents = (
        results[
            "documents"
        ][
            query_index
        ]
    )


    result_metadatas = (
        results[
            "metadatas"
        ][
            query_index
        ]
    )


    result_distances = (
        results[
            "distances"
        ][
            query_index
        ]
    )


    if not result_ids:

        raise ValueError(
            "Soru için hiçbir retrieval "
            "sonucu bulunamadı:\n"
            f"{question}"
        )


    # ========================================================
    # CHILD RESULTS
    # ========================================================

    child_results = []


    for rank, (
        child_id,
        document,
        metadata,
        distance,
    ) in enumerate(

        zip(
            result_ids,
            result_documents,
            result_metadatas,
            result_distances,
        ),

        start=1
    ):

        if metadata is None:

            metadata = {}


        similarity = (
            cosine_distance_to_similarity(
                distance
            )
        )


        child_result = {

            "rank": rank,

            "child_id": str(
                child_id
            ),

            "parent_id": str(
                metadata.get(
                    "parent_id",
                    ""
                )
            ),

            "article_id": str(
                metadata.get(
                    "article_id",
                    ""
                )
            ),

            "title": str(
                metadata.get(
                    "title",
                    ""
                )
            ),

            "url": str(
                metadata.get(
                    "url",
                    ""
                )
            ),

            "distance": float(
                distance
            ),

            "similarity": float(
                similarity
            ),

            "chunk_text": str(
                document
            ),
        }


        child_results.append(
            child_result
        )


        # ----------------------------------------------------
        # DETAILED CSV
        # ----------------------------------------------------

        detail_rows.append(
            {
                "question_number": (
                    question_number
                ),

                "question_type": (
                    question_type
                ),

                "question": (
                    question
                ),

                "child_rank": (
                    rank
                ),

                "similarity": (
                    similarity
                ),

                "distance": (
                    float(
                        distance
                    )
                ),

                "child_id": (
                    child_result[
                        "child_id"
                    ]
                ),

                "parent_id": (
                    child_result[
                        "parent_id"
                    ]
                ),

                "article_id": (
                    child_result[
                        "article_id"
                    ]
                ),

                "title": (
                    child_result[
                        "title"
                    ]
                ),

                "url": (
                    child_result[
                        "url"
                    ]
                ),

                "chunk_text": (
                    child_result[
                        "chunk_text"
                    ]
                ),
            }
        )


    # ========================================================
    # UNIQUE PARENT RANKING
    # ========================================================

    best_parent_results = {}


    for child in child_results:

        parent_id = (
            child[
                "parent_id"
            ]
        )


        if not parent_id:

            continue


        if (
            parent_id
            not in parent_lookup
        ):

            raise ValueError(
                "Chroma parent_id Parquet "
                "içerisinde bulunamadı:\n"
                f"{parent_id}"
            )


        current = (
            best_parent_results.get(
                parent_id
            )
        )


        if (
            current is None
            or child[
                "similarity"
            ]
            > current[
                "similarity"
            ]
        ):

            parent_info = (
                parent_lookup[
                    parent_id
                ]
            )


            best_parent_results[
                parent_id
            ] = {

                "parent_id": (
                    parent_id
                ),

                "article_id": (
                    parent_info[
                        "article_id"
                    ]
                ),

                "title": (
                    parent_info[
                        "title"
                    ]
                ),

                "url": (
                    parent_info[
                        "url"
                    ]
                ),

                "parent_text": (
                    parent_info[
                        "parent_text"
                    ]
                ),

                "parent_token_count": (
                    parent_info[
                        "parent_token_count"
                    ]
                ),

                "best_child_id": (
                    child[
                        "child_id"
                    ]
                ),

                "similarity": (
                    child[
                        "similarity"
                    ]
                ),
            }


    ranked_parents = sorted(

        best_parent_results.values(),

        key=lambda item: (
            item[
                "similarity"
            ]
        ),

        reverse=True,
    )


    ranked_parents = (
        ranked_parents[
            :TOP_K_PARENTS
        ]
    )


    # ========================================================
    # PARENT CSV
    # ========================================================

    for parent_rank, parent in enumerate(
        ranked_parents,
        start=1
    ):

        parent_rows.append(
            {
                "question_number": (
                    question_number
                ),

                "question_type": (
                    question_type
                ),

                "question": (
                    question
                ),

                "parent_rank": (
                    parent_rank
                ),

                "similarity": (
                    parent[
                        "similarity"
                    ]
                ),

                "parent_id": (
                    parent[
                        "parent_id"
                    ]
                ),

                "article_id": (
                    parent[
                        "article_id"
                    ]
                ),

                "best_child_id": (
                    parent[
                        "best_child_id"
                    ]
                ),

                "title": (
                    parent[
                        "title"
                    ]
                ),

                "url": (
                    parent[
                        "url"
                    ]
                ),

                "parent_token_count": (
                    parent[
                        "parent_token_count"
                    ]
                ),

                "parent_text": (
                    parent[
                        "parent_text"
                    ]
                ),
            }
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    top1_child = (
        child_results[0]
    )


    top1_parent = (
        ranked_parents[0]
        if ranked_parents
        else None
    )


    summary_row = {

        "question_number": (
            question_number
        ),

        "question_type": (
            question_type
        ),

        "question": (
            question
        ),

        "top1_similarity": (
            top1_child[
                "similarity"
            ]
        ),

        "top1_distance": (
            top1_child[
                "distance"
            ]
        ),

        "top1_child_id": (
            top1_child[
                "child_id"
            ]
        ),

        "top1_parent_id": (
            top1_child[
                "parent_id"
            ]
        ),

        "top1_title": (
            top1_child[
                "title"
            ]
        ),

        "top1_url": (
            top1_child[
                "url"
            ]
        ),

        "top1_chunk_preview": (
            preview_text(
                top1_child[
                    "chunk_text"
                ],
                700
            )
        ),
    }


    # --------------------------------------------------------
    # TOP PARENT INFO
    # --------------------------------------------------------

    if (
        top1_parent
        is not None
    ):

        summary_row[
            "top_parent_id"
        ] = (
            top1_parent[
                "parent_id"
            ]
        )


        summary_row[
            "top_parent_title"
        ] = (
            top1_parent[
                "title"
            ]
        )


        summary_row[
            "top_parent_similarity"
        ] = (
            top1_parent[
                "similarity"
            ]
        )


        summary_row[
            "top_parent_preview"
        ] = preview_text(
            top1_parent[
                "parent_text"
            ],
            900
        )


    # --------------------------------------------------------
    # TOP 5 PARENT BAŞLIKLARI
    # --------------------------------------------------------

    for parent_rank in range(
        1,
        TOP_K_PARENTS + 1
    ):

        index = (
            parent_rank - 1
        )


        if (
            index
            < len(
                ranked_parents
            )
        ):

            parent = (
                ranked_parents[
                    index
                ]
            )


            summary_row[
                f"parent_{parent_rank}_title"
            ] = (
                parent[
                    "title"
                ]
            )


            summary_row[
                f"parent_{parent_rank}_similarity"
            ] = (
                parent[
                    "similarity"
                ]
            )


        else:

            summary_row[
                f"parent_{parent_rank}_title"
            ] = ""


            summary_row[
                f"parent_{parent_rank}_similarity"
            ] = np.nan


    summary_rows.append(
        summary_row
    )


    # ========================================================
    # CONSOLE
    # ========================================================

    print(
        "\n"
        + "-" * 80
    )


    print(
        f"{question_number:02d}. "
        f"[{question_type.upper()}]"
    )


    print(
        question
    )


    print(
        f"\nTop-1 similarity : "
        f"{top1_child['similarity']:.6f}"
    )


    print(
        f"Top-1 title      : "
        f"{top1_child['title']}"
    )


    print(
        f"Top-1 child      : "
        f"{top1_child['child_id']}"
    )


    if top1_parent:

        print(
            f"Top parent       : "
            f"{top1_parent['parent_id']}"
        )


# ============================================================
# DATAFRAMES
# ============================================================

summary_df = pd.DataFrame(
    summary_rows
)


detail_df = pd.DataFrame(
    detail_rows
)


parents_result_df = pd.DataFrame(
    parent_rows
)


# ============================================================
# OUTPUT DİZİNİ
# ============================================================

SUMMARY_OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CSV KAYDET
# ============================================================

summary_df.to_csv(
    SUMMARY_OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
)


detail_df.to_csv(
    DETAIL_OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
)


parents_result_df.to_csv(
    PARENT_OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# SCORE SUMMARY
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "BENCHMARK TOP-1 SONUÇLARI"
)

print(
    "=" * 80
)


display_columns = [
    "question_number",
    "question_type",
    "question",
    "top1_similarity",
    "top1_title",
]


print(
    summary_df[
        display_columns
    ]
    .to_string(
        index=False
    )
)


# ============================================================
# POZİTİF / NEGATİF İSTATİSTİK
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "POZİTİF / NEGATİF SIMILARITY DAĞILIMI"
)

print(
    "=" * 80
)


score_stats = (
    summary_df
    .groupby(
        "question_type"
    )[
        "top1_similarity"
    ]
    .agg(
        [
            "count",
            "mean",
            "std",
            "min",
            "median",
            "max",
        ]
    )
    .round(6)
)


print(
    score_stats
)


# ============================================================
# AYRIM ANALİZİ
# ============================================================

positive_scores = (
    summary_df.loc[
        summary_df[
            "question_type"
        ]
        == "positive",
        "top1_similarity"
    ]
)


negative_scores = (
    summary_df.loc[
        summary_df[
            "question_type"
        ]
        == "negative",
        "top1_similarity"
    ]
)


positive_min = float(
    positive_scores.min()
)


negative_max = float(
    negative_scores.max()
)


score_gap = (
    positive_min
    - negative_max
)


print(
    "\n"
    + "=" * 80
)

print(
    "POZİTİF / NEGATİF AYRIMI"
)

print(
    "=" * 80
)


print(
    f"\nEn düşük pozitif similarity : "
    f"{positive_min:.6f}"
)


print(
    f"En yüksek negatif similarity: "
    f"{negative_max:.6f}"
)


print(
    f"Aradaki gap                  : "
    f"{score_gap:.6f}"
)


if score_gap > 0:

    print(
        "\nPozitif ve negatif skorlar "
        "bu benchmark üzerinde ayrışıyor."
    )

else:

    print(
        "\nPozitif ve negatif similarity "
        "dağılımları birbiriyle örtüşüyor."
    )


# ============================================================
# EN ZOR POZİTİFLER
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "EN DÜŞÜK SKORLU 5 POZİTİF"
)

print(
    "=" * 80
)


hardest_positive = (

    summary_df[
        summary_df[
            "question_type"
        ]
        == "positive"
    ]

    .sort_values(
        "top1_similarity",
        ascending=True
    )

    .head(5)
)


print(
    hardest_positive[
        [
            "question_number",
            "question",
            "top1_similarity",
            "top1_title",
        ]
    ]
    .to_string(
        index=False
    )
)


# ============================================================
# EN ZOR NEGATİFLER
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "EN YÜKSEK SKORLU 5 NEGATİF"
)

print(
    "=" * 80
)


hardest_negative = (

    summary_df[
        summary_df[
            "question_type"
        ]
        == "negative"
    ]

    .sort_values(
        "top1_similarity",
        ascending=False
    )

    .head(5)
)


print(
    hardest_negative[
        [
            "question_number",
            "question",
            "top1_similarity",
            "top1_title",
        ]
    ]
    .to_string(
        index=False
    )
)


# ============================================================
# PERFORMANS
# ============================================================

total_query_pipeline_seconds = (
    embedding_seconds
    + search_seconds
)


print(
    "\n"
    + "=" * 80
)

print(
    "PERFORMANS"
)

print(
    "=" * 80
)


print(
    f"\n30 query embedding süresi : "
    f"{embedding_seconds:.3f} saniye"
)


print(
    f"30 Chroma search süresi   : "
    f"{search_seconds:.3f} saniye"
)


print(
    f"Toplam retrieval süresi   : "
    f"{total_query_pipeline_seconds:.3f} saniye"
)


print(
    f"Ortalama / soru           : "
    f"{total_query_pipeline_seconds / total_count * 1000:.2f} ms"
)


# ============================================================
# OUTPUT
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "OUTPUT DOSYALARI"
)

print(
    "=" * 80
)


print(
    f"""
Summary:
{SUMMARY_OUTPUT_FILE}

Detailed child results:
{DETAIL_OUTPUT_FILE}

Unique parent results:
{PARENT_OUTPUT_FILE}
"""
)


# ============================================================
# TAMAMLANDI
# ============================================================

print(
    "=" * 80
)

print(
    "06 BENCHMARK TAMAMLANDI"
)

print(
    "=" * 80
)