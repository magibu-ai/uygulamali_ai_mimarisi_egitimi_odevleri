import gc
import json
import random
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
from tqdm import tqdm
from unsloth import FastLanguageModel


BASE_MODEL = "unsloth/Qwen3-1.7B"
LORA_MODEL = "sedayzc/qwen3-1.7b-turkish-electronics-lora-v2"

BENCHMARK_FILES = [
    Path("electronics_benchmark_results/turkish_electronics_benchmark.json"),
    Path("turkish_electronics_benchmark.json"),
]

SEED = 3407
PERMUTATIONS_PER_SAMPLE = 2
MAX_SEQ_LENGTH = 2048
MAX_NEW_TOKENS = 160
LOAD_IN_4BIT = True

OUTPUT_DIR = Path("electronics_benchmark_v3_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = OUTPUT_DIR / "electronics_benchmark_v3_checkpoint.json"
FINAL_FILE = OUTPUT_DIR / "electronics_benchmark_v3_results.json"

if not torch.cuda.is_available():
    raise RuntimeError("CUDA destekli GPU bulunamadı.")


def save_json(data: Any, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def clear_gpu() -> None:
    gc.collect()
    torch.cuda.empty_cache()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9çğıöşü]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_set(value: Any) -> set[str]:
    return {x for x in normalize_text(value).split() if len(x) >= 2}


def format_price(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".") + " TL"


def load_benchmark() -> dict[str, Any]:
    for path in BENCHMARK_FILES:
        if path.exists():
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            print("Benchmark dosyası:", path.resolve())
            print("Recommendation:", len(data["recommendation"]))
            print("Comparison:", len(data["comparison"]))
            return data

    raise FileNotFoundError(
        "turkish_electronics_benchmark.json bulunamadı."
    )


def product_card(product: dict[str, Any]) -> str:
    rating = product.get("rating")
    rating_text = f"{rating:.2f}/5" if rating is not None else "Bilinmiyor"

    return "\n".join([
        f"Ürün adı: {product['name']}",
        f"Marka: {product['brand']}",
        f"Fiyat: {format_price(product['price'])}",
        f"Kullanıcı puanı: {rating_text}",
        f"Değerlendirme sayısı: {product['review_count']}",
        f"Favori sayısı: {product['favorite_count']}",
        f"Kategori: {product['category']}",
    ])


def build_prompt(
    sample: dict[str, Any],
    products: list[dict[str, Any]],
    benchmark_type: str,
) -> str:
    cards = "\n\n---\n\n".join(product_card(x) for x in products)

    if benchmark_type == "recommendation":
        role = "Türkçe elektronik ürün danışmanı"
        task = (
            "Aşağıdaki adaylar arasından kullanıcının isteğine "
            "en uygun tek ürünü seç."
        )
        first_line = "Önerilen ürün:"
        question = sample["instruction"]
        question_label = "Kullanıcı isteği"
    else:
        role = "Türkçe elektronik ürün karşılaştırma danışmanı"
        task = (
            "Aşağıdaki iki ürünü verilen bilgilere göre karşılaştır "
            "ve soruya göre daha uygun olan tek ürünü seç."
        )
        first_line = "Kazanan ürün:"
        question = sample["instruction"]
        question_label = "Karşılaştırma sorusu"

    return f"""
Sen bir {role}sın.

{task}

Cevap formatı:
{first_line} <ürün adını aynen yaz>
Gerekçe: <kararı destekleyen kısa ve somut bir cümle>

Kurallar:
- Yalnızca verilen bilgilere dayan.
- Liste dışında ürün veya özellik uydurma.
- P1, P2, A veya B gibi seçenek kodları kullanma.
- Gerekçede yalnızca fiyat, kullanıcı puanı, değerlendirme
  sayısı, favori sayısı, marka ve kategori bilgilerini kullan.
- En fazla iki satır yaz.

{question_label}:
{question}

Ürünler:
{cards}
""".strip()


def load_model(model_name: str):
    print("\n" + "=" * 80)
    print("MODEL YÜKLENİYOR")
    print(model_name)
    print("=" * 80)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=LOAD_IN_4BIT,
    )
    FastLanguageModel.for_inference(model)

    if hasattr(model, "generation_config"):
        model.generation_config.max_length = None

    return model, tokenizer


