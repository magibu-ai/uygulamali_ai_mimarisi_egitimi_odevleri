from pathlib import Path
import json
import sys
import time

import chromadb
import numpy as np
import pandas as pd
import torch

from sentence_transformers import SentenceTransformer
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
)


# ============================================================
# DOSYALAR
# ============================================================

SOURCE_FILE = Path(
    "data/chunks_with_embeddings.parquet"
)

CHROMA_DIR = Path(
    "data/chroma_db"
)

THRESHOLD_FILE = Path(
    "analysis/selected_threshold.json"
)


# ============================================================
# CHROMA
# ============================================================

COLLECTION_NAME = (
    "turkish_medical_chunks"
)


# ============================================================
# EMBEDDING MODELİ
# ============================================================

EMBEDDING_MODEL_NAME = (
    "Qwen/Qwen3-Embedding-0.6B"
)

EXPECTED_EMBEDDING_DIMENSION = 1024


# ============================================================
# GENERATION MODELİ
# ============================================================

GENERATOR_MODEL_NAME = (
    "Qwen/Qwen3-1.7B"
)


# ============================================================
# RETRIEVAL
# ============================================================

TOP_K_CHILDREN = 10

MAX_CONTEXT_PARENTS = 3


# ============================================================
# GENERATION
# ============================================================

MAX_NEW_TOKENS = 400

TEMPERATURE = 0.1


# ============================================================
# FALLBACK
# ============================================================

NO_ANSWER_RESPONSE = (
    "Bu sorunun cevabı dokümanlarımda yer almamaktadır"
)


# ============================================================
# DEVICE
# ============================================================

if torch.cuda.is_available():

    EMBEDDING_DEVICE = "cuda"

else:

    EMBEDDING_DEVICE = "cpu"


# ============================================================
# YARDIMCI
# ============================================================

def cosine_distance_to_similarity(
    distance
):

    similarity = (
        1.0
        - float(distance)
    )

    return max(
        -1.0,
        min(
            1.0,
            similarity
        )
    )


def normalize_vector(
    vector
):

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
            "Sıfır normlu embedding oluştu."
        )


    return (
        vector
        / norm
    ).astype(
        np.float32
    )


# ============================================================
# INPUT KONTROLLERİ
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "TURKISH MEDICAL RAG"
)

print(
    "=" * 80
)


if not SOURCE_FILE.exists():

    raise FileNotFoundError(
        f"{SOURCE_FILE} bulunamadı."
    )


if not CHROMA_DIR.exists():

    raise FileNotFoundError(
        f"{CHROMA_DIR} bulunamadı."
    )


if not THRESHOLD_FILE.exists():

    raise FileNotFoundError(
        f"{THRESHOLD_FILE} bulunamadı.\n"
        "Önce 07_select_threshold.py çalıştırılmalıdır."
    )


# ============================================================
# THRESHOLD YÜKLE
# ============================================================

with open(
    THRESHOLD_FILE,
    "r",
    encoding="utf-8"
) as file:

    threshold_data = json.load(
        file
    )


FINAL_THRESHOLD = float(
    threshold_data[
        "selected_threshold"
    ]
)


print(
    f"\nThreshold: "
    f"{FINAL_THRESHOLD:.3f}"
)


# ============================================================
# THRESHOLD MODEL KONTROLÜ
# ============================================================

threshold_model = (
    threshold_data.get(
        "embedding_model"
    )
)


if (
    threshold_model
    != EMBEDDING_MODEL_NAME
):

    raise ValueError(
        "Threshold farklı embedding modeli "
        "ile oluşturulmuş.\n"
        f"Threshold model: "
        f"{threshold_model}\n"
        f"Current model  : "
        f"{EMBEDDING_MODEL_NAME}"
    )


# ============================================================
# SOURCE PARQUET
# ============================================================

print(
    "\nSource parquet yükleniyor..."
)


df = pd.read_parquet(
    SOURCE_FILE
)


print(
    f"Child sayısı : "
    f"{len(df)}"
)


# ============================================================
# SOURCE VALIDATION
# ============================================================

required_columns = [
    "article_id",
    "parent_id",
    "child_id",
    "title",
    "url",
    "parent_text",
    "chunk_text",
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
# MODEL VALIDATION
# ============================================================

document_models = (
    df[
        "embedding_model"
    ]
    .dropna()
    .astype(str)
    .unique()
)


if len(
    document_models
) != 1:

    raise ValueError(
        "Birden fazla embedding modeli bulundu."
    )


document_model = (
    document_models[0]
)


if (
    document_model
    != EMBEDDING_MODEL_NAME
):

    raise ValueError(
        "Document embedding modeli "
        "query modeli ile aynı değil."
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
    f"Parent sayısı: "
    f"{len(parent_lookup)}"
)


# ============================================================
# CHROMADB
# ============================================================

print(
    "\nChromaDB yükleniyor..."
)


client = (
    chromadb.PersistentClient(
        path=str(
            CHROMA_DIR
        )
    )
)


collection = (
    client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )
)


