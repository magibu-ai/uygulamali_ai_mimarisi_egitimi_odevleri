# 09_run_rag_questions.py

from pathlib import Path
import os

# ============================================================
# HUGGING FACE CACHE
# ============================================================
# Hugging Face kullanan importlardan ÖNCE tanımlanmalı.

os.environ["HF_HOME"] = r"D:\huggingface"
os.environ["HF_HUB_CACHE"] = r"D:\huggingface\hub"
os.environ["HF_XET_CACHE"] = r"D:\huggingface\xet"


import json
import re
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

QUESTIONS_FILE = Path(
    "data/benchmark_questions.txt"
)

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
# OUTPUT
# ============================================================

OUTPUT_DIR = Path(
    "analysis"
)

CSV_OUTPUT = (
    OUTPUT_DIR
    / "rag_question_answers.csv"
)

JSON_OUTPUT = (
    OUTPUT_DIR
    / "rag_question_answers.json"
)

TXT_OUTPUT = (
    OUTPUT_DIR
    / "rag_question_answers.txt"
)


# ============================================================
# CHROMA
# ============================================================

COLLECTION_NAME = (
    "turkish_medical_chunks"
)


# ============================================================
# EMBEDDING MODEL
# ============================================================

EMBEDDING_MODEL_NAME = (
    "Qwen/Qwen3-Embedding-0.6B"
)

EXPECTED_EMBEDDING_DIMENSION = 1024


# ============================================================
# GENERATOR MODEL
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

MAX_NEW_TOKENS = 350


# ============================================================
# FALLBACK
# ============================================================

NO_ANSWER_RESPONSE = (
    "Bu sorunun cevabı dokümanlarımda yer almamaktadır"
)


# ============================================================
# RESUME
# ============================================================

# True:
# Script yarıda kesilirse mevcut CSV'deki soruları atlayıp
# kaldığı yerden devam eder.

RESUME = True


# ============================================================
# DEVICE
# ============================================================

# Generator daha çok GPU'ya ihtiyaç duyduğu için
# embedding modelini CPU'ya koyuyoruz.
#
# Böylece RTX 4050 6 GB VRAM'in büyük kısmı
# generation modeline kalır.

EMBEDDING_DEVICE = "cpu"


if torch.cuda.is_available():

    GENERATOR_DEVICE = "cuda"

else:

    GENERATOR_DEVICE = "cpu"


# ============================================================
# BENCHMARK TXT PARSER
# ============================================================

def parse_benchmark_questions(
    file_path
):

    text = file_path.read_text(
        encoding="utf-8"
    )

    lines = text.splitlines()


    question_pattern = re.compile(
        r"^\s*(\d+)\.\s*(.+?)\s*$"
    )


    current_type = None

    questions = []

    current_number = None

    current_parts = []


    def save_current():

        nonlocal current_number
        nonlocal current_parts


        if current_number is None:

            return


        question_text = (
            " ".join(
                current_parts
            )
            .strip()
        )


        if not question_text:

            raise ValueError(
                f"{current_number}. soru boş."
            )


        questions.append(
            {
                "question_number": (
                    current_number
                ),

                "question_type": (
                    current_type
                ),

                "question": (
                    question_text
                ),
            }
        )


        current_number = None

        current_parts = []


    for raw_line in lines:

        line = raw_line.strip()

        upper_line = line.upper()


        if (
            "POZİTİF SORULAR"
            in upper_line
        ):

            save_current()

            current_type = (
                "positive"
            )

            continue


        if (
            "NEGATİF SORULAR"
            in upper_line
        ):

            save_current()

            current_type = (
                "negative"
            )

            continue


        if current_type is None:

            continue


        if not line:

            continue


        if set(line) == {"="}:

            continue


        match = (
            question_pattern.match(
                line
            )
        )


        if match:

            save_current()


            current_number = int(
                match.group(1)
            )


            current_parts = [
                match.group(2)
            ]


            continue


        if current_number is not None:

            current_parts.append(
                line
            )


    save_current()


    return questions


# ============================================================
# VECTOR NORMALIZATION
# ============================================================

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
            "Sıfır normlu embedding."
        )


    return (
        vector
        / norm
    ).astype(
        np.float32
    )


# ============================================================
# COSINE DISTANCE -> SIMILARITY
# ============================================================

def distance_to_similarity(
    distance
):

    similarity = (
        1.0
        - float(
            distance
        )
    )


    return max(
        -1.0,
        min(
            1.0,
            similarity
        )
    )


# ============================================================
# BAŞLANGIÇ
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "09 - FINAL RAG QUESTION / ANSWER TEST"
)