def generate_response(model, tokenizer, prompt: str) -> str:
    formatted = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    inputs = tokenizer(
        formatted,
        return_tensors="pt",
        add_special_tokens=False,
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
    )
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    input_length = inputs["input_ids"].shape[1]

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            use_cache=True,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )

    return tokenizer.decode(
        output[0, input_length:],
        skip_special_tokens=True,
    ).strip()


def title_match_score(title: str, response: str) -> float:
    title_norm = normalize_text(title)
    response_norm = normalize_text(response)

    if title_norm and title_norm in response_norm:
        return 1.0

    title_tokens = token_set(title)
    response_tokens = token_set(response)

    if not title_tokens or not response_tokens:
        return 0.0

    overlap = title_tokens & response_tokens
    recall = len(overlap) / len(title_tokens)
    precision = len(overlap) / len(response_tokens)

    return (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )


def identify_product(
    response: str,
    products: list[dict[str, Any]],
) -> tuple[str | None, float]:
    scores = sorted(
        [
            (title_match_score(x["name"], response), x["name"])
            for x in products
        ],
        reverse=True,
    )

    best_score, best_name = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0.0

    if best_score < 0.18:
        return None, best_score

    if best_score < 0.45 and best_score - second_score < 0.04:
        return None, best_score

    return best_name, best_score


TASK_KEYWORDS = {
    "cheapest": {"ucuz", "fiyat", "uygun", "düşük", "dusuk"},
    "highest_rating": {"puan", "yüksek", "yuksek", "rating"},
    "higher_rating": {"puan", "yüksek", "yuksek", "rating"},
    "most_reviewed": {
        "değerlendirme", "degerlendirme", "yorum", "kullanıcı", "kullanici"
    },
    "more_reviewed": {
        "değerlendirme", "degerlendirme", "yorum", "kullanıcı", "kullanici"
    },
    "more_favorited": {"favori", "beğeni", "begeni"},
    "best_value": {
        "fiyat", "performans", "puan", "değerlendirme", "degerlendirme"
    },
}


def criterion_score(task: str, response: str) -> float:
    keywords = TASK_KEYWORDS.get(task, set())
    matched = keywords & token_set(response)
    divisor = 3.0 if task == "best_value" else 1.0
    return min(len(matched) / divisor, 1.0)


def format_score(response: str, benchmark_type: str) -> float:
    normalized = response.casefold()
    prefix = (
        "önerilen ürün:"
        if benchmark_type == "recommendation"
        else "kazanan ürün:"
    )
    has_prefix = prefix in normalized
    has_reason = "gerekçe:" in normalized
    lines = [x for x in response.splitlines() if x.strip()]
    concise = 1 <= len(lines) <= 4

    return (
        float(has_prefix)
        + float(has_reason)
        + float(concise)
    ) / 3.0


UNSUPPORTED_PATTERNS = {
    "ram": r"\b\d+\s*gb\s*(?:ram|bellek)\b",
    "ssd": r"\b\d+\s*(?:gb|tb)\s*ssd\b",
    "gpu": r"\b(?:rtx|gtx|rx)\s*\d{3,4}(?:\s*ti)?\b",
    "screen": (
        r"\b\d{2,3}\s*hz\b|"
        r"\b\d{2}(?:[.,]\d)?\s*(?:inç|inc|inch)\b"
    ),
}


def unsupported_claims(response: str) -> list[str]:
    return [
        name
        for name, pattern in UNSUPPORTED_PATTERNS.items()
        if re.search(pattern, response, flags=re.IGNORECASE)
    ]


