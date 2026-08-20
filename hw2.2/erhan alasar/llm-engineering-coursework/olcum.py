"""Qwen2.5 base ve LangUsta LoRA modellerini Türkçe MMLU ile karşılaştırır."""

from __future__ import annotations

import argparse
import gc
import time
from pathlib import Path

import pandas as pd
import torch
from peft import PeftModel
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL_PATH = Path("models/base")
ADAPTER_PATH = Path("models/adapter")
RESULTS_DIR = Path("results")
MMLU_URL = (
    "hf://datasets/alibayram/yapay_zeka_turkce_mmlu_model_cevaplari/"
    "data/train-00000-of-00001.parquet"
)

MODEL_CONFIGS = (
    {
        "name": "Qwen2.5-0.5B-Instruct",
        "column": "qwen2.5-0.5b-base_cevap",
        "adapter": False,
    },
    {
        "name": "LangUsta-KPSS-LoRA",
        "column": "langusta-kpss-lora_cevap",
        "adapter": True,
    },
)

_semantic_model: SentenceTransformer | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Hızlı kontrol için ilk N soruyu çalıştırır; verilmezse 6.200 sorunun tamamı kullanılır.",
    )
    return parser.parse_args()


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_semantic_model(device: str) -> SentenceTransformer:
    global _semantic_model
    if _semantic_model is None:
        _semantic_model = SentenceTransformer(
            "paraphrase-multilingual-mpnet-base-v2",
            device=device,
        )
    return _semantic_model


def cevap_dogru_mu(
    dogru_cevap_index: int,
    verilen_cevap: str,
    secenekler: list[str],
    device: str,
) -> bool:
    harfler = ["A", "B", "C", "D", "E"]
    dogru_harf = harfler[int(dogru_cevap_index)]
    verilen_cevap = verilen_cevap.upper().strip()

    if dogru_harf == verilen_cevap:
        return True
    if len(verilen_cevap) > 1 and verilen_cevap[1] in [" ", ":", ")", "=", "-", "."]:
        return dogru_harf == verilen_cevap[0]

    semantic_model = get_semantic_model(device)
    encoded_cevap = semantic_model.encode([verilen_cevap])
    encoded_secenekler = semantic_model.encode(secenekler)
    benzerlikler = semantic_model.similarity(
        encoded_cevap,
        encoded_secenekler,
    ).tolist()[0]
    return benzerlikler.index(max(benzerlikler)) == int(dogru_cevap_index)


def ilerleme_cubugu(guncel: int, toplam: int, cubuk_uzunlugu: int = 30) -> str:
    ilerleme = guncel / toplam
    blok = int(cubuk_uzunlugu * ilerleme)
    cubuk = "#" * blok + "-" * (cubuk_uzunlugu - blok)
    return f"[{cubuk}] %{ilerleme * 100:6.2f}"


def modeli_yukle(
    tokenizer: AutoTokenizer,
    adapter_kullan: bool,
    device: str,
) -> AutoModelForCausalLM | PeftModel:
    dtype = torch.float16 if device in {"cuda", "mps"} else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )

    if adapter_kullan:
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)

    model.to(device)
    model.eval()

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    return model


