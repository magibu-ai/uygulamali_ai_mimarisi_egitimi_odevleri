"""E-Commerce NER Synthetic Data Generator using NVIDIA NeMo Data Designer.

Generates realistic Turkish e-commerce product titles and accurate NER entity annotations
(BRAND, CATEGORY, MODEL, COLOR, SIZE_VARIANT, GENDER_TARGET, MATERIAL, SPECIFICATION)
using HF Inference Provider (deepseek-ai/DeepSeek-V4-Flash:fireworks-ai).
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

try:
    from data_designer.interface import DataDesigner
    from data_designer.config import (
        CategorySamplerParams,
        DataDesignerConfigBuilder,
        LLMTextColumnConfig,
        ModelConfig,
        ModelProvider,
        SamplerColumnConfig,
        SamplerType,
    )
except ImportError:
    try:
        from data_designer.essentials import (
            CategorySamplerParams,
            DataDesigner,
            DataDesignerConfigBuilder,
            LLMTextColumnConfig,
            ModelConfig,
            ModelProvider,
            SamplerColumnConfig,
            SamplerType,
        )
    except ImportError:
        DataDesigner = None


def load_seed_taxonomy(seed_path: Path) -> Dict[str, Any]:
    """Load categories, brands, and attribute seeds from JSON file."""
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_exact_offsets(product_name: str, raw_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and compute exact character start and end offsets in product_name."""
    valid_entities = []
    used_spans = []

    for ent in raw_entities:
        text = str(ent.get("text", "")).strip()
        label = str(ent.get("label", "")).strip().upper()
        if not text or not label:
            continue

        idx = product_name.find(text)
        if idx != -1:
            start_pos = idx
            end_pos = idx + len(text)
            overlap = False
            for u_start, u_end in used_spans:
                if max(start_pos, u_start) < min(end_pos, u_end):
                    overlap = True
                    break
            
            if not overlap:
                valid_entities.append({
                    "text": text,
                    "label": label,
                    "start": start_pos,
                    "end": end_pos,
                })
                used_spans.append((start_pos, end_pos))

    valid_entities.sort(key=lambda x: x["start"])
    return valid_entities


def create_nemo_datadesigner_config(
    model_name: str = "deepseek-ai/DeepSeek-V4-Flash:fireworks-ai",
    max_parallel: int = 25,
    no_reasoning: bool = False
):
    """Build NeMo Data Designer configuration for Hugging Face Inference Provider."""
    if DataDesigner is None:
        raise ImportError("data-designer package is not installed in environment.")

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token or hf_token == "hf_your_token_here":
        raise ValueError("HF_TOKEN is not set or contains placeholder in .env file.")

    # 1. Define Hugging Face Inference Provider (OpenAI-compatible router)
    provider_kwargs = {
        "name": "huggingface",
        "endpoint": "https://router.huggingface.co/v1",
        "provider_type": "openai",
        "api_key": hf_token,
    }
    if no_reasoning:
        provider_kwargs["extra_body"] = {"reasoning_effort": "none"}

    hf_provider = ModelProvider(**provider_kwargs)

    # 2. Define Model Config with high concurrency & extra_body for reasoning effort
    inference_params: Dict[str, Any] = {"max_parallel_requests": max_parallel}
    if no_reasoning:
        inference_params["extra_body"] = {"reasoning_effort": "none"}

    hf_model = ModelConfig(
        alias="deepseek-v4-flash",
        model=model_name,
        provider="huggingface",
        inference_parameters=inference_params,
    )

    designer = DataDesigner(model_providers=[hf_provider])
    builder = DataDesignerConfigBuilder(model_configs=[hf_model])

    # 3. Add Domain Sampler
    domains = [
        "Ayakkabı", "Çanta", "Giyim", "Aksesuar", "Elektronik",
        "Ev & Mutfak", "Mobilya & Dekorasyon", "Kozmetik", "Kişisel Bakım", "Spor & Outdoor"
    ]
    builder.add_column(
        SamplerColumnConfig(
            name="domain",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(values=domains),
        )
    )

    # 4. Add LLM generation column for product titles + NER tags
    prompt_template = """Sen uzman bir Türk e-ticaret veri mühendisisin.
Görevin, {{ domain }} kategorisinde Trendyol / Hepsiburada tarzında %100 doğal, mantıklı ve gerçekçi bir Türkçe e-ticaret ürün adı ve bu ad içindeki NER (Named Entity Recognition) bileşenlerini çıkarmaktır.

Etiket Çeşitleri:
- BRAND: Marka
- CATEGORY: Ürün türü / Kategorisi
- MODEL: Ürün modeli veya serisi
- COLOR: Renk
- SIZE_VARIANT: Beden / Boyut / Kapasite / Hacim
- GENDER_TARGET: Hedef kitle (Erkek, Kadın, Çocuk vb.)
- MATERIAL: Malzeme / Kumaş
- SPECIFICATION: Nitelik / Teknik özellik / Stil

ÖNEMLİ: Ürün adı tamamen gerçekçi olmalıdır (Örnek: "Nike Air Max 270 Siyah Erkek Spor Ayakkabı 42 Numara"). Saçma veya uyumsuz kombinasyonlar yapma.

Lütfen SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir kelime veya açıklama ekleme:
{
  "product_name": "Nike Air Max 270 Siyah Erkek Spor Ayakkabı 42 Numara",
  "entities": [
    {"text": "Nike", "label": "BRAND"},
    {"text": "Air Max 270", "label": "MODEL"},
    {"text": "Siyah", "label": "COLOR"},
    {"text": "Erkek", "label": "GENDER_TARGET"},
    {"text": "Spor Ayakkabı", "label": "CATEGORY"},
    {"text": "42 Numara", "label": "SIZE_VARIANT"}
  ]
}"""

    builder.add_column(
        LLMTextColumnConfig(
            name="raw_response",
            model_alias="deepseek-v4-flash",
            prompt=prompt_template,
        )
    )

    return designer, builder