def extract_numeric_claims(response: str) -> dict[str, list[float]]:
    claims = {
        "price": [],
        "rating": [],
        "review_count": [],
        "favorite_count": [],
    }

    for match in re.finditer(
        r"(\d[\d\.\s]{2,})\s*tl\b",
        response,
        flags=re.IGNORECASE,
    ):
        digits = re.sub(r"[^\d]", "", match.group(1))
        if digits:
            claims["price"].append(float(digits))

    for match in re.finditer(
        r"(?:puan|rating)\D{0,10}(\d(?:[.,]\d+)?)",
        response,
        flags=re.IGNORECASE,
    ):
        claims["rating"].append(
            float(match.group(1).replace(",", "."))
        )

    for match in re.finditer(
        r"(\d+)\s*(?:değerlendirme|degerlendirme|yorum)",
        response,
        flags=re.IGNORECASE,
    ):
        claims["review_count"].append(float(match.group(1)))

    for match in re.finditer(
        r"(\d+)\s*favori",
        response,
        flags=re.IGNORECASE,
    ):
        claims["favorite_count"].append(float(match.group(1)))

    return claims


def find_product(
    products: list[dict[str, Any]],
    name: str | None,
) -> dict[str, Any] | None:
    for product in products:
        if product["name"] == name:
            return product
    return None


def numeric_factuality(
    response: str,
    product: dict[str, Any] | None,
) -> tuple[float, int]:
    claims = extract_numeric_claims(response)
    claim_count = sum(len(x) for x in claims.values())

    if claim_count == 0:
        return 1.0, 0

    if product is None:
        return 0.0, claim_count

    expected = {
        "price": product["price"],
        "rating": product.get("rating"),
        "review_count": product["review_count"],
        "favorite_count": product["favorite_count"],
    }

    supported = 0

    for field, values in claims.items():
        target = expected[field]

        if target is None:
            continue

        tolerance = (
            max(100.0, target * 0.01)
            if field == "price"
            else 0.06
            if field == "rating"
            else 1.0
        )

        supported += sum(
            abs(value - target) <= tolerance
            for value in values
        )

    return supported / claim_count, claim_count


