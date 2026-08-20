# 🇹🇷 Turkish Electronics Qwen3 LoRA

Qwen3-1.7B modelinin Türkçe elektronik ürün karşılaştırma ve öneri veri seti üzerinde **LoRA (Low-Rank Adaptation)** yöntemiyle fine-tune edildiği bir LLM projesidir.

Model, Türkçe kullanıcı sorgularına elektronik ürün önerileri ve ürün karşılaştırmaları sunacak şekilde özelleştirilmiştir.

Fine-tuning işlemi **Unsloth** kullanılarak gerçekleştirilmiş ve oluşturulan LoRA adapter Hugging Face Hub üzerinde yayınlanmıştır.

---

## 🎯 Projenin Amacı

Bu projenin amacı genel amaçlı bir dil modeli olan **Qwen3-1.7B** modelini, Türkçe elektronik ürün karşılaştırma ve öneri alanına adapte etmektir.

Modelin aşağıdaki türdeki kullanıcı sorgularına daha domain-specific cevaplar üretmesi hedeflenmiştir:

```text
En iyi fiyat performans Lenovo laptop önerisinde bulun.

30.000 TL bütçeyle hangi laptopu önerirsin?

HP Victus ile Lenovo LOQ modellerini karşılaştırır mısın?

Kullanıcı puanlarına göre iyi bir oyuncu laptopu önerir misin?

Uygun fiyatlı ama yüksek puanlı bir elektronik ürün önerir misin?
```

Fine-tuning sonucunda modelin özellikle ürün önerilerini daha yapılandırılmış biçimde sunması amaçlanmıştır.

---

# 🧠 Model

Projede kullanılan base model:

```text
Qwen3-1.7B
```

Fine-tuning yöntemi:

```text
LoRA (Low-Rank Adaptation)
```

Eğitim framework'ü:

```text
Unsloth
```

Model ağırlıklarının tamamını yeniden eğitmek yerine yalnızca LoRA adapter parametreleri eğitilmiştir.

Bu yaklaşım sayesinde daha düşük GPU belleği kullanılarak fine-tuning gerçekleştirilebilmiştir.

---

# 📊 Dataset

Model, Türkçe elektronik ürün karşılaştırma ve öneri konuşmalarından oluşan özel bir chat dataset üzerinde eğitilmiştir.

Dataset Hugging Face üzerinde yayınlanmıştır:

```text
sedayzc/turkish-electronics-product-comparison-recommendation
```

Dataset'in V2 sürümü toplam **6.886 chat örneği** içermektedir.

| Veri Türü | Kayıt Sayısı |
|---|---:|
| Product Comparison | 4.851 |
| Product Recommendation | 2.035 |
| **Toplam** | **6.886** |

Dataset chat formatında hazırlanmıştır.

