# Gemma-4 LoRA Fine-Tune Rehberi (Unsloth + Colab L4)

Bu veri setini Unsloth'un Gemma-4 notebook'unda eğitmek için üç adım:
**veriyi hazırla → GitHub'a koy → doğru hücreleri çalıştır.**

---

## 1. Hangi dosya, neden

Notebook **ShareGPT `conversations` formatı** bekler (`standardize_data_formats` +
Gemma-4 chat template). Bunun için üretilen dosya:

```
data/train_sharegpt.jsonl
```

`export` komutu bunu otomatik üretir. Yapısı (araç çağıran örnek, **çok-turlu**):

| Tur | Rol | İçerik | Eğitim |
|---|---|---|---|
| 1 | human | kullanıcı sorusu | maskeli |
| 2 | gpt | `<think>…</think>` + `<tool_call>…</tool_call>` | **öğrenilir** |
| 3 | human | `<tool_response>…</tool_response>` | maskeli |
| 4 | gpt | doğal dille son cevap | **öğrenilir** |

Araç gerektirmeyen örneklerde tek `gpt` turu olur: `<think>` + cevap.

Böylece model **iki beceriyi** öğrenir: (a) doğru aracı doğru parametreyle çağırmak,
(b) dönen sonucu kullanıcıya düzgün anlatmak. `train_on_responses_only` sayesinde
kayıp yalnızca `gpt` turlarında hesaplanır; kullanıcı ve tool_response turları maskelidir
— yani model tool sonucunu **uydurmayı değil**, yorumlamayı öğrenir.

Üretim bitince tekrar çalıştır:

```bash
python cli.py export
```

> `--no-thinking` ile `<think>` bloklarını çıkarabilirsin (sadece araç+cevap eğitimi).

---

## 2. Hugging Face Hub'a koyma (önerilen)

Veri setleri için en temiz yol HF Hub — Colab tek satırla, ham URL uğraşı olmadan
yükler. `.env` içine `HF_TOKEN` (write yetkili) ekle, sonra:

```bash
python cli.py push KULLANICI/math-toolcall
```

Bu, `data/train_sharegpt.jsonl`'i yükler ve sana Colab'da kullanacağın satırı yazar:

```python
dataset = load_dataset("KULLANICI/math-toolcall", split = "train")
```

