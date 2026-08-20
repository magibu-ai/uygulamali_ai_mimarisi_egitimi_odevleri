# İki Ayrı Ödev — BPE Tokenizer & Minyatür Transformer Eğitimi

**Görev:** Mineral / değerli taş adı üretme.
**Metin:** kendi derlediğim korpus, **1000 mineral/taş adı** (`data/mineraller.txt`),
her satırda bir ad.

Bu klasör **birbirinden bağımsız iki ödevi** barındırır. İkisi de aynı metni
kullanır ama biri diğerinin girdisi **değildir**.

| | Ödev 1 — BPE Tokenizer | Ödev 2 — Model eğitimi |
| --- | --- | --- |
| Ne yapar | Metinden BPE ile tokenizasyon kurar | Modelleri teker teker eğitip ad üretir |
| Token sistemi | BPE (vocab 500) | **Karakter** (vocab 32) |
| Kod | `hf_bpe.py` | `train_all.py`, `train_model.py`, `generate_model.py` |
| Çıktı | `tokenizer.json` | `checkpoints/*.pt` |
| Sonuçlar | `BPE_SONUCLAR.md` | `SONUCLAR.md`, `SONUCLAR_LOG.md` |

> **Not:** `tokenizer.json` model eğitiminde **kullanılmaz**. Eğitim, repodaki
> `CharTokenizer` ile karakter seviyesinde yapılır. İki ödev birbirine bağlı değil.

## Ödev 1 — BPE Tokenizer (HuggingFace `tokenizers`, hazır kütüphane)

Korpustan BPE eğitilir: algoritma harfleri tek tek alır, en sık geçen ikilileri
adım adım birleştirerek sözlük kurar. Standart **`tokenizer.json`** üretilir
(HF LLM Course böl. 6.5 yolu). Mineral adlarının sık tekrar eden ekleri
(`pirit`, `matit`, `kolumbit`, `kalko`) tek token olur.

```
'hematit'    -> ['he', 'matit', '\n']
'kalkopirit' -> ['kalko', 'pirit', '\n']
```

Ayrıntı ve doğrulama: **`BPE_SONUCLAR.md`**.

## Ödev 2 — Karakter token'larıyla model eğitimi

[malibayram/single_letter_transformers](https://github.com/malibayram/single_letter_transformers)
reposundaki minyatür modeller, reponun **kendi karakter tokenizer'ı**
(`tokenizer.py` → `CharTokenizer`) ile teker teker eğitilir: her token tek
karakter, `\n` hem ad ayıracı hem EOS. Karakter sözlüğü doğrudan korpustan
kurulur (**32** karakter).

Repodaki BÜTÜN dil modelleri eğitildi:

| key | Sınıf | Parametre | Özellik |
| --- | --- | --- | --- |
| `qwen3`     | TinyQwen     | 20K | Yoğun: RMSNorm+RoPE+GQA+SwiGLU |
| `qwen3_5`   | TinyQwen35   | 42K | Hibrit: Gated DeltaNet + tam attention |
| `gemma4`    | TinyGemma    | 63K | Sliding-window, sandwich norm, GeGLU |
| `deepseek3` | TinyDeepSeek | 48K | MLA + MoE (uzman karışımı) |

`acestep` (ses üretimi) ve `lora` (fine-tune eklentisi) bilerek dışarıda —
metin üretme göreviyle alakasız.

Sonuçlar: **`SONUCLAR.md`** (anlatım), **`SONUCLAR_LOG.md`** (checkpoint'lerden
otomatik üretilen gerçek metrikler).

## Dosyalar

| Dosya | Ne yapar |
| --- | --- |
| `data/mineraller.txt` | Metin — 1000 mineral/taş adı, her satırda biri |
| `hf_bpe.py` | **Ödev 1:** HF `tokenizers` ile BPE → `tokenizer.json` |
| `train_all.py` | **Ödev 2:** 4 modelin **hepsini** sırayla eğitir |
| `train_model.py <key>` | **Ödev 2:** tek modeli karakter token'larıyla eğitir → `checkpoints/<key>.pt` |
| `generate_model.py <key> [n] [T]` | Eğitilmiş modelden mineral adı üretir |
| `sonuclar_uret.py` | Checkpoint'lerden **otomatik** rapor → `SONUCLAR_LOG.md` |
| `checkpoints_bpe/` | Arşiv: BPE token'larıyla eğitilmiş eski modeller (teslimin parçası değil) |

## Çalıştırma

```bash
python3 -m venv venv && source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install tokenizers          # yalnızca Ödev 1 için

cd proje

# Ödev 1 — BPE
python hf_bpe.py                          # -> tokenizer.json

# Ödev 2 — karakter eğitimi (BPE'ye ihtiyaç duymaz)
python train_all.py                       # 4 modeli de eğit -> checkpoints/*.pt
python train_model.py gemma4              # ya da teker teker
python generate_model.py gemma4 20 0.8    # gemma4'ten 20 ad, sıcaklık 0.8
python sonuclar_uret.py                   # gerçek sonuç raporu -> SONUCLAR_LOG.md
```

## Nasıl çalışıyor (Ödev 2)

1. **Karakter tokenizer:** `CharTokenizer.from_file(mineraller.txt)` sözlüğü
   metinde geçen karakterlerden kurar. `\n` ad ayıracı ve EOS.
2. **Eğitim** (`train_model.py`): her model kendi klasöründen aynen import edilir
   (`ModelConfig(vocab_size=32)`), karakter id'leriyle next-token tahmini
   eğitilir. Her model ayrı subprocess'te → aynı adlı dosyalar (`config.py`,
   `model.py`, `tokenizer.py`) çakışmaz.
3. **Üretim** (`generate_model.py`): EOS'tan başla, otoregresif üret, sonraki
   EOS'a kadar decode et.
