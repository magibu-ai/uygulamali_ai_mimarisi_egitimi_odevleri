import gc
import json
import re
from pathlib import Path

import torch
from datasets import load_dataset
from unsloth import FastLanguageModel


# ============================================================
# MODELLER
# ============================================================

BASE_MODEL = "unsloth/Qwen3-1.7B"

LORA_MODEL = (
    "sedayzc/"
    "qwen3-1.7b-turkish-electronics-lora-v2"
)

MAX_SEQ_LENGTH = 1024
LOAD_IN_4BIT = True


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_DIR = Path("benchmark_results")
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FINAL_OUTPUT_FILE = (
    OUTPUT_DIR
    / "benchmark_results_v2.json"
)

CHECKPOINT_FILE = (
    OUTPUT_DIR
    / "benchmark_checkpoint.json"
)


# ============================================================
# BENCHMARK AYARLARI
# ============================================================

SEED = 3407

# İlk ciddi karşılaştırma için 500 örnek.
# Daha sonra full benchmark yapılabilir.
MMLU_LIMIT = 500
GSM8K_LIMIT = 500
TURKISH_MMLU_LIMIT = 500


# ============================================================
# GPU
# ============================================================

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA GPU bulunamadı. "
        "Benchmark GPU üzerinde çalıştırılmalıdır."
    )


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def clear_gpu():
    """
    GPU belleğini mümkün olduğunca temizler.
    """

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def save_json(
    data,
    path,
):
    """
    Sonuçları JSON dosyasına güvenli şekilde yazar.
    """

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def load_model(
    model_name,
):
    """
    Base veya LoRA modelini 4-bit olarak yükler.
    """

    print(
        "\n"
        + "=" * 80
    )

    print(
        "MODEL YÜKLENİYOR"
    )

    print(
        model_name
    )

    print(
        "=" * 80
    )

    model, tokenizer = (
        FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=MAX_SEQ_LENGTH,
            dtype=None,
            load_in_4bit=LOAD_IN_4BIT,
        )
    )

    FastLanguageModel.for_inference(
        model
    )

    # max_new_tokens ile max_length warning'ini önle
    if hasattr(
        model,
        "generation_config",
    ):

        model.generation_config.max_length = None

    return model, tokenizer


def generate(
    model,
    tokenizer,
    prompt,
    max_new_tokens=64,
):
    """
    Deterministic inference.

    Benchmark sırasında sampling kapalıdır.
    """

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    formatted = (
        tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    )

    inputs = tokenizer(
        formatted,
        return_tensors="pt",
        add_special_tokens=False,
    )

    inputs = {
        key: value.to(
            model.device
        )
        for key, value
        in inputs.items()
    }

    input_length = (
        inputs[
            "input_ids"
        ].shape[1]
    )

    with torch.inference_mode():

        outputs = model.generate(

            **inputs,

            max_new_tokens=max_new_tokens,

            # Benchmark için deterministic
            do_sample=False,

            use_cache=True,

            eos_token_id=(
                tokenizer.eos_token_id
            ),

            pad_token_id=(
                tokenizer.pad_token_id
            ),
        )

    generated = (
        outputs[
            0,
            input_length:
        ]
    )

    text = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    )

    return text.strip()


# ============================================================
# MULTIPLE CHOICE EXTRACTOR
# ============================================================

