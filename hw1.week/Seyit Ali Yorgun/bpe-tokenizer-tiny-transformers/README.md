# BPE Tokenizer + Minyatür Transformer Eğitimi

Ders ödevi — **iki ayrı ödev**, ortak metin (kendi derlediğim **1000 mineral/taş
adı** korpusu).

| | Ödev 1 — BPE Tokenizer | Ödev 2 — Model eğitimi |
| --- | --- | --- |
| Ne yapar | Metinden BPE ile tokenizasyon kurar | Modelleri teker teker eğitip mineral adı üretir |
| Token sistemi | BPE (vocab 500) | **Karakter** (vocab 32) |
| Çıktı | `proje/tokenizer.json` | `proje/checkpoints/*.pt` |
| Sonuçlar | [`proje/BPE_SONUCLAR.md`](proje/BPE_SONUCLAR.md) | [`proje/SONUCLAR.md`](proje/SONUCLAR.md) |

İki ödev **birbirine bağlı değildir**: `tokenizer.json` model eğitiminde
kullanılmaz, eğitim karakter seviyesinde yapılır.

Ayrıntılı anlatım: **[`proje/README.md`](proje/README.md)**

## Sonuçlar — Ödev 2 (karakter token'larıyla eğitim)

1000 mineral adı, vocab=32, taban(rastgele) kayıp = ln(32) = 3.47.
CPU, 3000 adım, AdamW lr=3e-3.

| Sıra | Model | Parametre | Son kayıp | İyileşme |
| --- | --- | --- | --- | --- |
| 1 | gemma4    | 63,360 | 0.6425 | 5.4× |
| 2 | qwen3_5   | 42,056 | 0.6761 | 5.1× |
| 3 | deepseek3 | 48,040 | 0.9063 | 3.8× |
| 4 | qwen3     | 19,648 | 1.1683 | 3.0× |

Üretilen adlardan örnekler: `hausmanit`, `böhmit`, `nikelin`, `pirotin`, `götit`,
`karneol`, `inezit`, `klinoklor`, `ferrierit`, `illit`, `simplezit`.

## Kurulum

Modeller [malibayram/single_letter_transformers](https://github.com/malibayram/single_letter_transformers)
reposundan gelir; bu depoya dahil değildir (ayrı bir projedir), yanına klonlanır:

```bash
git clone https://github.com/CYBki/bpe-tokenizer-tiny-transformers.git
cd bpe-tokenizer-tiny-transformers
git clone https://github.com/malibayram/single_letter_transformers.git

python3 -m venv venv && source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install tokenizers          # yalnızca Ödev 1 için
```

Beklenen klasör yapısı:

```
bpe-tokenizer-tiny-transformers/
├── proje/                        # bu depo
└── single_letter_transformers/   # yukarıda klonlanan upstream repo
```

## Çalıştırma

```bash
cd proje

# Ödev 1 — BPE
python hf_bpe.py                          # -> tokenizer.json

# Ödev 2 — karakter eğitimi (BPE'ye ihtiyaç duymaz)
python train_all.py                       # 4 modeli de eğit -> checkpoints/*.pt
python generate_model.py gemma4 20 0.8    # gemma4'ten 20 mineral adı
python sonuclar_uret.py                   # gerçek sonuç raporu -> SONUCLAR_LOG.md
```