Örnek:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Fiyat performans açısından hangi Laptop modelini önerirsin?"
    },
    {
      "role": "assistant",
      "content": "LENOVO NB V15 82YU0123TX RYZEN 5 7520U 16GB 512SSD O/B 15.6 DOS öne çıkıyor. Ürün fiyat, kullanıcı puanı, değerlendirme sayısı ve mevcut teknik özellikler birlikte dikkate alınarak seçilmiştir."
    }
  ]
}
```

Dataset içerisinde modelin öğrenmesi hedeflenen temel görevler:

- Elektronik ürün önerisi
- Fiyat-performans odaklı ürün önerisi
- Bütçe bazlı ürün önerisi
- Kullanıcı puanı bazlı ürün önerisi
- Ürün karşılaştırma
- Alternatif ürün sunma
- Yapılandırılmış ürün cevabı üretme

---

# ⚙️ Fine-Tuning

Fine-tuning işlemi **Unsloth** ve **LoRA** kullanılarak gerçekleştirilmiştir.

Temel eğitim konfigürasyonu:

| Parametre | Değer |
|---|---|
| Base Model | Qwen3-1.7B |
| Fine-Tuning | LoRA |
| LoRA Rank | 8 |
| LoRA Alpha | 16 |
| Quantization | 4-bit |
| Max Sequence Length | 1024 |
| Epoch | 1 |
| Batch Size | 1 |
| Gradient Accumulation | 8 |
| Learning Rate | 2e-4 |
| Optimizer | AdamW 8-bit |

LoRA aşağıdaki model katmanlarına uygulanmıştır:

```text
q_proj
k_proj
v_proj
o_proj
gate_proj
up_proj
down_proj
```

Gradient checkpointing için Unsloth optimizasyonu kullanılmıştır.

---

# 🖥️ Eğitim Donanımı

Fine-tuning işlemi lokal bir laptop GPU üzerinde gerçekleştirilmiştir.

```text
GPU: NVIDIA GeForce RTX 4050 Laptop GPU
VRAM: 6 GB
CUDA: Enabled
Quantization: 4-bit
```

Unsloth ve 4-bit quantization sayesinde Qwen3-1.7B modeli 6 GB VRAM'e sahip GPU üzerinde LoRA ile fine-tune edilebilmiştir.

---

# 📈 Eğitim Sonuçları

V2 dataset ile gerçekleştirilen eğitim sonucunda:

```text
Training Examples : ~6.5K
Training Steps    : 818
Epoch             : 1
Training Runtime  : ~51 dakika
Training Loss     : 0.4207
```

Eğitim başarıyla tamamlandıktan sonra LoRA adapter hem lokal olarak kaydedilmiş hem de Hugging Face Hub'a yüklenmiştir.

Hugging Face LoRA Adapter:

```text
sedayzc/qwen3-1.7b-turkish-electronics-lora-v2
```

---

# 🚀 Kurulum

Repository'yi klonlayın:

```bash
git clone https://github.com/ssedayzc/turkish-electronics-qwen3-lora.git
cd turkish-electronics-qwen3-lora
```

Gerekli Python paketlerini yükleyin:

```bash
pip install -r requirements.txt
```

Temel bağımlılıklar:

```text
unsloth
transformers
datasets
trl
peft
accelerate
bitsandbytes
huggingface-hub
```

CUDA destekli PyTorch kurulumunun sisteminizde ayrıca doğru şekilde yapılandırılmış olması gerekir.

GPU kontrolü için:

```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'GPU Yok')"
```

---

# 🏋️ Modeli Eğitme

Fine-tuning işlemini başlatmak için:

```bash
python train.py
```

Eğitim pipeline'ı temel olarak şu adımları gerçekleştirir:

```text
Hugging Face Dataset
        ↓
Chat Template Formatting
        ↓
Train / Validation Split
        ↓
Qwen3-1.7B 4-bit Loading
        ↓
LoRA Adapter Injection
        ↓
Supervised Fine-Tuning
        ↓
Local LoRA Adapter
        ↓
Hugging Face Hub
```

Eğitim tamamlandıktan sonra adapter lokal olarak aşağıdaki dizine kaydedilir:

```text
outputs/final_lora_adapter/
```

---

# 💬 Inference

Fine-tuned LoRA modeliyle inference yapmak için:

```bash
python inference.py
```

Inference sırasında model Hugging Face üzerindeki LoRA adapter üzerinden yüklenebilir:

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="sedayzc/qwen3-1.7b-turkish-electronics-lora-v2",
    max_seq_length=1024,
    dtype=None,
    load_in_4bit=True,
)

FastLanguageModel.for_inference(model)
```

Örnek sorgu:

```text
30.000 TL bütçeyle hangi laptopu önerirsin?
```

Model, fine-tuning sırasında öğrendiği cevap yapısına göre ürün önerisi oluşturur.

---

# 📈 Base Model vs Fine-Tuned Model

Fine-tuning etkisini incelemek amacıyla:

```text
Qwen3-1.7B Base
```

ve

```text
Qwen3-1.7B + Turkish Electronics LoRA
```

aynı benchmark soruları üzerinde karşılaştırılmıştır.

