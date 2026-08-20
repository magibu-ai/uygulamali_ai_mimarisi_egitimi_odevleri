from pathlib import Path
import sys
import time

import chromadb
import numpy as np
import pandas as pd
import torch

from sentence_transformers import SentenceTransformer


# ============================================================
# AYARLAR
# ============================================================

SOURCE_FILE = Path(
    "data/chunks_with_embeddings.parquet"
)

CHROMA_DIR = Path(
    "data/chroma_db"
)

COLLECTION_NAME = (
    "turkish_medical_chunks"
)

OUTPUT_FILE = Path(
    "analysis/retrieval_smoke_test.csv"
)


# ============================================================
# EMBEDDING MODELİ
# ============================================================

MODEL_NAME = (
    "Qwen/Qwen3-Embedding-0.6B"
)

EXPECTED_EMBEDDING_DIMENSION = 1024


# ============================================================
# RETRIEVAL AYARLARI
# ============================================================

# Önce kaç child getirilecek?
TOP_K_CHILDREN = 10

# Kaç unique parent gösterilecek?
TOP_K_PARENTS = 5

# Console'da metinlerin ne kadarı gösterilsin?
CHILD_PREVIEW_CHARS = 500
PARENT_PREVIEW_CHARS = 900


# ============================================================
# TEST SORULARI
# ============================================================

# Threshold belirlemek için henüz kullanılmıyor.
#
# Buradaki amaç:
# pozitif ve negatif soruların similarity skorlarını
# ilk kez gözlemlemek.

TEST_QUESTIONS = [

    # --------------------------------------------------------
    # POZİTİF
    # --------------------------------------------------------

    {
        "type": "positive",
        "question": (
            "Angelman sendromunun belirtileri nelerdir?"
        ),
    },

    {
        "type": "positive",
        "question": (
            "Bradikardi nedir ve belirtileri nelerdir?"
        ),
    },

    {
        "type": "positive",
        "question": (
            "Böbrek yetmezliğinin belirtileri nelerdir?"
        ),
    },

    {
        "type": "positive",
        "question": (
            "Migrene ne iyi gelir?"
        ),
    },

    {
        "type": "positive",
        "question": (
            "Hamileliğin ilk haftasında "
            "mide bulantısı olur mu?"
        ),
    },

    # --------------------------------------------------------
    # NEGATİF
    # --------------------------------------------------------

    {
        "type": "negative",
        "question": (
            "Toyota Corolla'nın motor hacmi kaç cc?"
        ),
    },

    {
        "type": "negative",
        "question": (
            "Python'da bir liste nasıl sıralanır?"
        ),
    },

    {
        "type": "negative",
        "question": (
            "İstanbul'dan Ankara'ya hızlı tren "
            "kaç saat sürer?"
        ),
    },
]


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

def preview_text(
    text,
    max_chars
):
    """
    Console çıktısında çok uzun metinleri kısaltır.
    """

    if text is None:
        return ""

    text = str(text).strip()

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        .rstrip()
        + " ..."
    )


def cosine_distance_to_similarity(
    distance
):
    """
    Chroma cosine distance:
        distance = 1 - cosine_similarity

    Dolayısıyla:
        similarity = 1 - distance

    Floating point sapmalarına karşı [-1, 1]
    aralığına clamp edilir.
    """

    similarity = (
        1.0
        - float(distance)
    )

    similarity = max(
        -1.0,
        min(
            1.0,
            similarity
        )
    )

    return similarity


def normalize_vector(
    vector
):
    """
    Float32 seviyesinde kesin L2 normalization.
    """

    vector = np.asarray(
        vector,
        dtype=np.float32
    )

    norm = float(
        np.linalg.norm(
            vector
        )
    )

    if norm == 0:

        raise ValueError(
            "Sıfır normlu query embedding oluştu."
        )

    vector = (
        vector
        / norm
    ).astype(
        np.float32
    )

    return vector


# ============================================================
# INPUT KONTROLLERİ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "05 - RETRIEVAL TEST"
)

print(
    "=" * 70
)