Özel tutmak istersen `--private` ekle. Token'ı `.env` yerine tek seferlik vermek için
`--token hf_xxx`. Gerekli paketler: `pip install datasets huggingface_hub`
(requirements.txt'te var).

> **HF neden GitHub'dan iyi:** `conversations` kolonu şemasıyla saklanır, sürümlenir,
> `load_dataset` doğrudan tanır, dosya boyutu derdi yok.

### Alternatif — GitHub (ham URL ile)

Veri küçük (~1-2 MB), git-lfs gerekmez:

```bash
git init
git add .gitignore README.md FINETUNE.md *.py requirements.txt .env.example
git add data/train_sharegpt.jsonl data/dataset.json data/dataset_chat.json
git commit -m "Matematik tool-call veri seti"
gh repo create math-toolcall-dataset --public --source=. --push
```

Colab'da: `load_dataset("json", data_files="https://raw.githubusercontent.com/KULLANICI/math-toolcall-dataset/main/data/train_sharegpt.jsonl", split="train")`

Her iki yolda da `.env` ve anahtarlar `.gitignore` ile korunur.

---

## 3. Colab'da hangi hücreler

Notebook'u açıp **Runtime → Run all** yerine, aşağıdaki gibi seçerek çalıştır.
Çoğu hücre olduğu gibi kalır; sadece **3 hücreyi değiştir**, multimodal demo
hücrelerini **atla**.

### Çalıştır (sırayla)

1. **Installation** hücreleri (pip install...) — aynen.
2. **`FastModel.from_pretrained(...)`** — aynen (veya `max_seq_length` → `2048`, altta).
3. **`get_peft_model(...)`** — aynen (LoRA adaptörleri).
4. **`get_chat_template(tokenizer, "gemma-4")`** — aynen.
5. **Veri yükleme** — ⬇️ DEĞİŞTİR.
6. **`standardize_data_formats`** — aynen.
7. **`formatting_prompts_func` + `dataset.map`** — aynen.
8. **`SFTTrainer(...)`** — ⬇️ DEĞİŞTİR (eğitim süresi).
9. **`train_on_responses_only`** — aynen (bizim formatı maskeleyen kritik hücre).
10. Bellek istatistiği + **`trainer.train()`** — aynen.
11. **Kaydetme** hücrelerinden ihtiyacın olanı (altta).

### Atla (multimodal demo — gereksiz, sadece zaman/indirme yükü)

- `do_gemma_4_inference` tanımı ve altındaki tüm **görsel / ses / poem** demoları
  (sloth resmi, NASA mp3, "combine all 3 modalities").
- Eğitim sonrası **Inference** demoları isteğe bağlı (modeli denemek için çalıştırabilirsin).

### Değişiklik 5 — Veri yükleme hücresi

Şunu:

```python
from datasets import load_dataset
dataset = load_dataset("mlabonne/FineTome-100k", split = "train[:3000]")
```

bununla değiştir (HF Hub — önerilen):

```python
from datasets import load_dataset
dataset = load_dataset("KULLANICI/math-toolcall", split = "train")
```

> GitHub kullandıysan onun yerine:
> `dataset = load_dataset("json", data_files="https://raw.githubusercontent.com/KULLANICI/math-toolcall-dataset/main/data/train_sharegpt.jsonl", split="train")`

`standardize_data_formats` ve `formatting_prompts_func` hücreleri hiç değişmez —
bizim `conversations` kolonu doğru şemada.

### Değişiklik 2 (opsiyonel ama önerilir) — max_seq_length

Model yükleme hücresinde:

```python
max_seq_length = 2048,   # 1024 idi; kayitlarimizin en uzunu ~900 token, 2048 guvenli pay
```

### Değişiklik 8 — Eğitim süresi

Notebook demo için `max_steps = 60`. ~300-400 örneklik gerçek bir tur için epoch bazlı yap:

```python
args = SFTConfig(
    dataset_text_field = "text",
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 4,
    warmup_steps = 5,
    num_train_epochs = 3,      # max_steps yerine
    # max_steps = 60,          # <-- YORUM SATIRI YAP / SIL
    learning_rate = 2e-4,      # az veri: overfit olursa 1e-4'e dusur
    logging_steps = 1,
    optim = "adamw_8bit",
    weight_decay = 0.001,
    lr_scheduler_type = "linear",
    seed = 3407,
    report_to = "none",
),
```

> Küçük veri setinde 2-3 epoch iyi bir başlangıç. Eğitim kaybı çok hızlı 0'a
> inip cevaplar ezberlenmiş görünüyorsa epoch'u 2'ye, learning_rate'i 1e-4'e çek.
> LoRA `r`: notebook'ta 8; daha fazla kapasite için 16 (alpha da 16) deneyebilirsin,
> ama az veride 8 daha güvenli.

### Kaydetme (en alttaki `if False:` bloklarından birini `if True:` yap)

| Amaç | Hücre |
|---|---|
| Sadece LoRA adaptörü (küçük) | `model.save_pretrained("gemma_4_lora")` |
| Ollama / llama.cpp (yerel çalıştırma) | `save_pretrained_gguf(..., "Q8_0")` |
| vLLM / 16bit birleşik | `save_pretrained_merged(...)` |
| HF Hub'a yükle | `push_to_hub_*` (token gerekir) |

Colab oturumu kapanınca dosyalar silinir — **indir ya da HF/Drive'a yükle.**

---

## Özet akış

```bash
# yerel
python cli.py run --n 200 --fresh          # veri uret (istedigin sayiya ulasana kadar)
python cli.py export                        # train_sharegpt.jsonl olusur
python cli.py push KULLANICI/math-toolcall  # HF Hub'a yukle (.env icinde HF_TOKEN)

# Colab: veri yukleme hucresini load_dataset("KULLANICI/math-toolcall", split="train")
#        yap -> secili hucreleri calistir -> modeli kaydet/indir
```