def extract_choice(
    text,
    valid_choices=(
        "A",
        "B",
        "C",
        "D",
    ),
):
    """
    Multiple-choice cevabını çıkarır.

    valid_choices dinamik olduğu için
    A-D veya A-E gibi benchmarkları destekler.
    """

    if not text:
        return None

    text = (
        text
        .strip()
        .upper()
    )

    valid_choices = tuple(
        str(choice).upper()
        for choice
        in valid_choices
    )

    # Direkt sadece harf döndürdüyse
    if text in valid_choices:
        return text

    choice_pattern = (
        "["
        + "".join(
            re.escape(choice)
            for choice
            in valid_choices
        )
        + "]"
    )

    patterns = [

        # CEVAP: B
        rf"CEVAP\s*[:\-]?\s*{choice_pattern}",

        # ANSWER: B
        rf"ANSWER\s*[:\-]?\s*{choice_pattern}",

        # DOĞRU CEVAP: B
        rf"DOĞRU\s+CEVAP\s*[:\-]?\s*{choice_pattern}",

        # CORRECT ANSWER: B
        rf"CORRECT\s+ANSWER\s*[:\-]?\s*{choice_pattern}",

        # B ŞIKKI
        rf"\b{choice_pattern}\s*ŞIKKI\b",

        # B)
        rf"^\s*{choice_pattern}\s*[\.\)\-:]",

        # **B**
        rf"\*\*\s*{choice_pattern}\s*\*\*",

        # Son fallback
        rf"\b{choice_pattern}\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:

            matched_text = (
                match.group(0)
            )

            for choice in valid_choices:

                if re.search(
                    rf"\b{re.escape(choice)}\b",
                    matched_text,
                ):

                    return choice

    return None


# ============================================================
# GSM8K EXTRACTOR
# ============================================================

def normalize_number(
    value,
):
    """
    Sayısal cevabı karşılaştırılabilir hale getirir.
    """

    if value is None:
        return None

    value = (
        str(value)
        .strip()
        .replace(",", "")
    )

    # 72.0 -> 72
    try:

        numeric = float(
            value
        )

        if numeric.is_integer():
            return str(
                int(numeric)
            )

        return str(
            numeric
        )

    except ValueError:

        return value


def extract_number(
    text,
):
    """
    Model cevabındaki final sayıyı çıkarır.

    Öncelik:
    FINAL ANSWER / CEVAP / SONUÇ

    Bulunamazsa cevaptaki son sayıyı alır.
    """

    if not text:
        return None

    cleaned = (
        text
        .strip()
        .replace(",", "")
    )

    explicit_patterns = [

        r"(?:FINAL\s+ANSWER|FINAL\s+CEVAP)"
        r"\s*[:=\-]?\s*"
        r"(-?\d+(?:\.\d+)?)",

        r"(?:CEVAP|ANSWER|SONUÇ|RESULT)"
        r"\s*[:=\-]?\s*"
        r"(-?\d+(?:\.\d+)?)",
    ]

    for pattern in explicit_patterns:

        match = re.search(
            pattern,
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    numbers = re.findall(
        r"-?\d+(?:\.\d+)?",
        cleaned,
    )

    if not numbers:
        return None

    return numbers[-1]


# ============================================================
# BENCHMARK SAMPLE HELPER
# ============================================================

def deterministic_sample(
    dataset,
    limit,
):
    """
    Base ve LoRA'nın aynı örnekleri görmesini sağlar.
    """

    dataset = dataset.shuffle(
        seed=SEED
    )

    if limit is None:
        return dataset

    sample_size = min(
        limit,
        len(dataset),
    )

    return dataset.select(
        range(
            sample_size
        )
    )


# ============================================================
# MMLU
# ============================================================

def run_mmlu(
    model,
    tokenizer,
    limit=MMLU_LIMIT,
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        "MMLU"
    )

    print(
        "=" * 80
    )

    dataset = load_dataset(
        "cais/mmlu",
        "all",
        split="test",
    )

    dataset = deterministic_sample(
        dataset,
        limit,
    )

    correct = 0
    null_predictions = 0

    results = []

    letters = [
        "A",
        "B",
        "C",
        "D",
    ]

    for index, row in enumerate(
        dataset,
        start=1,
    ):

        question = (
            row[
                "question"
            ]
        )

        choices = (
            row[
                "choices"
            ]
        )

        answer_index = (
            row[
                "answer"
            ]
        )

        gold = (
            letters[
                answer_index
            ]
        )

        prompt = f"""
Aşağıdaki çoktan seçmeli soruyu cevapla.

Açıklama yapma.
Soruyu çözmek için içinden düşün, ancak cevabında yalnızca aşağıdaki formatı kullan:

CEVAP: X

Buradaki X yalnızca A, B, C veya D olabilir.

Soru:
{question}

A) {choices[0]}
B) {choices[1]}
C) {choices[2]}
D) {choices[3]}

Yanıt:
""".strip()

        response = generate(
            model,
            tokenizer,
            prompt,
            max_new_tokens=32,
        )

        predicted = extract_choice(
            response,
            valid_choices=letters,
        )

        if predicted is None:
            null_predictions += 1

        is_correct = (
            predicted == gold
        )

        correct += int(
            is_correct
        )

        results.append(
            {
                "question": question,
                "choices": choices,
                "gold": gold,
                "prediction": predicted,
                "raw_response": response,
                "correct": is_correct,
            }
        )

        if (
            index % 25 == 0
            or index == len(dataset)
        ):

            print(
                f"MMLU "
                f"{index}/"
                f"{len(dataset)}"
            )

    total = len(
        dataset
    )

    accuracy = (
        correct / total
        if total
        else 0
    )

    valid_prediction_rate = (
        (
            total
            - null_predictions
        )
        / total
        if total
        else 0
    )

    print(
        "\nMMLU sonuç:"
    )

    print(
        f"Doğru: "
        f"{correct}/{total}"
    )

    print(
        f"Null prediction: "
        f"{null_predictions}"
    )

    print(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        "Valid prediction rate: "
        f"{valid_prediction_rate * 100:.2f}%"
    )

    return {
        "benchmark": "MMLU",
        "samples": total,
        "correct": correct,
        "null_predictions": (
            null_predictions
        ),
        "valid_prediction_rate": (
            valid_prediction_rate
        ),
        "accuracy": accuracy,
        "results": results,
    }


# ============================================================
# GSM8K
# ============================================================

def run_gsm8k(
    model,
    tokenizer,
    limit=GSM8K_LIMIT,
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        "GSM8K"
    )

    print(
        "=" * 80
    )

    dataset = load_dataset(
        "openai/gsm8k",
        "main",
        split="test",
    )

    dataset = deterministic_sample(
        dataset,
        limit,
    )

    correct = 0
    null_predictions = 0

    results = []

    for index, row in enumerate(
        dataset,
        start=1,
    ):

        question = (
            row[
                "question"
            ]
        )

        gold_raw = (
            row[
                "answer"
            ]
        )

        if "####" in gold_raw:

            gold = (
                gold_raw
                .split(
                    "####"
                )[-1]
                .strip()
            )

        else:

            gold = extract_number(
                gold_raw
            )

        gold = normalize_number(
            gold
        )

        prompt = f"""
Aşağıdaki matematik problemini çöz.

Problemi doğru şekilde hesapla.

Cevabının son satırını mutlaka şu formatta yaz:

CEVAP: SAYI

Problem:
{question}
""".strip()

        response = generate(
            model,
            tokenizer,
            prompt,
            max_new_tokens=192,
        )

        predicted = normalize_number(
            extract_number(
                response
            )
        )

        if predicted is None:
            null_predictions += 1

        is_correct = (
            predicted == gold
        )

        correct += int(
            is_correct
        )

        results.append(
            {
                "question": question,
                "gold": gold,
                "prediction": predicted,
                "raw_response": response,
                "correct": is_correct,
            }
        )

        if (
            index % 25 == 0
            or index == len(dataset)
        ):

            print(
                f"GSM8K "
                f"{index}/"
                f"{len(dataset)}"
            )

    total = len(
        dataset
    )

    accuracy = (
        correct / total
        if total
        else 0
    )

    valid_prediction_rate = (
        (
            total
            - null_predictions
        )
        / total
        if total
        else 0
    )

    print(
        "\nGSM8K sonuç:"
    )

    print(
        f"Doğru: "
        f"{correct}/{total}"
    )

    print(
        f"Null prediction: "
        f"{null_predictions}"
    )

    print(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        "Valid prediction rate: "
        f"{valid_prediction_rate * 100:.2f}%"
    )

    return {
        "benchmark": "GSM8K",
        "samples": total,
        "correct": correct,
        "null_predictions": (
            null_predictions
        ),
        "valid_prediction_rate": (
            valid_prediction_rate
        ),
        "accuracy": accuracy,
        "results": results,
    }


# ============================================================
# TURKISH MMLU
# ============================================================

def run_turkish_mmlu(
    model,
    tokenizer,
    limit=TURKISH_MMLU_LIMIT,
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        "TURKISH MMLU"
    )

    print(
        "=" * 80
    )

    # ÖNEMLİ:
    # train değil, özel MMLU split'i.
    dataset = load_dataset(
        "alibayram/turkish_mmlu",
        split="mmlu",
    )

    print(
        "TurkishMMLU kolonları:",
        dataset.column_names,
    )

    dataset = deterministic_sample(
        dataset,
        limit,
    )

    print(
        "\nÖrnek TurkishMMLU kaydı:"
    )

    print(
        dataset[0]
    )

    results = []

    correct = 0
    null_predictions = 0

    for index, row in enumerate(
        dataset,
        start=1,
    ):

        question = (
            row.get(
                "soru"
            )
            or row.get(
                "question"
            )
        )

        choices = (
            row.get(
                "secenekler"
            )
            or row.get(
                "choices"
            )
            or row.get(
                "options"
            )
        )

        answer = (
            row.get(
                "cevap"
            )
        )

        if answer is None:

            answer = (
                row.get(
                    "answer"
                )
            )

        if answer is None:

            answer = (
                row.get(
                    "label"
                )
            )

        if (
            question is None
            or choices is None
            or answer is None
        ):

            continue

        # ----------------------------------------------------
        # SEÇENEKLER
        # ----------------------------------------------------

        if isinstance(
            choices,
            dict,
        ):

            choice_map = {
                str(key).upper(): value
                for key, value
                in choices.items()
            }

        elif isinstance(
            choices,
            list,
        ):

            choice_map = {
                chr(
                    65 + i
                ): value
                for i, value
                in enumerate(
                    choices
                )
            }

        else:

            continue

        valid_letters = list(
            choice_map.keys()
        )

        # ----------------------------------------------------
        # GOLD ANSWER
        # ----------------------------------------------------

        if isinstance(
            answer,
            int,
        ):

            if (
                answer < 0
                or answer
                >= len(
                    valid_letters
                )
            ):

                continue

            gold = (
                valid_letters[
                    answer
                ]
            )

        else:

            answer_string = (
                str(
                    answer
                )
                .strip()
                .upper()
            )

            # cevap "4" gibi string indeks olarak geldiyse
            if (
                answer_string
                .isdigit()
            ):

                answer_index = int(
                    answer_string
                )

                if (
                    0
                    <= answer_index
                    < len(
                        valid_letters
                    )
                ):

                    gold = (
                        valid_letters[
                            answer_index
                        ]
                    )

                else:

                    continue

            else:

                gold = (
                    answer_string
                )

        options_text = "\n".join(

            f"{key}) {value}"

            for key, value
            in choice_map.items()
        )

        choices_display = ", ".join(
            valid_letters
        )

        prompt = f"""
Aşağıdaki Türkçe çoktan seçmeli soruyu cevapla.

Açıklama yapma.

Soruyu çözmek için içinden düşün, ancak cevabında yalnızca aşağıdaki formatı kullan:

CEVAP: X

X yalnızca şu seçeneklerden biri olabilir:

{choices_display}

Soru:
{question}

{options_text}

Yanıt:
""".strip()

        response = generate(
            model,
            tokenizer,
            prompt,
            max_new_tokens=32,
        )

        predicted = extract_choice(
            response,
            tuple(
                valid_letters
            ),
        )

        if predicted is None:
            null_predictions += 1

        is_correct = (
            predicted == gold
        )

        correct += int(
            is_correct
        )

        results.append(
            {
                "question": question,
                "choices": choice_map,
                "gold": gold,
                "prediction": predicted,
                "raw_response": response,
                "correct": is_correct,
            }
        )

        if (
            index % 25 == 0
            or index == len(dataset)
        ):

            print(
                f"TurkishMMLU "
                f"{index}/"
                f"{len(dataset)}"
            )

    evaluated = len(
        results
    )

    accuracy = (
        correct / evaluated
        if evaluated
        else 0
    )

    valid_prediction_rate = (
        (
            evaluated
            - null_predictions
        )
        / evaluated
        if evaluated
        else 0
    )

    print(
        "\nTurkishMMLU sonuç:"
    )

    print(
        f"Doğru: "
        f"{correct}/{evaluated}"
    )

    print(
        f"Null prediction: "
        f"{null_predictions}"
    )

    print(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        "Valid prediction rate: "
        f"{valid_prediction_rate * 100:.2f}%"
    )

    return {
        "benchmark": (
            "TurkishMMLU"
        ),
        "samples": evaluated,
        "correct": correct,
        "null_predictions": (
            null_predictions
        ),
        "valid_prediction_rate": (
            valid_prediction_rate
        ),
        "accuracy": accuracy,
        "results": results,
    }


# ============================================================
# CHECKPOINT HELPER
# ============================================================

def save_checkpoint(
    all_results,
):
    """
    Her benchmark sonrasında ara sonuç kaydeder.
    """

    save_json(
        all_results,
        CHECKPOINT_FILE,
    )

    print(
        "\nAra sonuç kaydedildi:"
    )

    print(
        CHECKPOINT_FILE.resolve()
    )


# ============================================================
# BİR MODELİ TÜM BENCHMARKLARDA ÇALIŞTIR
# ============================================================

def benchmark_model(
    model_name,
    model_label,
    all_results,
    result_key,
):

    model, tokenizer = load_model(
        model_name
    )

    model_results = {
        "model": model_label,
        "model_id": model_name,
    }

    all_results[
        result_key
    ] = model_results

    try:

        # ----------------------------------------------------
        # MMLU
        # ----------------------------------------------------

        try:

            model_results[
                "mmlu"
            ] = run_mmlu(
                model,
                tokenizer,
            )

        except Exception as error:

            print(
                "\nMMLU HATASI:"
            )

            print(
                error
            )

            model_results[
                "mmlu"
            ] = {
                "benchmark": "MMLU",
                "status": "error",
                "error": str(
                    error
                ),
            }

        save_checkpoint(
            all_results
        )

        # ----------------------------------------------------
        # GSM8K
        # ----------------------------------------------------

        try:

            model_results[
                "gsm8k"
            ] = run_gsm8k(
                model,
                tokenizer,
            )

        except Exception as error:

            print(
                "\nGSM8K HATASI:"
            )

            print(
                error
            )

            model_results[
                "gsm8k"
            ] = {
                "benchmark": "GSM8K",
                "status": "error",
                "error": str(
                    error
                ),
            }

        save_checkpoint(
            all_results
        )

        # ----------------------------------------------------
        # TURKISH MMLU
        # ----------------------------------------------------

        try:

            model_results[
                "turkish_mmlu"
            ] = run_turkish_mmlu(
                model,
                tokenizer,
            )

        except Exception as error:

            print(
                "\nTurkishMMLU HATASI:"
            )

            print(
                error
            )

            model_results[
                "turkish_mmlu"
            ] = {
                "benchmark": (
                    "TurkishMMLU"
                ),
                "status": "error",
                "error": str(
                    error
                ),
            }

        save_checkpoint(
            all_results
        )

    finally:

        del model
        del tokenizer

        clear_gpu()

    return model_results


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    base_results,
    lora_results,
):

    print(
        "\n"
        + "=" * 80
    )

    print(
        "BENCHMARK SUMMARY"
    )

    print(
        "=" * 80
    )

    benchmark_keys = [
        "mmlu",
        "gsm8k",
        "turkish_mmlu",
    ]

    for benchmark_key in benchmark_keys:

        base_benchmark = (
            base_results.get(
                benchmark_key,
                {},
            )
        )

        lora_benchmark = (
            lora_results.get(
                benchmark_key,
                {},
            )
        )

        print(
            "\n"
            + benchmark_key.upper()
        )

        if (
            "accuracy"
            not in base_benchmark
            or
            "accuracy"
            not in lora_benchmark
        ):

            print(
                "Benchmark tamamlanamadı."
            )

            continue

        base_score = (
            base_benchmark[
                "accuracy"
            ]
            * 100
        )

        lora_score = (
            lora_benchmark[
                "accuracy"
            ]
            * 100
        )

        delta = (
            lora_score
            - base_score
        )

        base_null = (
            base_benchmark
            .get(
                "null_predictions",
                0,
            )
        )

        lora_null = (
            lora_benchmark
            .get(
                "null_predictions",
                0,
            )
        )

        base_valid = (
            base_benchmark
            .get(
                "valid_prediction_rate",
                1.0,
            )
            * 100
        )

        lora_valid = (
            lora_benchmark
            .get(
                "valid_prediction_rate",
                1.0,
            )
            * 100
        )

        print(
            f"Base accuracy : "
            f"{base_score:.2f}%"
        )

        print(
            f"LoRA accuracy : "
            f"{lora_score:.2f}%"
        )

        print(
            f"Delta         : "
            f"{delta:+.2f}"
        )

        print(
            f"Base null     : "
            f"{base_null}"
        )

        print(
            f"LoRA null     : "
            f"{lora_null}"
        )

        print(
            f"Base valid    : "
            f"{base_valid:.2f}%"
        )

        print(
            f"LoRA valid    : "
            f"{lora_valid:.2f}%"
        )


# ============================================================
# MAIN
# ============================================================

print(
    "=" * 80
)

print(
    "QWEN3 BASE vs LoRA STANDARD BENCHMARKS V2"
)

print(
    "=" * 80
)

print(
    "PyTorch:",
    torch.__version__,
)

print(
    "CUDA:",
    torch.cuda.is_available(),
)

print(
    "GPU:",
    torch.cuda.get_device_name(
        0
    ),
)

gpu_memory = (
    torch.cuda
    .get_device_properties(
        0
    )
    .total_memory
    / 1024**3
)

print(
    f"GPU VRAM: "
    f"{gpu_memory:.2f} GB"
)

print(
    "\nBenchmark sample size:"
)

print(
    "MMLU:",
    MMLU_LIMIT,
)

print(
    "GSM8K:",
    GSM8K_LIMIT,
)

print(
    "TurkishMMLU:",
    TURKISH_MMLU_LIMIT,
)

print(
    "\nSeed:",
    SEED,
)


# ============================================================
# RESULT CONTAINER
# ============================================================

all_results = {
    "config": {
        "seed": SEED,
        "mmlu_limit": (
            MMLU_LIMIT
        ),
        "gsm8k_limit": (
            GSM8K_LIMIT
        ),
        "turkish_mmlu_limit": (
            TURKISH_MMLU_LIMIT
        ),
        "max_seq_length": (
            MAX_SEQ_LENGTH
        ),
        "load_in_4bit": (
            LOAD_IN_4BIT
        ),
    }
}


# ============================================================
# BASE
# ============================================================

base_results = benchmark_model(

    BASE_MODEL,

    "Base Qwen3-1.7B",

    all_results,

    "base",
)


# ============================================================
# LoRA
# ============================================================

lora_results = benchmark_model(

    LORA_MODEL,

    (
        "Qwen3-1.7B "
        "+ Electronics LoRA"
    ),

    all_results,

    "lora",
)


# ============================================================
# FINAL SAVE
# ============================================================

save_json(
    all_results,
    FINAL_OUTPUT_FILE,
)


# ============================================================
# SUMMARY
# ============================================================

print_summary(
    base_results,
    lora_results,
)


print(
    "\n"
    + "=" * 80
)

print(
    "BENCHMARK TAMAMLANDI"
)

print(
    "=" * 80
)

print(
    "\nFinal sonuç dosyası:"
)

print(
    FINAL_OUTPUT_FILE.resolve()
)

print(
    "\nCheckpoint dosyası:"
)

print(
    CHECKPOINT_FILE.resolve()
)