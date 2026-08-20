# math-toolcall-tr

Türkçe **matematik fonksiyon çağırma (tool calling)** veri seti ve Gemma-4 LoRA fine-tune'u.

Uçtan uca: veri üretimi → veri seti → eğitim → model.

| | Bağlantı |
|---|---|
| 📊 **Veri seti** | [huggingface.co/datasets/bilalabic/math-toolcall-tr](https://huggingface.co/datasets/bilalabic/math-toolcall-tr) |
| 🤖 **Model (LoRA)** | [huggingface.co/bilalabic/gemma_4_math-toolcall-tr_lora](https://huggingface.co/bilalabic/gemma_4_math-toolcall-tr_lora) |
| 📓 **Eğitim notebook'u** | [notebooks/gemma4_e4b_math_toolcall_lora.ipynb](notebooks/gemma4_e4b_math_toolcall_lora.ipynb) |
| 📈 **Benchmark notebook'u** | [notebooks/benchmark_base_vs_finetune.ipynb](notebooks/benchmark_base_vs_finetune.ipynb) |
| 🛠️ **Veri üretim kodu** | [toolcall-dataset/](toolcall-dataset/) |

### Colab'da aç (tek tık)

| Notebook | |
|---|---|
| Eğitim | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BilalAbic/math-toolcall-tr/blob/main/notebooks/gemma4_e4b_math_toolcall_lora.ipynb) |
| Benchmark | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/BilalAbic/math-toolcall-tr/blob/main/notebooks/benchmark_base_vs_finetune.ipynb) |

Rozete tıklamak yeterli — Colab notebook'u GitHub'dan doğrudan açar. Alternatif olarak
Colab'da **Dosya → Not defteri aç → GitHub** sekmesine `BilalAbic/math-toolcall-tr`
yazabilirsin. Açtıktan sonra **Runtime → Change runtime type → GPU** seçmeyi unutma.

## Ne bu?

Bir dil modelinin **doğru fonksiyonu doğru parametreyle çağırmasını** ve dönen sonucu
**kullanıcıya düzgün anlatmasını** öğreten Türkçe veri seti — tamamen matematik odaklı.

Veri kasıtlı olarak yalnızca "başarılı çağrı" içermez. Örneklerin **%31'inde hiç araç
çağrılmaz**: soru zaten cevaplanabilir ya da zorunlu bir parametre eksiktir ve model
uydurmak yerine netleştirme sorusu sorar.

**2.127 örnek · 13 alt alan · 70 konu · 8 senaryo**

| Senaryo | Ne öğretir |
|---|---|
| `arac_gereksiz` | Araç gerekmiyorsa çağırmamak |
| `tek_cagri` | Tek aracı doğru parametreyle çağırmak |
| `yanlis_arac_tuzagi` | Benzer isimli araçlardan doğrusunu seçmek |
| `paralel_cagri` | Bağımsız hesapları aynı anda yapmak |
| `hata_yonetimi` | Sıfıra bölme / tanımsızlık gibi hataları açıklamak |
| `eksik_parametre` | Uydurmak yerine netleştirme sorusu sormak |
| `cok_adimli_gorev` | Tek istekte 3+ çağrıyla tamamlamak |
| `zincirli_cagri` | İkinci çağrının girdisini ilkinin sonucundan almak |

## Repo yapısı

```
.
├── notebooks/
│   ├── gemma4_e4b_math_toolcall_lora.ipynb   # Unsloth ile LoRA eğitimi (Colab)
│   └── benchmark_base_vs_finetune.ipynb      # base vs fine-tune karşılaştırması
└── toolcall-dataset/                          # veri seti üreteci (CLI)
    ├── cli.py          # komutlar: run / export / push / card / stats
    ├── prompts.py      # tek master prompt — kalite ayarı burada
    ├── topics.py       # 13 alt alan, 70 konu, 8 senaryo
    ├── providers.py    # OpenAI + Gemini için tek istemci
    ├── exporters.py    # ShareGPT / OpenAI / Gemini formatları
    ├── CARD.md         # HF dataset kartı
    ├── MODEL_CARD.md   # HF model kartı
    ├── FINETUNE.md     # eğitim rehberi (hangi hücre, hangi ayar)
    └── data/
        ├── train_sharegpt.jsonl   # eğitim dosyası (Unsloth bunu kullanır)
        ├── dataset.json           # tam provenance (hangi model, hangi konu)
        └── dataset_chat.json      # sohbet formatı
```

## Hızlı başlangıç

### Veri üretmek