# 📈 Base Model ve Fine-Tuned Model Karşılaştırması

Fine-tuning sürecinin model üzerindeki etkisini incelemek amacıyla aşağıdaki iki model aynı benchmark senaryoları üzerinde karşılaştırılmıştır.

```text
Qwen3-1.7B Base
```

ve

```text
Qwen3-1.7B + Turkish Electronics LoRA
```

Model değerlendirmesi yalnızca genel amaçlı LLM benchmarkları ile sınırlı tutulmamış, ayrıca elektronik ürün önerisi ve karşılaştırma görevleri için bu proje kapsamında geliştirilen domain-specific benchmarklar ile de gerçekleştirilmiştir.

---

# 🌍 Genel Amaçlı LLM Benchmarkları

Fine-tuning sonrasında modelin genel dil ve muhakeme yeteneklerinin korunup korunmadığını incelemek amacıyla MMLU, GSM8K ve Turkish MMLU benchmarkları uygulanmıştır.

| Benchmark | Base | LoRA |
|-----------|------:|------:|
| **MMLU** | 50.60% | **51.40%** |
| **GSM8K** | **50.40%** | 24.00% |
| **Turkish MMLU** | **34.80%** | 32.40% |

## Gözlemler

- Fine-tuning sonrasında modelin genel muhakeme yeteneği korunmuştur. MMLU benchmarkında küçük de olsa iyileşme gözlemlenmiştir.
- Matematik problemi çözmeye yönelik herhangi bir eğitim verilmediği için GSM8K performansında beklenen bir düşüş oluşmuştur.
- Turkish MMLU sonucundaki küçük fark, modelin genel Türkçe bilgi seviyesinin büyük ölçüde korunduğunu göstermektedir.

---

# 🛒 Turkish Electronics Benchmark

Mevcut benchmarklar elektronik ürün önerisi ve karşılaştırma görevlerini doğrudan değerlendirmediği için bu proje kapsamında yeni bir benchmark geliştirilmiştir.

Benchmark iki ana görevden oluşmaktadır.

## Recommendation

- En ucuz ürünü önerme
- En yüksek puanlı ürünü önerme
- En fazla değerlendirmeye sahip ürünü önerme
- Fiyat / performans açısından en uygun ürünü önerme

## Comparison

- Daha ucuz ürünü belirleme
- Daha yüksek puanlı ürünü belirleme
- Daha fazla değerlendirmeye sahip ürünü belirleme
- Daha fazla favoriye sahip ürünü belirleme
- Fiyat / performans açısından daha avantajlı ürünü belirleme

Bu görevler klasik çoktan seçmeli benchmarklardan farklı olarak modelin doğal dilde yazılmış kullanıcı isteğini anlamasını, doğru ürünü seçmesini ve bunu açıklayarak sunmasını gerektirmektedir.

---

# 📊 Electronics Domain Benchmark 

Benchmark'ın üçüncü versiyonunda yalnızca doğru ürünün seçilip seçilmediği değil, modelin cevabının ne kadar tutarlı, doğru ve güvenilir olduğu da değerlendirilmektedir.

Ölçülen metrikler:

- Selection Accuracy
- Robust Accuracy
- Permutation Consistency
- Criterion Mention
- Numeric Factuality
- Hallucination-Free
- Format Compliance
- Valid Prediction
- First Position Selection
- Composite Score

## Recommendation

| Metric | Base | LoRA |
|--------|------:|------:|
| Selection Accuracy | 26.00 | **28.25** |
| Robust Accuracy | 10.50 | **12.50** |
| Numeric Factuality | 83.96 | **95.10** |
| Valid Prediction | 84.00 | **100.00** |

## Comparison

| Metric | Base | LoRA |
|--------|------:|------:|
| Selection Accuracy | 49.00 | **51.25** |
| Robust Accuracy | 40.50 | **43.00** |
| Permutation Consistency | 77.50 | **83.50** |
| Valid Prediction | 80.75 | **100.00** |

---