print(
    f"Chroma kayıt sayısı: "
    f"{collection.count()}"
)


if (
    collection.count()
    != len(df)
):

    raise ValueError(
        "ChromaDB ile parquet "
        "kayıt sayıları eşleşmiyor."
    )


# ============================================================
# QUERY EMBEDDING MODELİ
# ============================================================

print(
    "\nEmbedding modeli yükleniyor..."
)


embedding_start = (
    time.perf_counter()
)


embedding_model = (
    SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        device=EMBEDDING_DEVICE,
    )
)


print(
    f"Embedding model yüklendi: "
    f"{time.perf_counter() - embedding_start:.2f} sn"
)


# ============================================================
# EMBEDDING DIMENSION
# ============================================================

embedding_dimension = (
    embedding_model.get_embedding_dimension()
)


if (
    embedding_dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Embedding dimension hatalı.\n"
        f"Beklenen: "
        f"{EXPECTED_EMBEDDING_DIMENSION}\n"
        f"Gelen   : "
        f"{embedding_dimension}"
    )


# ============================================================
# GENERATOR
# ============================================================

print(
    "\nGeneration modeli yükleniyor..."
)


generator_start = (
    time.perf_counter()
)


generator_tokenizer = (
    AutoTokenizer.from_pretrained(
        GENERATOR_MODEL_NAME
    )
)


# CUDA varsa transformers mümkün olduğunca
# GPU kullanır. Bellek yetmezse device_map="auto"
# CPU'ya bazı katmanları taşıyabilir.

generator_model = (
    AutoModelForCausalLM.from_pretrained(
        GENERATOR_MODEL_NAME,
        torch_dtype="auto",
        device_map="auto",
    )
)


generator_model.eval()


print(
    f"Generator yüklendi: "
    f"{time.perf_counter() - generator_start:.2f} sn"
)


# ============================================================
# QUERY EMBEDDING
# ============================================================

def embed_query(
    question
):

    question = str(
        question
    ).strip()


    if not question:

        raise ValueError(
            "Soru boş olamaz."
        )


    with torch.inference_mode():

        vector = embedding_model.encode(

            question,

            prompt_name="query",

            convert_to_numpy=True,

            normalize_embeddings=True,
        )


    vector = normalize_vector(
        vector
    )


    if (
        vector.shape
        != (
            EXPECTED_EMBEDDING_DIMENSION,
        )
    ):

        raise ValueError(
            "Query embedding shape yanlış."
        )


    return vector


# ============================================================
# CHILD RETRIEVAL
# ============================================================