def generate_fallback_records(num_records: int, seeds: Dict[str, Any], start_idx: int = 1) -> List[Dict[str, Any]]:
    """Generate deterministic seed-based synthetic records for offline testing."""
    domains = seeds.get("domains", [])
    records = []

    for i in range(num_records):
        dom = random.choice(domains)
        brand = random.choice(dom["brands"])
        category = random.choice(dom["categories"])
        color = random.choice(dom["colors"])
        size = random.choice(dom["sizes"])
        gender = random.choice(dom.get("target_audiences", ["Genel"]))

        title_parts = [brand]
        raw_ents = [{"text": brand, "label": "BRAND"}]

        if random.random() > 0.3 and gender != "Genel":
            title_parts.append(gender)
            raw_ents.append({"text": gender, "label": "GENDER_TARGET"})

        title_parts.append(color)
        raw_ents.append({"text": color, "label": "COLOR"})

        title_parts.append(category)
        raw_ents.append({"text": category, "label": "CATEGORY"})

        title_parts.append(size)
        raw_ents.append({"text": size, "label": "SIZE_VARIANT"})

        product_name = " ".join(title_parts)
        entities = calculate_exact_offsets(product_name, raw_ents)

        records.append({
            "id": f"ecom_ner_{start_idx + i:05d}",
            "product_name": product_name,
            "category_domain": dom["domain_name"],
            "entities": entities,
        })

    return records


