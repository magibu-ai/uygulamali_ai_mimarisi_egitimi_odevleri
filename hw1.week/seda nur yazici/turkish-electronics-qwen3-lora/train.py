import os
import torch

from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTConfig, SFTTrainer


# ============================================================
# AYARLAR
# ============================================================

MODEL_NAME = "unsloth/Qwen3-1.7B"

DATASET_NAME = (
    "sedayzc/"
    "turkish-electronics-product-comparison-recommendation"
)

HF_ADAPTER_REPO = (
    "sedayzc/"
    "qwen3-1.7b-turkish-electronics-lora-v2"
)

OUTPUT_DIR = "outputs"

MAX_SEQ_LENGTH = 512

LOAD_IN_4BIT = True

DTYPE = None


# ============================================================
# SİSTEM BİLGİLERİ
# ============================================================

print("=" * 70)
print("QWEN3 TURKISH ELECTRONICS LoRA FINE-TUNING")
print("=" * 70)

print("PyTorch:", torch.__version__)
print("CUDA kullanılabilir:", torch.cuda.is_available())

if torch.cuda.is_available():

    print(
        "GPU:",
        torch.cuda.get_device_name(0)
    )

    gpu_memory = (
        torch.cuda.get_device_properties(0)
        .total_memory
        / 1024**3
    )

    print(
        f"GPU VRAM: {gpu_memory:.2f} GB"
    )

else:

    raise RuntimeError(
        "CUDA GPU bulunamadı. "
        "Bu eğitim GPU üzerinde çalıştırılmalıdır."
    )


# ============================================================
# MODEL VE TOKENIZER
# ============================================================

print("\nModel yükleniyor...")

model, tokenizer = (
    FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )
)

print("Model başarıyla yüklendi.")


# ============================================================
# LoRA ADAPTER
# ============================================================

print("\nLoRA adapter hazırlanıyor...")

model = FastLanguageModel.get_peft_model(

    model,

    # 6 GB VRAM için düşük rank
    r=8,

    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],

    lora_alpha=16,

    lora_dropout=0,

    bias="none",

    use_gradient_checkpointing="unsloth",

    random_state=3407,

    use_rslora=False,

    loftq_config=None,
)

print("LoRA adapter hazır.")


# ============================================================
# DATASET
# ============================================================

print("\nDataset Hugging Face üzerinden yükleniyor...")

dataset = load_dataset(
    "json",
    data_files=(
        "hf://datasets/"
        "sedayzc/"
        "turkish-electronics-product-comparison-recommendation/"
        "data/recommendation_chat_dataset_v2.json"
    ),
    split="train",
)

print(
    "Toplam dataset kaydı:",
    len(dataset)
)

print(
    "\nDataset kolonları:",
    dataset.column_names
)

print(
    "\nÖrnek kayıt:"
)

print(
    dataset[0]
)


# ============================================================
# CHAT FORMAT -> TEXT
# ============================================================

def formatting_prompts_func(examples):

    conversations = examples["messages"]

    texts = []

    for conversation in conversations:

        text = tokenizer.apply_chat_template(

            conversation,

            tokenize=False,

            add_generation_prompt=False,
        )

        texts.append(text)

    return {
        "text": texts
    }


print(
    "\nChat dataset text formatına dönüştürülüyor..."
)

dataset = dataset.map(

    formatting_prompts_func,

    batched=True,
)


print(
    "Dataset formatlama tamamlandı."
)

print(
    "\nFormatlanmış örnek:"
)

print(
    dataset[0]["text"][:1000]
)


# ============================================================
# TRAIN / VALIDATION SPLIT
# ============================================================

print(
    "\nTrain / validation split oluşturuluyor..."
)

dataset_split = dataset.train_test_split(

    test_size=0.05,

    seed=3407,
)


train_dataset = (
    dataset_split["train"]
)

validation_dataset = (
    dataset_split["test"]
)


print(
    "Train kayıt:",
    len(train_dataset)
)

print(
    "Validation kayıt:",
    len(validation_dataset)
)


# ============================================================
# TRAINING CONFIG
# ============================================================

training_args = SFTConfig(

    output_dir=OUTPUT_DIR,

    # 6 GB VRAM
    per_device_train_batch_size=1,

    per_device_eval_batch_size=1,

    gradient_accumulation_steps=8,

    # İlk testte 1 epoch
    num_train_epochs=1,

    learning_rate=2e-4,

    warmup_ratio=0.03,

    weight_decay=0.01,

    lr_scheduler_type="linear",

    optim="adamw_8bit",

    logging_steps=10,

    save_strategy="steps",

    save_steps=100,

    save_total_limit=2,

    eval_strategy="steps",

    eval_steps=100,

    fp16=not torch.cuda.is_bf16_supported(),

    bf16=torch.cuda.is_bf16_supported(),

    max_length=MAX_SEQ_LENGTH,

    dataset_text_field="text",

    packing=False,

    report_to="none",

    seed=3407,
)


# ============================================================
# TRAINER
# ============================================================

print(
    "\nSFTTrainer hazırlanıyor..."
)

trainer = SFTTrainer(

    model=model,

    tokenizer=tokenizer,

    train_dataset=train_dataset,

    eval_dataset=validation_dataset,

    args=training_args,
)


# ============================================================
# GPU MEMORY
# ============================================================

gpu_stats = torch.cuda.get_device_properties(0)

start_gpu_memory = (
    round(
        torch.cuda.max_memory_reserved()
        / 1024**3,
        3,
    )
)

max_memory = (
    round(
        gpu_stats.total_memory
        / 1024**3,
        3,
    )
)


print(
    "\nGPU:",
    gpu_stats.name
)

print(
    "Toplam VRAM:",
    max_memory,
    "GB",
)

print(
    "Başlangıçta ayrılmış VRAM:",
    start_gpu_memory,
    "GB",
)


# ============================================================
# TRAINING
# ============================================================

print("\n" + "=" * 70)
print("FINE-TUNING BAŞLIYOR")
print("=" * 70)


trainer_stats = trainer.train()


# ============================================================
# TRAINING SONUÇLARI
# ============================================================

print("\n" + "=" * 70)
print("FINE-TUNING TAMAMLANDI")
print("=" * 70)

print(
    "Training loss:",
    trainer_stats.training_loss
)

print(
    "Training runtime:",
    trainer_stats.metrics.get(
        "train_runtime"
    ),
)


# ============================================================
# LOCAL LoRA SAVE
# ============================================================

LOCAL_ADAPTER_DIR = (
    "outputs/final_lora_adapter"
)


print(
    "\nLoRA adapter lokal olarak kaydediliyor..."
)

model.save_pretrained(
    LOCAL_ADAPTER_DIR
)

tokenizer.save_pretrained(
    LOCAL_ADAPTER_DIR
)


print(
    "Lokal LoRA adapter:",
    LOCAL_ADAPTER_DIR
)


# ============================================================
# HUGGING FACE PUSH
# ============================================================

print("\n" + "=" * 70)
print("HUGGING FACE PUSH")
print("=" * 70)

print(
    "Repo:",
    HF_ADAPTER_REPO
)


model.push_to_hub(
    HF_ADAPTER_REPO,
)

tokenizer.push_to_hub(
    HF_ADAPTER_REPO,
)


print(
    "\nLoRA adapter Hugging Face'e "
    "başarıyla yüklendi."
)


print("\n" + "=" * 70)
print("TÜM İŞLEMLER TAMAMLANDI")
print("=" * 70)

print(
    "\nHugging Face LoRA Adapter:"
)

print(
    "https://huggingface.co/"
    + HF_ADAPTER_REPO
)