def retrieve_children(
    question
):

    query_vector = (
        embed_query(
            question
        )
    )


    result = (
        collection.query(

            query_embeddings=[
                query_vector.tolist()
            ],

            n_results=TOP_K_CHILDREN,

            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )
    )


    children = []


    for rank, (
        child_id,
        document,
        metadata,
        distance,
    ) in enumerate(

        zip(

            result[
                "ids"
            ][0],

            result[
                "documents"
            ][0],

            result[
                "metadatas"
            ][0],

            result[
                "distances"
            ][0],
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


        children.append(
            {
                "rank": (
                    rank
                ),

                "child_id": (
                    str(
                        child_id
                    )
                ),

                "parent_id": (
                    str(
                        metadata.get(
                            "parent_id",
                            ""
                        )
                    )
                ),

                "title": (
                    str(
                        metadata.get(
                            "title",
                            ""
                        )
                    )
                ),

                "url": (
                    str(
                        metadata.get(
                            "url",
                            ""
                        )
                    )
                ),

                "similarity": (
                    similarity
                ),

                "distance": (
                    float(
                        distance
                    )
                ),

                "chunk_text": (
                    str(
                        document
                    )
                ),
            }
        )


    return children


# ============================================================
# UNIQUE PARENT CONTEXT
# ============================================================

def select_context_parents(
    children
):
    """
    Threshold'u geçen child sonuçlarından
    unique parent context seçer.
    """

    selected = []


    used_parent_ids = set()


    for child in children:

        # ----------------------------------------
        # Context'e yalnızca threshold'u geçen
        # retrieval sonuçlarını al.
        # ----------------------------------------

        if (
            child[
                "similarity"
            ]
            < FINAL_THRESHOLD
        ):

            continue


        parent_id = (
            child[
                "parent_id"
            ]
        )


        if not parent_id:

            continue


        if (
            parent_id
            in used_parent_ids
        ):

            continue


        if (
            parent_id
            not in parent_lookup
        ):

            continue


        parent_info = (
            parent_lookup[
                parent_id
            ]
        )


        selected.append(
            {
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

                "similarity": (
                    child[
                        "similarity"
                    ]
                ),

                "best_child_id": (
                    child[
                        "child_id"
                    ]
                ),
            }
        )


        used_parent_ids.add(
            parent_id
        )


        if (
            len(
                selected
            )
            >= MAX_CONTEXT_PARENTS
        ):

            break


    return selected


# ============================================================
# CONTEXT OLUŞTUR
# ============================================================

def build_context(
    parents
):

    context_parts = []


    for index, parent in enumerate(
        parents,
        start=1
    ):

        context_part = f"""
[KAYNAK {index}]

Başlık:
{parent['title']}

URL:
{parent['url']}

İlgililik skoru:
{parent['similarity']:.4f}

Doküman:
{parent['parent_text']}
""".strip()


        context_parts.append(
            context_part
        )


    return (
        "\n\n"
        + "\n\n".join(
            context_parts
        )
    )


# ============================================================
# GENERATION
# ============================================================

def generate_answer(
    question,
    parents
):

    context = (
        build_context(
            parents
        )
    )


    system_message = f"""
Sen Türkçe tıbbi dokümanlar üzerinde çalışan
bir Retrieval-Augmented Generation asistanısın.

Görevin yalnızca sana verilen DOKÜMAN BAĞLAMI
içerisindeki bilgilere dayanarak kullanıcı
sorusunu cevaplamaktır.

Kurallar:

1. Dokümanlarda bulunmayan bilgi ekleme.
2. Kendi genel bilgini kullanma.
3. Tahmin veya varsayım yapma.
4. Cevabı Türkçe ver.
5. Cevabı açık ve doğrudan yaz.
6. Gereksiz uzun cevap üretme.
7. Tıbbi teşhis koymaya çalışma.
8. Bağlam soruya yeterli cevap vermiyorsa
   yalnızca şu ifadeyi döndür:

{NO_ANSWER_RESPONSE}
""".strip()


    user_message = f"""
DOKÜMAN BAĞLAMI:

{context}


KULLANICI SORUSU:

{question}


Yalnızca yukarıdaki doküman bağlamını
kullanarak cevap ver.
""".strip()


    messages = [

        {
            "role": "system",
            "content": (
                system_message
            ),
        },

        {
            "role": "user",
            "content": (
                user_message
            ),
        },
    ]


    # Qwen3 için thinking kapatılıyor.
    # Final cevapta reasoning istemiyoruz.

    try:

        text = (
            generator_tokenizer
            .apply_chat_template(

                messages,

                tokenize=False,

                add_generation_prompt=True,

                enable_thinking=False,
            )
        )

    except TypeError:

        # Daha eski transformers sürümü
        # enable_thinking argümanını desteklemiyorsa.

        text = (
            generator_tokenizer
            .apply_chat_template(

                messages,

                tokenize=False,

                add_generation_prompt=True,
            )
        )


    model_inputs = (
        generator_tokenizer(

            [
                text
            ],

            return_tensors="pt",
        )
    )


    # Model hangi device'taysa input'u
    # ilk parametrenin device'ına gönder.

    model_device = next(
        generator_model.parameters()
    ).device


    model_inputs = {
        key: value.to(
            model_device
        )
        for key, value
        in model_inputs.items()
    }


    with torch.inference_mode():

        generated_ids = (
            generator_model.generate(

                **model_inputs,

                max_new_tokens=MAX_NEW_TOKENS,

                do_sample=(
                    TEMPERATURE > 0
                ),

                temperature=(
                    TEMPERATURE
                ),

                top_p=0.9,

                repetition_penalty=1.05,

                pad_token_id=(
                    generator_tokenizer.eos_token_id
                ),
            )
        )


    # Sadece yeni üretilen token'ları al.

    input_length = (
        model_inputs[
            "input_ids"
        ].shape[1]
    )


    generated_tokens = (
        generated_ids[
            :,
            input_length:
        ]
    )


    answer = (
        generator_tokenizer
        .batch_decode(

            generated_tokens,

            skip_special_tokens=True,
        )[0]
        .strip()
    )


    if not answer:

        return (
            NO_ANSWER_RESPONSE
        )


    return answer


# ============================================================
# FINAL RAG
# ============================================================

def ask(
    question,
    show_debug=True
):

    total_start = (
        time.perf_counter()
    )


    # ========================================================
    # RETRIEVAL
    # ========================================================

    retrieval_start = (
        time.perf_counter()
    )


    children = (
        retrieve_children(
            question
        )
    )


    retrieval_seconds = (
        time.perf_counter()
        - retrieval_start
    )


    if not children:

        return {
            "answer": (
                NO_ANSWER_RESPONSE
            ),

            "accepted": False,

            "top_similarity": (
                None
            ),

            "sources": [],
        }


    top_child = (
        children[0]
    )


    top_similarity = (
        top_child[
            "similarity"
        ]
    )


    # ========================================================
    # THRESHOLD
    # ========================================================

    if (
        top_similarity
        < FINAL_THRESHOLD
    ):

        total_seconds = (
            time.perf_counter()
            - total_start
        )


        if show_debug:

            print(
                "\n"
                + "-" * 80
            )

            print(
                "RETRIEVAL"
            )

            print(
                "-" * 80
            )


            print(
                f"Top similarity : "
                f"{top_similarity:.6f}"
            )


            print(
                f"Threshold      : "
                f"{FINAL_THRESHOLD:.6f}"
            )


            print(
                "Durum          : "
                "REJECT"
            )


            print(
                f"Retrieval süre : "
                f"{retrieval_seconds * 1000:.2f} ms"
            )


            print(
                f"Toplam süre    : "
                f"{total_seconds * 1000:.2f} ms"
            )


        return {

            "answer": (
                NO_ANSWER_RESPONSE
            ),

            "accepted": False,

            "top_similarity": (
                top_similarity
            ),

            "sources": [],
        }


    # ========================================================
    # PARENT CONTEXT
    # ========================================================

    parents = (
        select_context_parents(
            children
        )
    )


    if not parents:

        return {

            "answer": (
                NO_ANSWER_RESPONSE
            ),

            "accepted": False,

            "top_similarity": (
                top_similarity
            ),

            "sources": [],
        }


    # ========================================================
    # LLM GENERATION
    # ========================================================

    generation_start = (
        time.perf_counter()
    )


    answer = (
        generate_answer(
            question,
            parents
        )
    )


    generation_seconds = (
        time.perf_counter()
        - generation_start
    )


    total_seconds = (
        time.perf_counter()
        - total_start
    )


    # ========================================================
    # DEBUG
    # ========================================================

    if show_debug:

        print(
            "\n"
            + "-" * 80
        )

        print(
            "RETRIEVAL"
        )

        print(
            "-" * 80
        )


        print(
            f"Top similarity : "
            f"{top_similarity:.6f}"
        )


        print(
            f"Threshold      : "
            f"{FINAL_THRESHOLD:.6f}"
        )


        print(
            "Durum          : "
            "ACCEPT"
        )


        print(
            f"Context parent : "
            f"{len(parents)}"
        )


        print(
            f"Retrieval süre : "
            f"{retrieval_seconds * 1000:.2f} ms"
        )


        print(
            f"Generation süre: "
            f"{generation_seconds:.2f} sn"
        )


        print(
            f"Toplam süre    : "
            f"{total_seconds:.2f} sn"
        )


        print(
            "\nKaynaklar:"
        )


        for index, parent in enumerate(
            parents,
            start=1
        ):

            print(
                f"\n{index}. "
                f"{parent['title']}"
            )

            print(
                f"   Similarity: "
                f"{parent['similarity']:.6f}"
            )

            print(
                f"   {parent['url']}"
            )


    return {

        "answer": (
            answer
        ),

        "accepted": True,

        "top_similarity": (
            top_similarity
        ),

        "sources": (
            parents
        ),
    }


# ============================================================
# TEK SORU
# ============================================================

def run_single_question(
    question
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        "SORU"
    )

    print(
        "=" * 80
    )


    print(
        question
    )


    result = (
        ask(
            question,
            show_debug=True
        )
    )


    print(
        "\n"
        + "=" * 80
    )

    print(
        "CEVAP"
    )

    print(
        "=" * 80
    )


    # Ödevde istenen fallback burada
    # karakter karakter aynı kalır.

    print(
        result[
            "answer"
        ]
    )


# ============================================================
# INTERACTIVE MODE
# ============================================================

def interactive_mode():

    print(
        "\n"
        + "=" * 80
    )

    print(
        "INTERACTIVE RAG"
    )

    print(
        "=" * 80
    )


    print(
        "\nÇıkmak için:"
        "\nq"
        "\nquit"
        "\nexit"
    )


    while True:

        try:

            question = input(
                "\nSorunuz: "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError
        ):

            print(
                "\nÇıkılıyor."
            )

            break


        if (
            question.lower()
            in {
                "q",
                "quit",
                "exit",
            }
        ):

            print(
                "Çıkılıyor."
            )

            break


        if not question:

            continue


        run_single_question(
            question
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    cli_question = (
        " ".join(
            sys.argv[1:]
        )
        .strip()
    )


    if cli_question:

        run_single_question(
            cli_question
        )

    else:

        interactive_mode()