# 📊 Electronics Benchmark Rescore

V3.1 sürümünde mevcut model cevapları tekrar inference yapılmadan yeniden değerlendirilmiştir.

Bu sürümde özellikle sayısal ve teknik ifadeler daha ayrıntılı şekilde analiz edilmektedir.

Eklenen yeni metrikler:

- Numeric Claim Coverage
- Corrected Numeric Quality
- Technical Claim Coverage
- Technical Claim Factuality
- Corrected Hallucination-Free
- Corrected Composite Score

## Recommendation

| Metric | Base | LoRA |
|--------|------:|------:|
| Technical Factuality | 72.33 | **78.40** |

## Comparison

| Metric | Base | LoRA |
|--------|------:|------:|
| Technical Claim Coverage | 18.25 | **79.50** |
| Technical Factuality | 67.12 | **84.43** |

---

# 🔍 Fine-Tuning Sonuçlarının Değerlendirilmesi

Benchmark sonuçları incelendiğinde LoRA fine-tuning işleminin modelin genel bilgi seviyesinden çok elektronik ürün önerisi alanındaki davranış biçimini değiştirdiği görülmektedir.

Base model daha genel amaçlı cevaplar üretirken, fine-tuned model elektronik ürün önerisi görevlerinde:

- kullanıcı isteğini daha tutarlı yorumlayabilmekte,
- geçerli ürün seçme oranını artırmakta,
- farklı prompt sıralamalarına karşı daha kararlı davranabilmekte,
- teknik özelliklerden daha fazla bahsedebilmekte,
- ürün karşılaştırmalarını daha yapılandırılmış şekilde sunabilmektedir.

Bununla birlikte benchmarklar modelin hâlen geliştirilmesi gereken bazı yönlerini de ortaya koymaktadır.

Örneğin;

- doğru kategoride yanlış ürünü seçebilmesi,
- öneri ve karşılaştırma görevlerini zaman zaman karıştırabilmesi,
- birden fazla kısıtı (bütçe, kategori vb.) aynı anda her zaman doğru uygulayamaması,
- bazı teknik ifadeleri eksik veya yetersiz açıklaması

gibi durumlar gözlemlenmiştir.

Sonuç olarak mevcut LoRA modeli elektronik ürün önerisi alanına başarılı şekilde adapte olmuş olsa da ürün seviyesinde muhakeme ve teknik doğruluk açısından geliştirmeye açık yönler bulunmaktadır.

---

# 🧪 Benchmark Metodolojisi

Bu projede geliştirilen benchmark yalnızca doğru cevabı kontrol etmek yerine model davranışını çok boyutlu olarak değerlendirmektedir.

Ölçülen davranışlar şunlardır:

- doğru ürün seçimi,
- doğru ürün karşılaştırması,
- bütçe kısıtına uyum,
- kategori uyumu,
- prompt sıralamasına karşı tutarlılık,
- sayısal bilgilerin doğruluğu,
- teknik açıklamaların doğruluğu,
- halüsinasyon oranı,
- cevap formatı,
- doğal dilde açıklama kalitesi.

Benchmark tamamen otomatik çalışabilmekte ve aynı veri seti üzerinde farklı modellerin doğrudan karşılaştırılmasına olanak sağlamaktadır.
---

# 📂 Proje Yapısı

```text
turkish-electronics-qwen3-lora/
│
├── train.py
├── inference.py
├── compare_base_vs_lora.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── assets/
│   └── base_vs_lora_comparison.png
│
├── evaluation_results.json
│
└── outputs/
    └── final_lora_adapter/
```

`outputs/` klasörü GitHub repository'sine dahil edilmiyorsa LoRA adapter doğrudan Hugging Face Hub üzerinden yüklenebilir.

---

# 🔗 Hugging Face

## Fine-Tuned LoRA Adapter

```text
sedayzc/qwen3-1.7b-turkish-electronics-lora-v2
```

## Training Dataset

```text
sedayzc/turkish-electronics-product-comparison-recommendation
```

---