```bash
cd toolcall-dataset
pip install -r requirements.txt
cp .env.example .env          # OPENAI_API_KEY ve HF_TOKEN doldur

python cli.py run --n 200 --fresh   # üret (soru → cevap, dalgalar hâlinde)
python cli.py export                # train_sharegpt.jsonl oluştur
python cli.py stats                 # dağılım raporu
```

### Modeli kullanmak

```python
from unsloth import FastModel

model, tokenizer = FastModel.from_pretrained(
    model_name     = "bilalabic/gemma_4_math-toolcall-tr_lora",
    max_seq_length = 2048,
    load_in_4bit   = True,
)
```

Model `<think>` + `<tool_call>` üretir; sen aracı çalıştırıp sonucu `<tool_response>`
olarak geri beslersin. Ayrıntı: [model kartı](https://huggingface.co/bilalabic/gemma_4_math-toolcall-tr_lora).

### Eğitmek

[FINETUNE.md](toolcall-dataset/FINETUNE.md) — hangi hücreyi çalıştıracağın, neyi
atlayacağın ve hangi ayarı değiştireceğin adım adım anlatılır.

### Ölçmek

[benchmark_base_vs_finetune.ipynb](notebooks/benchmark_base_vs_finetune.ipynb) — base
model ile fine-tune'u **üç benchmark'ta** karşılaştırır:

| Benchmark | Ölçtüğü | Beklenti |
|---|---|---|
| Türkçe MMLU | Genel bilgi | Düşmemeli (aşırı uyum kontrolü) |
| Matematik Tool-Call | Araç seçimi, çekimserlik, format | **Yükselmeli** |
| [GSM8K](https://huggingface.co/datasets/openai/gsm8k) | Serbest matematik akıl yürütme | Düşmemeli |

Tool-call testi modelin **hiç görmediği 450 örnek** üzerinde çalışır (eğitim 757'de
kesildi) — yani ezber değil, genelleme ölçülür. GSM8K ise sektör standardı referans
noktası; İngilizce olduğu için kazanç değil, **bozulma olmadığı** ölçülür.

## Nasıl üretildi

İki aşamalı sentetik üretim, `gpt-5.4-mini` ile:

1. **Soru** — (alt alan, konu, senaryo, zorluk) kombinasyonu seçilir; model 2-4 fonksiyon
   şeması + doğal bir kullanıcı mesajı üretir. Şemaların yalnızca 1-2'si gerçekten
   gereklidir, diğerleri inandırıcı çeldiricidir.
2. **Cevap** — aynı model düşünme adımlarını, araç çağrılarını, beklenen sonuçları ve
   son yanıtı üretir.

Üretim birikimlidir ve dalgalar hâlinde diske yazar; yarıda kesilse bile ilerleme korunur.

## Eğitim özeti

| | |
|---|---|
| Temel model | `unsloth/gemma-4-e4b-it-unsloth-bnb-4bit` |
| Yöntem | LoRA (r=8, alpha=8), yalnızca dil katmanları |
| Eğitilebilir parametre | 18,35M / 8,01B (%0,23) |
| Eğitilen örnek | **757** (veri setinin eski sürümü) |
| Epoch / adım | 3 / 285 |
| Batch | 2 × 4 = 8 |
| Öğrenme oranı | 2e-4 |
| Donanım | A100-SXM4-80GB (Colab) |
| Son kayıp | ≈ 0,076 |

> ⚠️ Yayımlanan adaptör **757 örnekle** eğitilmiştir. Veri seti bugün **2.127** örnektir;
> güncel sürümle yeniden eğitim henüz yapılmamıştır.

`train_on_responses_only` kullanılır — kayıp yalnızca model yanıtlarında hesaplanır,
`tool_response` turu maskelidir. Model böylece araç sonucunu uydurmayı değil,
**yorumlamayı** öğrenir.

## Sınırlamalar

Veri seti sentetiktir ve insan doğrulamasından geçmemiştir. `tool_response` içerikleri
gerçek fonksiyon çalıştırılarak değil model tarafından üretilmiştir; hesaplar örneklem
üzerinden doğrulanmış ancak tamamı tek tek kontrol edilmemiştir. Senaryo tutarsızlığı
%3,1'dir (37 örnekte çağrı beklenirken liste boş). Ayrıntı: [dataset kartı](https://huggingface.co/datasets/bilalabic/math-toolcall-tr).

## Lisans

Apache-2.0. Temel model [Gemma kullanım şartlarına](https://ai.google.dev/gemma/terms) tabidir.