print(
    "=" * 80
)


# ============================================================
# DOSYA KONTROLLERİ
# ============================================================

for path in [

    QUESTIONS_FILE,
    SOURCE_FILE,
    THRESHOLD_FILE,

]:

    if not path.exists():

        raise FileNotFoundError(
            f"{path} bulunamadı."
        )


if not CHROMA_DIR.exists():

    raise FileNotFoundError(
        f"{CHROMA_DIR} bulunamadı."
    )


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SORULAR
# ============================================================

questions = parse_benchmark_questions(
    QUESTIONS_FILE
)

questions_df = pd.DataFrame(
    questions
)

positive_count = int(
    (
        questions_df["question_type"]
        == "positive"
    ).sum()
)

negative_count = int(
    (
        questions_df["question_type"]
        == "negative"
    ).sum()
)

print(
    f"\nToplam soru: {len(questions_df)}"
)

print(
    f"Pozitif    : {positive_count}"
)

print(
    f"Negatif    : {negative_count}"
)


# ============================================================
# THRESHOLD
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
    f"{FINAL_THRESHOLD:.6f}"
)


# ============================================================
# THRESHOLD MODEL VALIDATION
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
        "ile hesaplanmış."
    )


# ============================================================
# SOURCE DATA
# ============================================================

print(
    "\nParquet yükleniyor..."
)


df = pd.read_parquet(
    SOURCE_FILE
)