if not SOURCE_FILE.exists():

    raise FileNotFoundError(
        f"{SOURCE_FILE} bulunamadı.\n"
        "Önce 03_embed_chunks.py "
        "çalıştırılmalıdır."
    )


if not CHROMA_DIR.exists():

    raise FileNotFoundError(
        f"{CHROMA_DIR} bulunamadı.\n"
        "Önce 04_build_chroma.py "
        "çalıştırılmalıdır."
    )


# ============================================================
# SOURCE PARQUET
# ============================================================

print(
    f"\nSource file:\n"
    f"{SOURCE_FILE}"
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
        "Eksik kolonlar:\n"
        + "\n".join(
            missing_columns
        )
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
        "Birden fazla embedding modeli bulundu:\n"
        f"{embedding_models}"
    )


stored_embedding_model = (
    embedding_models[0]
)


if (
    stored_embedding_model
    != MODEL_NAME
):

    raise ValueError(
        "Query modeli ile document embedding "
        "modeli eşleşmiyor.\n"
        f"Document model: "
        f"{stored_embedding_model}\n"
        f"Query model   : "
        f"{MODEL_NAME}"
    )


print(
    f"\nEmbedding model:"
    f"\n{stored_embedding_model}"
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
        "Birden fazla embedding "
        "dimension bulundu."
    )


stored_dimension = int(
    embedding_dimensions[0]
)


if (
    stored_dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Embedding dimension beklenenden farklı.\n"
        f"Beklenen: "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen   : "
        f"{stored_dimension}"
    )


print(
    f"Embedding dimension: "
    f"{stored_dimension}"
)


# ============================================================
# PARENT TEXT CONSISTENCY KONTROLÜ
# ============================================================

print(
    "\nParent consistency kontrol ediliyor..."
)


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


inconsistent_parents = (
    parent_text_counts[
        parent_text_counts > 1
    ]
)


if len(
    inconsistent_parents
) > 0:

    raise ValueError(
        f"{len(inconsistent_parents)} parent_id "
        "için birden fazla parent_text bulundu."
    )


print(
    "Parent consistency: OK"
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
    f"Unique parent sayısı: "
    f"{len(parent_lookup)}"
)


# ============================================================
# CHROMADB CLIENT
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CHROMADB YÜKLENİYOR"
)

print(
    "=" * 70
)


client = (
    chromadb.PersistentClient(
        path=str(
            CHROMA_DIR
        )
    )
)


# ============================================================
# COLLECTION
# ============================================================

collection = (
    client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )
)


collection_count = (
    collection.count()
)


print(
    f"\nCollection:"
    f"\n{COLLECTION_NAME}"
)


print(
    f"\nChroma kayıt sayısı: "
    f"{collection_count}"
)


if (
    collection_count
    != len(df)
):

    raise ValueError(
        "Chroma kayıt sayısı ile "
        "Parquet kayıt sayısı eşleşmiyor.\n"
        f"Chroma : "
        f"{collection_count}\n"
        f"Parquet: "
        f"{len(df)}"
    )


print(
    "Collection count: OK"
)


# ============================================================
# QUERY EMBEDDING MODELİ
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "QUERY EMBEDDING MODELİ YÜKLENİYOR"
)

print(
    "=" * 70
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
    f"\nModel yüklendi: "
    f"{model_load_seconds:.2f} saniye"
)


# ============================================================
# MODEL DIMENSION VALIDATION
# ============================================================

model_dimension = (
    model.get_embedding_dimension()
)


if (
    model_dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Query embedding dimension hatalı.\n"
        f"Beklenen: "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen   : "
        f"{model_dimension}"
    )


print(
    f"Query embedding dimension: "
    f"{model_dimension}"
)


# ============================================================
# QUERY EMBEDDING
# ============================================================

