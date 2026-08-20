"""Özel rol tokenlerini ekler ve chat template'i tokenizer'a bağlar."""

import argparse
from pathlib import Path

from transformers import AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOKENIZER = "samliumay/turkish_bpe_based_on_cyber_security_texts"
ROLE_TOKENS = ["<|system|>", "<|user|>", "<|assistant|>"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Türkçe BPE tokenizer'ı chat template kullanımı için hazırlar."
    )
    parser.add_argument(
        "--tokenizer",
        default=DEFAULT_TOKENIZER,
        help="Hugging Face depo adı veya yerel tokenizer dizini.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=PROJECT_ROOT / "chat_template.jinja",
        help="Jinja chat template dosyası.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "output" / "chat_tokenizer",
        help="Hazırlanan tokenizer'ın kaydedileceği dizin.",
    )
    return parser.parse_args()


def validate_special_tokens(tokenizer):
    for token in ROLE_TOKENS:
        token_ids = tokenizer.encode(token, add_special_tokens=False)
        if len(token_ids) != 1:
            raise RuntimeError(
                f"{token!r} tek token olarak kodlanmadı: {token_ids}"
            )


def main():
    args = parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    if tokenizer.bos_token is None or tokenizer.eos_token is None:
        raise RuntimeError("Tokenizer bos_token ve eos_token tanımlamalıdır.")

    current_special_tokens = list(
        tokenizer.special_tokens_map.get("additional_special_tokens", [])
    )
    all_special_tokens = list(dict.fromkeys(current_special_tokens + ROLE_TOKENS))
    added_count = tokenizer.add_special_tokens(
        {"additional_special_tokens": all_special_tokens}
    )

    tokenizer.chat_template = args.template.read_text(encoding="utf-8")
    validate_special_tokens(tokenizer)

    messages = [
        {"role": "system", "content": "Her zaman Türkçe cevap ver."},
        {"role": "user", "content": "Zero Trust nedir?"},
    ]
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    token_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=False,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(args.output_dir)

    print(f"Kaynak tokenizer: {args.tokenizer}")
    print(f"Eklenen token sayısı: {added_count}")
    print(f"Yeni sözlük boyutu: {len(tokenizer)}")
    print(f"Kaydedilen dizin: {args.output_dir}")
    print("\nRender edilmiş sohbet:\n")
    print(rendered)
    print(f"Token sayısı: {len(token_ids)}")
    print("Rol token ID'leri:")
    for token in ROLE_TOKENS:
        print(f"  {token}: {tokenizer.convert_tokens_to_ids(token)}")


if __name__ == "__main__":
    main()