print(
    f"Child sayısı : "
    f"{len(df)}"
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


# ============================================================
# EMBEDDING MODEL
# ============================================================

print(
    "\nEmbedding modeli yükleniyor..."
)


start = (
    time.perf_counter()
)


embedding_model = (
    SentenceTransformer(

        EMBEDDING_MODEL_NAME,

        device=EMBEDDING_DEVICE,
    )
)


print(
    f"Embedding model device: "
    f"{EMBEDDING_DEVICE}"
)


print(
    f"Embedding model yükleme: "
    f"{time.perf_counter() - start:.2f} sn"
)


# ============================================================
# EMBEDDING DIMENSION
# ============================================================

dimension = (
    embedding_model
    .get_embedding_dimension()
)


if (
    dimension
    != EXPECTED_EMBEDDING_DIMENSION
):

    raise ValueError(
        "Embedding dimension uyuşmuyor."
    )


# ============================================================
# GENERATOR TOKENIZER
# ============================================================

print(
    "\nGenerator tokenizer yükleniyor..."
)


generator_tokenizer = (
    AutoTokenizer.from_pretrained(
        GENERATOR_MODEL_NAME
    )
)


# ============================================================
# GENERATOR MODEL
# ============================================================

print(
    "\nGenerator model yükleniyor..."
)


start = (
    time.perf_counter()
)


if (
    GENERATOR_DEVICE
    == "cuda"
):

    generator_model = (
        AutoModelForCausalLM
        .from_pretrained(

            GENERATOR_MODEL_NAME,

            torch_dtype=(
                torch.float16
            ),

            device_map="auto",
        )
    )

else:

    generator_model = (
        AutoModelForCausalLM
        .from_pretrained(

            GENERATOR_MODEL_NAME,

            torch_dtype="auto",

            device_map="cpu",
        )
    )


generator_model.eval()


print(
    f"Generator yükleme: "
    f"{time.perf_counter() - start:.2f} sn"
)


print(
    "\nGenerator device map:"
)


print(
    getattr(
        generator_model,
        "hf_device_map",
        "device_map bilgisi yok"
    )
)


# ============================================================
# QUERY EMBEDDING
# ============================================================

def embed_query(
    question
):

    start = (
        time.perf_counter()
    )


    with torch.inference_mode():

        vector = (
            embedding_model.encode(

                question,

                prompt_name="query",

                convert_to_numpy=True,

                normalize_embeddings=True,
            )
        )


    vector = (
        normalize_vector(
            vector
        )
    )


    elapsed = (
        time.perf_counter()
        - start
    )


    return (
        vector,
        elapsed
    )


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(
    question
):

    query_vector, embedding_seconds = (
        embed_query(
            question
        )
    )


    search_start = (
        time.perf_counter()
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


    search_seconds = (
        time.perf_counter()
        - search_start
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
            distance_to_similarity(
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

                "chunk_text": (
                    str(
                        document
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
            }
        )


    return (
        children,
        embedding_seconds,
        search_seconds,
    )


# ============================================================
# PARENT SELECTION
# ============================================================

def get_context_parents(
    children
):

    parents = []

    used_parent_ids = set()


    for child in children:

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


        info = (
            parent_lookup[
                parent_id
            ]
        )


        parents.append(
            {
                "parent_id": (
                    parent_id
                ),

                "article_id": (
                    info[
                        "article_id"
                    ]
                ),

                "title": (
                    info[
                        "title"
                    ]
                ),

                "url": (
                    info[
                        "url"
                    ]
                ),

                "parent_text": (
                    info[
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
            len(parents)
            >= MAX_CONTEXT_PARENTS
        ):

            break


    return parents


# ============================================================
# CONTEXT
# ============================================================

def build_context(
    parents
):

    sections = []


    for index, parent in enumerate(
        parents,
        start=1
    ):

        sections.append(
            f"""
[KAYNAK {index}]

Başlık:
{parent['title']}

URL:
{parent['url']}

Doküman:
{parent['parent_text']}
""".strip()
        )


    return (
        "\n\n".join(
            sections
        )
    )


# ============================================================
# GENERATE
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


    system_prompt = f"""
Sen Türkçe tıbbi dokümanlar üzerinde çalışan
bir Retrieval-Augmented Generation asistanısın.

Yalnızca verilen doküman bağlamını kullan.

Kurallar:

- Dokümanda olmayan bilgi ekleme.
- Genel bilgini kullanma.
- Tahmin yapma.
- Türkçe cevap ver.
- Cevabı açık ve doğrudan ver.
- Gereksiz uzun cevap üretme.
- Tıbbi teşhis koyma.
- Bağlam soruya cevap vermiyorsa yalnızca:

{NO_ANSWER_RESPONSE}

ifadesini döndür.
""".strip()


    user_prompt = f"""
DOKÜMAN BAĞLAMI:

{context}


SORU:

{question}


Yalnızca yukarıdaki dokümanlara göre cevap ver.
""".strip()


    messages = [

        {
            "role": "system",
            "content": system_prompt,
        },

        {
            "role": "user",
            "content": user_prompt,
        },
    ]


    try:

        prompt = (
            generator_tokenizer
            .apply_chat_template(

                messages,

                tokenize=False,

                add_generation_prompt=True,

                enable_thinking=False,
            )
        )

    except TypeError:

        prompt = (
            generator_tokenizer
            .apply_chat_template(

                messages,

                tokenize=False,

                add_generation_prompt=True,
            )
        )


    model_inputs = (
        generator_tokenizer(

            prompt,

            return_tensors="pt",
        )
    )


    model_device = (
        next(
            generator_model.parameters()
        ).device
    )


    model_inputs = {

        key: value.to(
            model_device
        )

        for key, value
        in model_inputs.items()
    }


    generation_start = (
        time.perf_counter()
    )


    with torch.inference_mode():

        output_ids = (
            generator_model.generate(

                **model_inputs,

                max_new_tokens=MAX_NEW_TOKENS,

                # Benchmark için deterministic.
                do_sample=False,

                repetition_penalty=1.05,

                pad_token_id=(
                    generator_tokenizer
                    .eos_token_id
                ),
            )
        )


    generation_seconds = (
        time.perf_counter()
        - generation_start
    )


    input_length = (
        model_inputs[
            "input_ids"
        ].shape[1]
    )


    generated_tokens = (
        output_ids[
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

        answer = (
            NO_ANSWER_RESPONSE
        )


    return (
        answer,
        generation_seconds
    )


# ============================================================
# TEK SORU İŞLE
# ============================================================

def process_question(
    question_number,
    question_type,
    question
):

    total_start = (
        time.perf_counter()
    )


    children, (
        embedding_seconds
    ), (
        search_seconds
    ) = retrieve(
        question
    )


    if not children:

        raise RuntimeError(
            "Retrieval sonucu boş."
        )


    top_child = (
        children[0]
    )


    top_similarity = float(
        top_child[
            "similarity"
        ]
    )


    # ========================================================
    # THRESHOLD
    # ========================================================

    accepted = (
        top_similarity
        >= FINAL_THRESHOLD
    )


    if accepted:

        decision = (
            "ACCEPT"
        )

    else:

        decision = (
            "REJECT"
        )


    # ========================================================
    # REJECT
    # ========================================================

    if not accepted:

        answer = (
            NO_ANSWER_RESPONSE
        )


        parents = []


        generation_seconds = 0.0


    # ========================================================
    # ACCEPT
    # ========================================================

    else:

        parents = (
            get_context_parents(
                children
            )
        )


        if not parents:

            answer = (
                NO_ANSWER_RESPONSE
            )


            generation_seconds = 0.0


        else:

            answer, generation_seconds = (
                generate_answer(

                    question,
                    parents,
                )
            )


    total_seconds = (
        time.perf_counter()
        - total_start
    )


    # ========================================================
    # EXPECTED THRESHOLD RESULT
    # ========================================================

    expected_accepted = (
        question_type
        == "positive"
    )


    threshold_correct = (
        accepted
        == expected_accepted
    )


    # ========================================================
    # SOURCE STRING
    # ========================================================

    source_titles = (
        " | ".join(
            [
                str(
                    parent[
                        "title"
                    ]
                )

                for parent in parents
            ]
        )
    )


    source_urls = (
        " | ".join(
            [
                str(
                    parent[
                        "url"
                    ]
                )

                for parent in parents
            ]
        )
    )


    source_parent_ids = (
        " | ".join(
            [
                str(
                    parent[
                        "parent_id"
                    ]
                )

                for parent in parents
            ]
        )
    )


    return {

        "question_number": (
            question_number
        ),

        "question_type": (
            question_type
        ),

        "question": (
            question
        ),

        "threshold": (
            FINAL_THRESHOLD
        ),

        "top1_similarity": (
            top_similarity
        ),

        "top1_title": (
            top_child[
                "title"
            ]
        ),

        "top1_child_id": (
            top_child[
                "child_id"
            ]
        ),

        "top1_parent_id": (
            top_child[
                "parent_id"
            ]
        ),

        "top1_url": (
            top_child[
                "url"
            ]
        ),

        "decision": (
            decision
        ),

        "threshold_correct": (
            threshold_correct
        ),

        "answer": (
            answer
        ),

        "is_fallback": (
            answer
            == NO_ANSWER_RESPONSE
        ),

        "context_parent_count": (
            len(
                parents
            )
        ),

        "source_parent_ids": (
            source_parent_ids
        ),

        "source_titles": (
            source_titles
        ),

        "source_urls": (
            source_urls
        ),

        "embedding_seconds": (
            embedding_seconds
        ),

        "search_seconds": (
            search_seconds
        ),

        "generation_seconds": (
            generation_seconds
        ),

        "total_seconds": (
            total_seconds
        ),
    }


# ============================================================
# SAVE FUNCTIONS
# ============================================================

def save_outputs(
    results
):

    result_df = (
        pd.DataFrame(
            results
        )
    )


    if len(result_df) == 0:

        return


    result_df = (
        result_df
        .sort_values(
            "question_number"
        )
    )


    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    result_df.to_csv(

        CSV_OUTPUT,

        index=False,

        encoding="utf-8-sig",
    )


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    json_records = (
        result_df
        .replace(
            {
                np.nan: None
            }
        )
        .to_dict(
            orient="records"
        )
    )


    with open(
        JSON_OUTPUT,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(

            json_records,

            file,

            ensure_ascii=False,

            indent=4,
        )


    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    with open(
        TXT_OUTPUT,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "TURKISH MEDICAL RAG - QUESTION / ANSWER RESULTS\n"
        )

        file.write(
            "=" * 80
            + "\n\n"
        )


        file.write(
            f"Embedding model : "
            f"{EMBEDDING_MODEL_NAME}\n"
        )


        file.write(
            f"Generator model : "
            f"{GENERATOR_MODEL_NAME}\n"
        )


        file.write(
            f"Threshold       : "
            f"{FINAL_THRESHOLD:.6f}\n\n"
        )


        for _, row in (
            result_df.iterrows()
        ):

            file.write(
                "=" * 80
                + "\n"
            )


            file.write(
                f"SORU {int(row['question_number'])}\n"
            )


            file.write(
                "=" * 80
                + "\n\n"
            )


            file.write(
                f"Tip:\n"
                f"{row['question_type']}\n\n"
            )


            file.write(
                f"Soru:\n"
                f"{row['question']}\n\n"
            )


            file.write(
                f"Top-1 similarity:\n"
                f"{row['top1_similarity']:.6f}\n\n"
            )


            file.write(
                f"Karar:\n"
                f"{row['decision']}\n\n"
            )


            file.write(
                f"Top-1 başlık:\n"
                f"{row['top1_title']}\n\n"
            )


            file.write(
                f"Cevap:\n"
                f"{row['answer']}\n\n"
            )


            if (
                row[
                    "source_titles"
                ]
            ):

                file.write(
                    "Kaynaklar:\n"
                )


                titles = str(
                    row[
                        "source_titles"
                    ]
                ).split(
                    " | "
                )


                urls = str(
                    row[
                        "source_urls"
                    ]
                ).split(
                    " | "
                )


                for index, (
                    title,
                    url
                ) in enumerate(

                    zip(
                        titles,
                        urls
                    ),

                    start=1
                ):

                    file.write(
                        f"{index}. "
                        f"{title}\n"
                    )


                    file.write(
                        f"   {url}\n"
                    )


                file.write(
                    "\n"
                )


            file.write(
                f"Generation süresi: "
                f"{row['generation_seconds']:.2f} sn\n"
            )


            file.write(
                f"Toplam süre    : "
                f"{row['total_seconds']:.2f} sn\n\n"
            )


# ============================================================
# RESUME
# ============================================================

results = []


completed_numbers = set()


if (
    RESUME
    and CSV_OUTPUT.exists()
):

    existing_df = (
        pd.read_csv(
            CSV_OUTPUT
        )
    )


    if (
        len(
            existing_df
        )
        > 0
    ):

        results = (
            existing_df
            .to_dict(
                orient="records"
            )
        )


        completed_numbers = set(
            existing_df[
                "question_number"
            ]
            .astype(int)
            .tolist()
        )


        print(
            "\nResume aktif."
        )


        print(
            f"Tamamlanmış soru: "
            f"{len(completed_numbers)}"
        )


# ============================================================
# BENCHMARK LOOP
# ============================================================

benchmark_start = (
    time.perf_counter()
)


for _, row in (
    questions_df.iterrows()
):

    question_number = int(
        row[
            "question_number"
        ]
    )


    question_type = str(
        row[
            "question_type"
        ]
    )


    question = str(
        row[
            "question"
        ]
    )


    # ========================================================
    # RESUME SKIP
    # ========================================================

    if (
        question_number
        in completed_numbers
    ):

        print(
            f"\n"
            f"{question_number:02d}. "
            "Zaten tamamlandı -> SKIP"
        )

        continue


    print(
        "\n"
        + "=" * 80
    )


    print(
        f"SORU "
        f"{question_number}/"
        f"{len(questions_df)}"
    )


    print(
        "=" * 80
    )


    print(
        f"\nTip  : "
        f"{question_type}"
    )


    print(
        f"Soru : "
        f"{question}"
    )


    # ========================================================
    # PROCESS
    # ========================================================

    result = (
        process_question(

            question_number,
            question_type,
            question,
        )
    )


    results.append(
        result
    )


    completed_numbers.add(
        question_number
    )


    # ========================================================
    # HER SORUDAN SONRA CHECKPOINT
    # ========================================================

    save_outputs(
        results
    )


    print(
        f"\nSimilarity : "
        f"{result['top1_similarity']:.6f}"
    )


    print(
        f"Threshold  : "
        f"{FINAL_THRESHOLD:.6f}"
    )


    print(
        f"Karar      : "
        f"{result['decision']}"
    )


    print(
        f"Başlık     : "
        f"{result['top1_title']}"
    )


    print(
        "\nCEVAP:"
    )


    print(
        result[
            "answer"
        ]
    )


    print(
        f"\nGeneration : "
        f"{result['generation_seconds']:.2f} sn"
    )


    print(
        f"Toplam     : "
        f"{result['total_seconds']:.2f} sn"
    )


    print(
        "\nCheckpoint kaydedildi."
    )


# ============================================================
# FINAL SAVE
# ============================================================

save_outputs(
    results
)


benchmark_seconds = (
    time.perf_counter()
    - benchmark_start
)


# ============================================================
# FINAL SUMMARY
# ============================================================

final_df = pd.DataFrame(
    results
)


final_df = (
    final_df
    .sort_values(
        "question_number"
    )
)


print(
    "\n"
    + "=" * 80
)

print(
    "FINAL RAG TEST TAMAMLANDI"
)

print(
    "=" * 80
)


print(
    f"\nToplam cevap: "
    f"{len(final_df)}"
)


if (
    "threshold_correct"
    in final_df.columns
):

    correct_count = int(
        final_df[
            "threshold_correct"
        ].sum()
    )


    print(
        f"Threshold doğru: "
        f"{correct_count}/"
        f"{len(final_df)}"
    )


print(
    f"\nToplam süre: "
    f"{benchmark_seconds / 60:.2f} dakika"
)


print(
    "\nOutput dosyaları:"
)


print(
    f"\nCSV:\n"
    f"{CSV_OUTPUT}"
)


print(
    f"\nJSON:\n"
    f"{JSON_OUTPUT}"
)


print(
    f"\nTXT:\n"
    f"{TXT_OUTPUT}"
)


print(
    "\n"
    + "=" * 80
)