def embed_query(
    question
):
    """
    Qwen3 retrieval query embedding.

    Document'lar 03 aşamasında prompt olmadan
    encode edildi.

    Query tarafında modelin kendi:
        prompt_name="query"

    prompt'u kullanılır.
    """

    question = str(
        question
    ).strip()

    if not question:

        raise ValueError(
            "Boş soru verilemez."
        )


    start = (
        time.perf_counter()
    )


    with torch.inference_mode():

        embedding = model.encode(

            question,

            prompt_name="query",

            convert_to_numpy=True,

            normalize_embeddings=True,
        )


    elapsed = (
        time.perf_counter()
        - start
    )


    embedding = normalize_vector(
        embedding
    )


    if (
        embedding.shape
        != (
            EXPECTED_EMBEDDING_DIMENSION,
        )
    ):

        raise ValueError(
            "Query embedding shape hatalı.\n"
            f"Gelen: "
            f"{embedding.shape}"
        )


    if not np.isfinite(
        embedding
    ).all():

        raise ValueError(
            "Query embedding içerisinde "
            "NaN veya Inf bulundu."
        )


    return (
        embedding,
        elapsed
    )


# ============================================================
# CHILD RETRIEVAL
# ============================================================

def search_children(
    question,
    top_k=TOP_K_CHILDREN
):
    """
    Soru -> query embedding -> Chroma child retrieval
    """

    query_embedding, embedding_time = (
        embed_query(
            question
        )
    )


    search_start = (
        time.perf_counter()
    )


    result = collection.query(

        query_embeddings=[
            query_embedding.tolist()
        ],

        n_results=min(
            top_k,
            collection_count
        ),

        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )


    search_time = (
        time.perf_counter()
        - search_start
    )


    ids = (
        result[
            "ids"
        ][0]
    )


    documents = (
        result[
            "documents"
        ][0]
    )


    metadatas = (
        result[
            "metadatas"
        ][0]
    )


    distances = (
        result[
            "distances"
        ][0]
    )


    rows = []


    for rank, (
        child_id,
        document,
        metadata,
        distance,
    ) in enumerate(

        zip(
            ids,
            documents,
            metadatas,
            distances,
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


        parent_id = str(
            metadata.get(
                "parent_id",
                ""
            )
        )


        title = str(
            metadata.get(
                "title",
                ""
            )
        )


        url = str(
            metadata.get(
                "url",
                ""
            )
        )


        rows.append(
            {
                "rank": rank,

                "child_id": (
                    str(
                        child_id
                    )
                ),

                "parent_id": (
                    parent_id
                ),

                "title": (
                    title
                ),

                "url": (
                    url
                ),

                "distance": (
                    float(
                        distance
                    )
                ),

                "similarity": (
                    similarity
                ),

                "chunk_text": (
                    str(
                        document
                    )
                ),
            }
        )


    return {
        "question": question,

        "query_embedding_time": (
            embedding_time
        ),

        "chroma_search_time": (
            search_time
        ),

        "query_vector_norm": float(
            np.linalg.norm(
                query_embedding
            )
        ),

        "children": rows,
    }


# ============================================================
# UNIQUE PARENT RANKING
# ============================================================

def rank_unique_parents(
    child_results,
    top_k=TOP_K_PARENTS
):
    """
    Aynı parent'a ait birden fazla child retrieval
    sonucu gelebilir.

    Her parent için en yüksek similarity'ye sahip
    child skoru kullanılır.
    """

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
                "Chroma'dan gelen parent_id "
                "Parquet'te bulunamadı:\n"
                f"{parent_id}"
            )


        existing = (
            best_parent_results.get(
                parent_id
            )
        )


        if (
            existing is None
            or child[
                "similarity"
            ]
            > existing[
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

                "parent_token_count": (
                    parent_info[
                        "parent_token_count"
                    ]
                ),

                "parent_text": (
                    parent_info[
                        "parent_text"
                    ]
                ),

                "best_child_id": (
                    child[
                        "child_id"
                    ]
                ),

                "best_child_text": (
                    child[
                        "chunk_text"
                    ]
                ),

                "distance": (
                    child[
                        "distance"
                    ]
                ),

                "similarity": (
                    child[
                        "similarity"
                    ]
                ),
            }


    ranked = sorted(

        best_parent_results.values(),

        key=lambda item: (
            item[
                "similarity"
            ]
        ),

        reverse=True,
    )


    return ranked[
        :top_k
    ]


# ============================================================
# CONSOLE OUTPUT
# ============================================================

def print_retrieval_result(
    question,
    retrieval_result,
    parent_results
):
    """
    Retrieval sonucunu okunabilir biçimde gösterir.
    """

    children = (
        retrieval_result[
            "children"
        ]
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        f"SORU:\n"
        f"{question}"
    )

    print(
        "=" * 90
    )


    print(
        "\nQuery vector norm : "
        f"{retrieval_result['query_vector_norm']:.8f}"
    )


    print(
        "Embedding süresi   : "
        f"{retrieval_result['query_embedding_time'] * 1000:.2f} ms"
    )


    print(
        "Chroma search      : "
        f"{retrieval_result['chroma_search_time'] * 1000:.2f} ms"
    )


    # --------------------------------------------------------
    # CHILD RESULTS
    # --------------------------------------------------------

    print(
        "\n"
        + "-" * 90
    )

    print(
        f"TOP {len(children)} CHILD"
    )

    print(
        "-" * 90
    )


    for child in children:

        print(
            f"""
#{child['rank']}

Similarity : {child['similarity']:.6f}
Distance   : {child['distance']:.6f}

Başlık     : {child['title']}
Child ID   : {child['child_id']}
Parent ID  : {child['parent_id']}

Chunk:
{preview_text(
    child['chunk_text'],
    CHILD_PREVIEW_CHARS
)}
"""
        )


    # --------------------------------------------------------
    # UNIQUE PARENT RESULTS
    # --------------------------------------------------------

    print(
        "\n"
        + "-" * 90
    )

    print(
        f"TOP {len(parent_results)} UNIQUE PARENT"
    )

    print(
        "-" * 90
    )


    for rank, parent in enumerate(
        parent_results,
        start=1
    ):

        print(
            f"""
PARENT #{rank}

Similarity      : {parent['similarity']:.6f}

Başlık          : {parent['title']}
Article ID      : {parent['article_id']}
Parent ID       : {parent['parent_id']}
Best Child ID   : {parent['best_child_id']}
Parent Token    : {parent['parent_token_count']}

URL:
{parent['url']}

Parent Text:
{preview_text(
    parent['parent_text'],
    PARENT_PREVIEW_CHARS
)}
"""
        )


# ============================================================
# TEK SORU RETRIEVAL
# ============================================================

def retrieve(
    question,
    print_result=True
):
    """
    Tek bir kullanıcı sorusu için:

        question
            ↓
        Qwen3 query embedding
            ↓
        Chroma child retrieval
            ↓
        unique parent ranking

    gerçekleştirir.
    """

    retrieval_result = (
        search_children(
            question
        )
    )


    parent_results = (
        rank_unique_parents(
            retrieval_result[
                "children"
            ]
        )
    )


    if print_result:

        print_retrieval_result(
            question,
            retrieval_result,
            parent_results
        )


    return {
        "retrieval": (
            retrieval_result
        ),

        "parents": (
            parent_results
        ),
    }


# ============================================================
# SMOKE TEST
# ============================================================

def run_smoke_test():
    """
    Hazır pozitif ve negatif sorular üzerinde
    retrieval sonuçlarını çalıştırır.

    Threshold uygulanmaz.
    """

    print(
        "\n"
        + "=" * 70
    )

    print(
        "SMOKE TEST BAŞLIYOR"
    )

    print(
        "=" * 70
    )


    output_rows = []


    for question_number, item in enumerate(
        TEST_QUESTIONS,
        start=1
    ):

        question_type = (
            item[
                "type"
            ]
        )

        question = (
            item[
                "question"
            ]
        )


        print(
            "\n\n"
            + "#" * 90
        )

        print(
            f"TEST {question_number}/"
            f"{len(TEST_QUESTIONS)}"
        )

        print(
            f"Beklenen tip: "
            f"{question_type.upper()}"
        )

        print(
            "#" * 90
        )


        result = retrieve(
            question,
            print_result=True
        )


        retrieval = (
            result[
                "retrieval"
            ]
        )


        parents = (
            result[
                "parents"
            ]
        )


        for child in retrieval[
            "children"
        ]:

            output_rows.append(
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
                        child[
                            "rank"
                        ]
                    ),

                    "similarity": (
                        child[
                            "similarity"
                        ]
                    ),

                    "distance": (
                        child[
                            "distance"
                        ]
                    ),

                    "child_id": (
                        child[
                            "child_id"
                        ]
                    ),

                    "parent_id": (
                        child[
                            "parent_id"
                        ]
                    ),

                    "title": (
                        child[
                            "title"
                        ]
                    ),

                    "url": (
                        child[
                            "url"
                        ]
                    ),

                    "chunk_text": (
                        child[
                            "chunk_text"
                        ]
                    ),

                    "query_embedding_ms": (
                        retrieval[
                            "query_embedding_time"
                        ]
                        * 1000
                    ),

                    "chroma_search_ms": (
                        retrieval[
                            "chroma_search_time"
                        ]
                        * 1000
                    ),
                }
            )


        # ----------------------------------------------------
        # KISA ÖZET
        # ----------------------------------------------------

        if retrieval[
            "children"
        ]:

            top_child = (
                retrieval[
                    "children"
                ][0]
            )


            print(
                "\n"
                + "=" * 50
            )

            print(
                "SORU ÖZETİ"
            )

            print(
                "=" * 50
            )


            print(
                f"Tip            : "
                f"{question_type}"
            )


            print(
                f"Top-1 similarity: "
                f"{top_child['similarity']:.6f}"
            )


            print(
                f"Top-1 başlık    : "
                f"{top_child['title']}"
            )


            print(
                f"Top-1 child     : "
                f"{top_child['child_id']}"
            )


            if parents:

                print(
                    f"Top parent      : "
                    f"{parents[0]['parent_id']}"
                )


    # ========================================================
    # CSV KAYDET
    # ========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    output_df = pd.DataFrame(
        output_rows
    )


    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    print(
        "\n"
        + "=" * 90
    )

    print(
        "SMOKE TEST TAMAMLANDI"
    )

    print(
        "=" * 90
    )


    print(
        f"\nSonuç dosyası:\n"
        f"{OUTPUT_FILE}"
    )


    # ========================================================
    # TOP-1 SCORE SUMMARY
    # ========================================================

    top1_df = (
        output_df[
            output_df[
                "child_rank"
            ]
            == 1
        ]
        .copy()
    )


    print(
        "\n"
        + "=" * 70
    )

    print(
        "TOP-1 SIMILARITY ÖZETİ"
    )

    print(
        "=" * 70
    )


    summary_columns = [
        "question_type",
        "question",
        "similarity",
        "title",
    ]


    print(
        top1_df[
            summary_columns
        ]
        .to_string(
            index=False
        )
    )


    # ========================================================
    # POZİTİF / NEGATİF SCORE İSTATİSTİĞİ
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "POZİTİF / NEGATİF TOP-1 SCORE"
    )

    print(
        "=" * 70
    )


    score_summary = (
        top1_df
        .groupby(
            "question_type"
        )[
            "similarity"
        ]
        .agg(
            [
                "count",
                "mean",
                "min",
                "max",
            ]
        )
        .round(6)
    )


    print(
        score_summary
    )


# ============================================================
# OPTIONAL COMMAND LINE QUERY
# ============================================================

def run_command_line_query():
    """
    Kullanım:

        python 05_test_retrieval.py
            -> hazır smoke test

        python 05_test_retrieval.py "Angelman nedir?"
            -> yalnızca verilen soruyu arar
    """

    question = " ".join(
        sys.argv[1:]
    ).strip()


    if question:

        print(
            "\nCommand-line query algılandı."
        )

        retrieve(
            question,
            print_result=True
        )

        return True


    return False


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    has_cli_query = (
        run_command_line_query()
    )


    if not has_cli_query:

        run_smoke_test()