def main():
    parser = argparse.ArgumentParser(description="NeMo Data Designer Synthetic E-Commerce NER Generator")
    parser.add_argument("--count", type=int, default=1000, help="Additional target records to generate (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size per LLM generation call (default: 50)")
    parser.add_argument("--max-parallel", type=int, default=25, help="Max parallel requests to HF Provider (default: 25)")
    parser.add_argument("--no-reasoning", action="store_true", help="Disable reasoning tokens (extra_body={'reasoning_effort': 'none'})")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing dataset file instead of appending")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retries per batch on API failure/timeout (default: 5)")
    parser.add_argument("--retry-delay", type=float, default=3.0, help="Base retry delay in seconds for exponential backoff (default: 3.0)")
    parser.add_argument("--preview", action="store_true", help="Run quick 5-record preview generation")
    parser.add_argument("--offline", action="store_true", help="Force offline seed-based generator without HF LLM API")
    parser.add_argument("--output", type=str, default=str(Path(__file__).parent / "data" / "ecommerce_ner_dataset.jsonl"), help="Output .jsonl path")
    parser.add_argument("--rate-limit-delay", type=float, default=0.1, help="Delay in seconds between LLM batches")
    args = parser.parse_args()

    additional_count = 5 if args.preview else args.count
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seed_file = Path(__file__).parent / "sample_seeds.json"
    seeds = load_seed_taxonomy(seed_file) if seed_file.exists() else {"domains": []}

    existing_records = []
    if output_path.exists() and not args.overwrite and not args.preview:
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        existing_records.append(json.loads(line))
                    except Exception:
                        pass
        print(f"[INFO] Found existing dataset file with {len(existing_records)} records. Appending new data (use --overwrite to reset).")
    elif args.overwrite and output_path.exists():
        print(f"[INFO] Overwrite flag passed. Existing dataset file at {output_path} will be reset.")

    target_total = len(existing_records) + additional_count
    print(f"[INFO] Initializing E-Commerce NER Generator (Existing={len(existing_records)}, Adding={additional_count}, Target Total={target_total})...")
    print(f"[INFO] Output path: {output_path.resolve()}")

    if args.no_reasoning:
        print("[INFO] Reasoning tokens DISABLED (extra_body={'reasoning_effort': 'none'})")

    if args.offline:
        print("[INFO] Running in OFFLINE mode (using sample taxonomy seeds)...")
        new_records = generate_fallback_records(additional_count, seeds, start_idx=len(existing_records)+1)
        all_records = existing_records + new_records
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[SUCCESS] Generated {len(new_records)} new records. Total records in {output_path}: {len(all_records)}")
        return

    # ONLINE MODE: Must call HF Inference Provider with NeMo Data Designer
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token or hf_token == "hf_your_token_here":
        print("\n[ERROR] HF_TOKEN is missing or contains placeholder 'hf_your_token_here' in .env")
        print("Lütfen .env dosyasındaki HF_TOKEN değerine kendi Hugging Face API anahtarınızı girin.")
        print("Çevrimdışı test etmek isterseniz '--offline' parametresiyle çalıştırabilirsiniz.\n")
        sys.exit(1)

    print(f"[INFO] Connecting to Hugging Face Inference Router (deepseek-ai/DeepSeek-V4-Flash:fireworks-ai, max_parallel={args.max_parallel})...")
    designer, builder = create_nemo_datadesigner_config(
        max_parallel=args.max_parallel,
        no_reasoning=args.no_reasoning
    )

    generated_records = list(existing_records)
    batch_count = 0

    while len(generated_records) < target_total:
        num_to_gen = min(args.batch_size, target_total - len(generated_records))
        batch_count += 1
        print(f"[INFO] Batch {batch_count}: Requesting {num_to_gen} records from LLM via HF Provider...")

        preview = None
        for attempt in range(1, args.max_retries + 1):
            try:
                preview = designer.preview(config_builder=builder, num_records=num_to_gen)
                break
            except Exception as api_err:
                if attempt < args.max_retries:
                    wait_sec = args.retry_delay * (2 ** (attempt - 1))
                    print(f"[WARNING] Batch {batch_count} attempt {attempt}/{args.max_retries} failed ({api_err}).")
                    print(f"[INFO] Retrying batch in {wait_sec:.1f} seconds (exponential backoff)...")
                    time.sleep(wait_sec)
                else:
                    print(f"\n[ERROR] Batch {batch_count} failed after {args.max_retries} retries: {api_err}")
                    print("[INFO] Saving current progress and exiting gracefully.\n")
                    with open(output_path, "w", encoding="utf-8") as f:
                        for rec in generated_records:
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    sys.exit(1)

        df = preview.dataset
        batch_success = 0
        for idx, row in df.iterrows():
            raw_str = row.get("raw_response", "")
            try:
                cleaned_str = raw_str.strip()
                if cleaned_str.startswith("```json"):
                    cleaned_str = cleaned_str[7:]
                if cleaned_str.startswith("```"):
                    cleaned_str = cleaned_str[3:]
                if cleaned_str.endswith("```"):
                    cleaned_str = cleaned_str[:-3]

                data = json.loads(cleaned_str.strip())
                p_name = data.get("product_name", "")
                raw_e = data.get("entities", [])
                exact_entities = calculate_exact_offsets(p_name, raw_e)

                if p_name and exact_entities:
                    generated_records.append({
                        "id": f"ecom_ner_{len(generated_records)+1:05d}",
                        "product_name": p_name,
                        "category_domain": row.get("domain", "Genel"),
                        "entities": exact_entities,
                    })
                    batch_success += 1
            except Exception as parse_err:
                print(f"[DEBUG] JSON parsing error on LLM output: {parse_err}")

        print(f"[INFO] Batch {batch_count} complete: {batch_success}/{num_to_gen} valid records extracted (Total: {len(generated_records)}/{target_total})")

        # Save checkpoint (preserves existing records & appends new ones)
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in generated_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        time.sleep(args.rate_limit_delay)

    print(f"\n[SUCCESS] Successfully generated {len(generated_records)} total records saved to {output_path}")

    if generated_records:
        print("\n--- SAMPLE LLM GENERATED RECORD ---")
        print(json.dumps(generated_records[-1], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