def cevap_uret(
    model: AutoModelForCausalLM | PeftModel,
    tokenizer: AutoTokenizer,
    prompt: str,
    device: str,
) -> str:
    sohbet = [{"role": "user", "content": prompt}]
    bicimlendirilmis_prompt = tokenizer.apply_chat_template(
        sohbet,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(bicimlendirilmis_prompt, return_tensors="pt").to(device)

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=42,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    yeni_tokenlar = output[0, inputs["input_ids"].shape[1] :]
    return tokenizer.decode(yeni_tokenlar, skip_special_tokens=True).strip()


def prompt_olustur(soru: str, secenekler: list[str]) -> str:
    harfler = ["A", "B", "C", "D", "E"]
    secenek_metni = "\n".join(
        f"{harfler[index]}: {secenek}"
        for index, secenek in enumerate(secenekler)
    )
    return (
        "Sana soru ve seçenekleri veriyorum. Sadece doğru seçeneğin harfini yaz. "
        "Örneğin 'A' veya 'B' gibi. Herhangi bir açıklama yapma!\n"
        f"Soru: {soru}\n{secenek_metni}"
    )


def modeli_test_et(
    model_config: dict[str, object],
    mmlu_veri: pd.DataFrame,
    tokenizer: AutoTokenizer,
    device: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    model_adi = str(model_config["name"])
    cevap_sutunu = str(model_config["column"])
    model = modeli_yukle(
        tokenizer,
        adapter_kullan=bool(model_config["adapter"]),
        device=device,
    )

    baslama_zamani = time.time()
    dogru_cevap_sayisi = 0
    bolum_sayaclari: dict[str, dict[str, int]] = {}

    print(f"\n{model_adi} ölçümü başladı ({len(mmlu_veri):,} soru).")

    for index, row in mmlu_veri.iterrows():
        secenekler = list(row["secenekler"])
        prompt = prompt_olustur(str(row["soru"]), secenekler)
        cevap = cevap_uret(model, tokenizer, prompt, device)
        mmlu_veri.at[index, cevap_sutunu] = cevap

        bolum = str(row["bolum"])
        bolum_sayaclari.setdefault(bolum, {"dogru": 0, "toplam": 0})
        bolum_sayaclari[bolum]["toplam"] += 1

        if cevap_dogru_mu(int(row["cevap"]), cevap, secenekler, device):
            dogru_cevap_sayisi += 1
            bolum_sayaclari[bolum]["dogru"] += 1

        tamamlanan = index + 1
        if tamamlanan == 1 or tamamlanan % 10 == 0 or tamamlanan == len(mmlu_veri):
            cubuk = ilerleme_cubugu(tamamlanan, len(mmlu_veri))
            basari = dogru_cevap_sayisi / tamamlanan * 100
            print(
                f"\r{cubuk} {tamamlanan:,}/{len(mmlu_veri):,} "
                f"doğru={dogru_cevap_sayisi:,} başarı=%{basari:.2f}",
                end="",
                flush=True,
            )

    toplam_sure = round(time.time() - baslama_zamani, 3)
    basari = round(dogru_cevap_sayisi / len(mmlu_veri) * 100, 2)
    print()

    genel_sonuc = {
        "model": model_adi,
        "toplam_soru": len(mmlu_veri),
        "dogru_cevap": dogru_cevap_sayisi,
        "basari_yuzdesi": basari,
        "toplam_sure_saniye": toplam_sure,
    }

    bolum_sonuclari = [
        {
            "model": model_adi,
            "bolum": bolum,
            "toplam_soru": sayac["toplam"],
            "dogru_cevap": sayac["dogru"],
            "basari_yuzdesi": round(sayac["dogru"] / sayac["toplam"] * 100, 2),
        }
        for bolum, sayac in sorted(bolum_sayaclari.items())
    ]

    del model
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    elif device == "mps":
        torch.mps.empty_cache()

    return genel_sonuc, bolum_sonuclari


def sonuclari_kaydet(
    genel_sonuclar: list[dict[str, object]],
    bolum_sonuclari: list[dict[str, object]],
    mmlu_veri: pd.DataFrame,
) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    mmlu_veri.to_parquet(
        RESULTS_DIR / "benchmark_answers.parquet",
        index=False,
    )
    markdown_sonuclarini_yaz(genel_sonuclar, bolum_sonuclari)


def markdown_sonuclarini_yaz(
    genel_sonuclar: list[dict[str, object]],
    bolum_sonuclari: list[dict[str, object]],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    satirlar = [
        "# TR-MMLU Benchmark Results",
        "",
        "Qwen2.5-0.5B-Instruct temel modeli ile LangUsta KPSS LoRA adaptörünün",
        "aynı Türkçe MMLU soruları üzerindeki karşılaştırmalı sonuçlarıdır.",
        "",
        "## Evaluation Setup",
        "",
        f"- Benchmark: [TR-MMLU](https://github.com/malibayram/llm-tr-benchmarks)",
        f"- Evaluated questions: {genel_sonuclar[0]['toplam_soru']:,}",
        "- Decoding: deterministic greedy generation",
        "- Maximum new tokens: 42",
        "- Answer evaluation: exact option matching with semantic fallback",
        "",
        "## Overall Results",
        "",
        "| Model | Correct | Questions | Accuracy | Duration |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for sonuc in genel_sonuclar:
        satirlar.append(
            f"| {sonuc['model']} | {sonuc['dogru_cevap']:,} | "
            f"{sonuc['toplam_soru']:,} | {sonuc['basari_yuzdesi']:.2f}% | "
            f"{sonuc['toplam_sure_saniye']:.3f} s |"
        )

    satirlar.extend(
        [
            "",
            "## Results by Section",
            "",
            "| Model | Section | Correct | Questions | Accuracy |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )

    for sonuc in bolum_sonuclari:
        satirlar.append(
            f"| {sonuc['model']} | {sonuc['bolum']} | "
            f"{sonuc['dogru_cevap']:,} | {sonuc['toplam_soru']:,} | "
            f"{sonuc['basari_yuzdesi']:.2f}% |"
        )

    satirlar.extend(
        [
            "",
            "## Reproduction",
            "",
            "```bash",
            "uv sync --python 3.12",
            "uv run python olcum.py",
            "```",
            "",
            "> This file is generated automatically by `olcum.py`.",
            "",
        ]
    )

    (RESULTS_DIR / "benchmark-results.md").write_text(
        "\n".join(satirlar),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    device = get_device()
    print(f"Cihaz: {device}")

    mmlu_veri = pd.read_parquet(MMLU_URL)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit en az 1 olmalıdır.")
        mmlu_veri = mmlu_veri.head(args.limit).copy()
    else:
        mmlu_veri = mmlu_veri.copy()
    mmlu_veri.reset_index(drop=True, inplace=True)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH)
    genel_sonuclar: list[dict[str, object]] = []
    bolum_sonuclari: list[dict[str, object]] = []

    for model_config in MODEL_CONFIGS:
        genel_sonuc, model_bolum_sonuclari = modeli_test_et(
            model_config,
            mmlu_veri,
            tokenizer,
            device,
        )
        genel_sonuclar.append(genel_sonuc)
        bolum_sonuclari.extend(model_bolum_sonuclari)
        sonuclari_kaydet(genel_sonuclar, bolum_sonuclari, mmlu_veri)

    print("\nKarşılaştırma:")
    print(pd.DataFrame(genel_sonuclar).to_string(index=False))
    print(f"\nModel kartı sonucu: {(RESULTS_DIR / 'benchmark-results.md').resolve()}")


if __name__ == "__main__":
    main()