def build_cases(
    benchmark: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    cases = {
        "recommendation": [],
        "comparison": [],
    }

    for benchmark_type in cases:
        for index, sample in enumerate(
            benchmark[benchmark_type]
        ):
            source_products = (
                sample["candidates"]
                if benchmark_type == "recommendation"
                else list(sample["products"].values())
            )

            for permutation in range(
                PERMUTATIONS_PER_SAMPLE
            ):
                products = list(source_products)
                random.Random(
                    SEED
                    + index * 100
                    + permutation
                    + (
                        100000
                        if benchmark_type == "comparison"
                        else 0
                    )
                ).shuffle(products)

                cases[benchmark_type].append(
                    {
                        "sample": sample,
                        "products": products,
                        "permutation": permutation,
                    }
                )

    return cases


def evaluate_case(
    response: str,
    sample: dict[str, Any],
    products: list[dict[str, Any]],
    benchmark_type: str,
) -> dict[str, Any]:
    predicted_name, match_score = identify_product(
        response,
        products,
    )

    predicted_product = find_product(
        products,
        predicted_name,
    )

    selection_correct = (
        predicted_name == sample["expected_product"]
    )

    criterion = criterion_score(
        sample["task"],
        response,
    )

    formatting = format_score(
        response,
        benchmark_type,
    )

    unsupported = unsupported_claims(
        response
    )

    factuality, numeric_claim_count = (
        numeric_factuality(
            response,
            predicted_product,
        )
    )

    hallucination_free = int(
        not unsupported
        and factuality >= 0.999
    )

    first_position = (
        predicted_name == products[0]["name"]
    )

    composite = (
        0.50 * float(selection_correct)
        + 0.15 * criterion
        + 0.15 * factuality
        + 0.10 * hallucination_free
        + 0.10 * formatting
    )

    return {
        "predicted_product": predicted_name,
        "match_score": match_score,
        "selection_correct": selection_correct,
        "criterion_mention_score": criterion,
        "numeric_factuality": factuality,
        "numeric_claim_count": numeric_claim_count,
        "unsupported_claims": unsupported,
        "hallucination_free": hallucination_free,
        "format_compliance": formatting,
        "first_position_selected": first_position,
        "composite_score": composite,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)

    def mean(key: str) -> float:
        return (
            sum(float(x[key]) for x in results) / total
            if total
            else 0.0
        )

    grouped = defaultdict(list)
    for result in results:
        grouped[result["sample_id"]].append(result)

    robust_correct = sum(
        all(x["selection_correct"] for x in group)
        for group in grouped.values()
    )

    consistent = sum(
        len({x["predicted_product"] for x in group}) == 1
        for group in grouped.values()
    )

    by_task = {}

    for task in sorted({x["task"] for x in results}):
        subset = [x for x in results if x["task"] == task]
        by_task[task] = {
            "cases": len(subset),
            "selection_accuracy": (
                sum(x["selection_correct"] for x in subset)
                / len(subset)
            ),
            "composite_score": (
                sum(x["composite_score"] for x in subset)
                / len(subset)
            ),
        }

    unique_samples = len(grouped)
    nulls = sum(x["predicted_product"] is None for x in results)

    return {
        "inference_cases": total,
        "unique_samples": unique_samples,
        "selection_accuracy": mean("selection_correct"),
        "robust_accuracy": (
            robust_correct / unique_samples
            if unique_samples
            else 0.0
        ),
        "permutation_consistency": (
            consistent / unique_samples
            if unique_samples
            else 0.0
        ),
        "valid_prediction_rate": (
            (total - nulls) / total
            if total
            else 0.0
        ),
        "criterion_mention_score": mean(
            "criterion_mention_score"
        ),
        "numeric_factuality": mean(
            "numeric_factuality"
        ),
        "hallucination_free_rate": mean(
            "hallucination_free"
        ),
        "format_compliance": mean(
            "format_compliance"
        ),
        "first_position_selection_rate": mean(
            "first_position_selected"
        ),
        "composite_score": mean(
            "composite_score"
        ),
        "null_predictions": nulls,
        "unsupported_claims_total": sum(
            len(x["unsupported_claims"])
            for x in results
        ),
        "by_task": by_task,
    }


def run_cases(
    model,
    tokenizer,
    cases: list[dict[str, Any]],
    benchmark_type: str,
    label: str,
) -> dict[str, Any]:
    results = []

    for case in tqdm(cases, desc=label):
        sample = case["sample"]
        products = case["products"]

        response = generate_response(
            model,
            tokenizer,
            build_prompt(
                sample,
                products,
                benchmark_type,
            ),
        )

        metrics = evaluate_case(
            response,
            sample,
            products,
            benchmark_type,
        )

        results.append(
            {
                "sample_id": sample["id"],
                "permutation": case["permutation"],
                "task": sample["task"],
                "expected_product": sample["expected_product"],
                "first_product_in_prompt": products[0]["name"],
                "response": response,
                **metrics,
            }
        )

    return {
        "summary": summarize(results),
        "results": results,
    }


def benchmark_model(
    model_name: str,
    label: str,
    cases: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    model, tokenizer = load_model(model_name)

    try:
        recommendation = run_cases(
            model,
            tokenizer,
            cases["recommendation"],
            "recommendation",
            label + " — V3 Recommendation",
        )

        comparison = run_cases(
            model,
            tokenizer,
            cases["comparison"],
            "comparison",
            label + " — V3 Comparison",
        )

    finally:
        del model
        del tokenizer
        clear_gpu()

    return {
        "model": label,
        "model_id": model_name,
        "recommendation": recommendation,
        "comparison": comparison,
    }


def print_section(
    title: str,
    base_data: dict[str, Any],
    lora_data: dict[str, Any],
) -> None:
    base = base_data["summary"]
    lora = lora_data["summary"]

    print("\n" + title)
    print("-" * 92)

    metrics = [
        ("selection_accuracy", "Selection accuracy"),
        ("robust_accuracy", "Robust accuracy"),
        ("permutation_consistency", "Permutation consistency"),
        ("criterion_mention_score", "Criterion mention"),
        ("numeric_factuality", "Numeric factuality"),
        ("hallucination_free_rate", "Hallucination-free"),
        ("format_compliance", "Format compliance"),
        ("valid_prediction_rate", "Valid prediction"),
        ("first_position_selection_rate", "First-position selection"),
        ("composite_score", "Composite score"),
    ]

    for key, label in metrics:
        base_value = base[key] * 100
        lora_value = lora[key] * 100

        print(
            f"{label:27s} | "
            f"Base: {base_value:6.2f}% | "
            f"LoRA: {lora_value:6.2f}% | "
            f"Delta: {lora_value - base_value:+6.2f}"
        )

    print("\nGörev bazlı selection accuracy:")

    for task in sorted(
        set(base["by_task"])
        | set(lora["by_task"])
    ):
        base_score = (
            base["by_task"][task]["selection_accuracy"]
            * 100
        )
        lora_score = (
            lora["by_task"][task]["selection_accuracy"]
            * 100
        )

        print(
            f"{task:18s} | "
            f"Base: {base_score:6.2f}% | "
            f"LoRA: {lora_score:6.2f}% | "
            f"Delta: {lora_score - base_score:+6.2f}"
        )


def main() -> None:
    print("=" * 92)
    print("TURKISH ELECTRONICS BENCHMARK V3")
    print("=" * 92)
    print("GPU:", torch.cuda.get_device_name(0))
    print("Seed:", SEED)
    print("Permutation/sample:", PERMUTATIONS_PER_SAMPLE)

    benchmark = load_benchmark()
    cases = build_cases(benchmark)

    print(
        "Recommendation inference case:",
        len(cases["recommendation"]),
    )
    print(
        "Comparison inference case:",
        len(cases["comparison"]),
    )

    results = {
        "config": {
            "seed": SEED,
            "permutations_per_sample": (
                PERMUTATIONS_PER_SAMPLE
            ),
            "max_seq_length": MAX_SEQ_LENGTH,
            "max_new_tokens": MAX_NEW_TOKENS,
            "load_in_4bit": LOAD_IN_4BIT,
            "composite_weights": {
                "selection_accuracy": 0.50,
                "criterion_mention": 0.15,
                "numeric_factuality": 0.15,
                "hallucination_free": 0.10,
                "format_compliance": 0.10,
            },
            "methodology_note": (
                "The existing fixed benchmark is reused. "
                "No new training dataset is created. "
                "Hallucination means claims unsupported by "
                "the product fields shown in the prompt."
            ),
        }
    }

    results["base"] = benchmark_model(
        BASE_MODEL,
        "Base Qwen3-1.7B",
        cases,
    )

    save_json(results, CHECKPOINT_FILE)
    print(
        "\nBase checkpoint kaydedildi:",
        CHECKPOINT_FILE.resolve(),
    )

    results["lora"] = benchmark_model(
        LORA_MODEL,
        "Qwen3-1.7B + Electronics LoRA",
        cases,
    )

    save_json(results, FINAL_FILE)

    print("\n" + "=" * 92)
    print("FINAL SUMMARY")
    print("=" * 92)

    print_section(
        "V3 RECOMMENDATION",
        results["base"]["recommendation"],
        results["lora"]["recommendation"],
    )

    print_section(
        "V3 COMPARISON",
        results["base"]["comparison"],
        results["lora"]["comparison"],
    )

    print("\n" + "=" * 92)
    print("BENCHMARK TAMAMLANDI")
    print("=" * 92)
    print("\nFinal sonuç:", FINAL_FILE.resolve())


if __name__ == "__main__":
    main()