import torch

from unsloth import FastLanguageModel


# ============================================================
# AYARLAR
# ============================================================

LORA_ADAPTER = (
    "sedayzc/"
    "qwen3-1.7b-turkish-electronics-lora-v2"
)

MAX_SEQ_LENGTH = 512
LOAD_IN_4BIT = True


# ============================================================
# SİSTEM BİLGİSİ
# ============================================================

print("=" * 70)
print("QWEN3 TURKISH ELECTRONICS LoRA INFERENCE")
print("=" * 70)

print(
    "CUDA kullanılabilir:",
    torch.cuda.is_available(),
)

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA GPU bulunamadı. "
        "Inference GPU üzerinde çalıştırılmalıdır."
    )

print(
    "GPU:",
    torch.cuda.get_device_name(0),
)


# ============================================================
# MODEL + TOKENIZER
# ============================================================

print(
    "\nFine-tuned LoRA model yükleniyor..."
)

model, tokenizer = (
    FastLanguageModel.from_pretrained(
        model_name=LORA_ADAPTER,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=LOAD_IN_4BIT,
    )
)


model.generation_config.max_length = None

FastLanguageModel.for_inference(
    model
)

print(
    "Model inference için hazır."
)


# ============================================================
# CEVAP ÜRETME FONKSİYONU
# ============================================================

def generate_response(
    question,
    max_new_tokens=300,
):
    """
    Kullanıcı sorusuna fine-tuned Qwen3 LoRA modeliyle
    cevap üretir.

    Qwen3 thinking modu kapalıdır.
    """

    messages = [
        {
            "role": "user",
            "content": question,
        }
    ]

    # ========================================================
    # CHAT TEMPLATE
    # ========================================================

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,

        # Qwen3 düşünme modunu kapat
        enable_thinking=False,
    )

    # ========================================================
    # TOKENIZATION
    # ========================================================

    inputs = tokenizer(
        prompt,
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

    # ========================================================
    # GENERATION
    # ========================================================

    with torch.inference_mode():

     outputs = model.generate(

        **inputs,

        # Üretilecek maksimum yeni token sayısı
        max_new_tokens=max_new_tokens,

        # Deterministik üretim
        # Aynı soruya mümkün olduğunca aynı cevabı verir
        do_sample=False,

        # Tekrarları azalt
        repetition_penalty=1.05,

        use_cache=True,

        # EOS geldiğinde üretimi durdur
        eos_token_id=tokenizer.eos_token_id,

        pad_token_id=tokenizer.pad_token_id,
    )


    # ========================================================
    # SADECE MODELİN YENİ ÜRETTİĞİ TOKENLARI AL
    # ========================================================

    generated_tokens = (
        outputs[
            0,
            input_length:
        ]
    )

    response = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )

    # Olası boşlukları temizle
    response = response.strip()

    return response


# ============================================================
# TEST SORULARI
# ============================================================

test_questions = [

    "En iyi fiyat performans Lenovo laptop önerisinde bulun.",

    "30.000 TL bütçeyle hangi laptopu önerirsin?",

    (
        "HP Victus ile Lenovo LOQ modellerini "
        "karşılaştırır mısın?"
    ),

    (
        "Kullanıcı puanlarına göre iyi bir "
        "oyuncu laptopu önerir misin?"
    ),

    (
        "Uygun fiyatlı ama yüksek puanlı "
        "bir elektronik ürün önerir misin?"
    ),
]


# ============================================================
# OTOMATİK TEST
# ============================================================

for index, question in enumerate(
    test_questions,
    start=1,
):

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"SORU {index}"
    )

    print(
        "=" * 70
    )

    print(
        question
    )

    try:

        answer = generate_response(
            question
        )

        print(
            "\nCEVAP:"
        )

        print(
            answer
        )

    except Exception as error:

        print(
            "\nHATA:"
        )

        print(
            error
        )


# ============================================================
# INTERACTIVE MODE
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "INTERACTIVE MODE"
)

print(
    "=" * 70
)

print(
    "Çıkmak için 'exit' yaz."
)


while True:

    user_input = input(
        "\nSoru: "
    ).strip()

    if user_input.lower() in {
        "exit",
        "quit",
        "q",
    }:

        print(
            "\nProgram kapatılıyor."
        )

        break

    if not user_input:

        continue

    try:

        answer = generate_response(
            user_input
        )

        print(
            "\nCevap:"
        )

        print(
            answer
        )

    except Exception as error:

        print(
            "\nInference sırasında hata oluştu:"
        )

        print(
            error
        )