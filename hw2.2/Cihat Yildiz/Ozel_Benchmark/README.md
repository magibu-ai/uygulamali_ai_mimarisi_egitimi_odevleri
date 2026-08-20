# 🎯 Özel Lojistik Benchmark — Türkçe Tedarik Zinciri Alan Testi

Türkçe lojistik ve tedarik zinciri alanında dil modellerini değerlendirmek için hazırlanmış **özel benchmark** projesidir. Fine-tune edilmiş bir LoRA modeli, 6 farklı LLM ile karşılaştırılmış ve sonuçlar kapsamlı şekilde raporlanmıştır.

> **Sertifika Programı:** [Magibu](https://magibu.com/) — Ders 4: Özel Benchmark Oluşturma Ödevi

---

## 📋 İçindekiler

- [Proje Hakkında](#-proje-hakkında)
- [Ödev Kriterleri](#-ödev-kriterleri)
- [Benchmark Yapısı](#-benchmark-yapısı)
- [Test Edilen Modeller](#-test-edilen-modeller)
- [Metot](#-metot)
- [Proje Akışı](#-proje-akışı)
- [Çıktılar ve Bağlantılar](#-çıktılar-ve-bağlantılar)
- [Kurulum ve Çalıştırma](#-kurulum-ve-çalıştırma)
- [Proje Yapısı](#-proje-yapısı)
- [Lisans](#-lisans)

---

## 🔍 Proje Hakkında

Bu proje, **Türkçe lojistik terminolojisi ve kavramlarına** dair bilgi doğruluğunu ölçmek amacıyla özel bir benchmark oluşturmayı hedefler. Benchmark, aşağıdaki lojistik alt alanlarını kapsamaktadır:

| Alan | Kapsam |
|------|--------|
| 🏭 Depo ve Envanter Yönetimi | WMS, slotting, picking stratejileri, FIFO/LIFO, stok devir hızı |
| 🚛 Taşımacılık ve Rotalama | VRP varyantları, intermodal taşıma, filo yönetimi |
| 🌐 Dış Ticaret ve Gümrük | Incoterms 2020, konşimento türleri, akreditif, gümrük rejimleri |
| 📊 Tedarik Zinciri Planlama | S&OP, MRP, talep tahmini metrikleri (MAPE, bias) |
| 💰 Lojistik Performans ve Maliyet | KPI'lar, birim maliyet analizi, hizmet seviyesi anlaşmaları |
| 📦 E-Ticaret ve Son Mil | Sipariş karşılama, iade yönetimi, dark store, mikro dağıtım |
| ♻️ Yalın ve Sürdürülebilir Lojistik | Muda türleri, kaizen, yeşil lojistik, karbon hesaplama |

---

## ✅ Ödev Kriterleri

| Kriter | Hedef | Gerçekleşen |
|--------|-------|-------------|
| Benchmark soru sayısı | ≥ 100 | **120 soru** |
| Test edilen model sayısı | ≥ 5 | **6 model** |
| Elle yazılmış soru | ≥ 10 | **15 soru** |
| Eğitim dışı veri ayrıldı | %5–10 | **%10 holdout** |
| Benchmark HF'de yayınlandı | — | ✅ |
| Sonuçlar model kartında | — | ✅ |

---

## 📝 Benchmark Yapısı

Benchmark, **120 çoktan seçmeli sorudan** oluşmaktadır:

- **15 elle yazılmış soru** — Lojistik sektöründeki pratik deneyime dayanarak hazırlanmış, CVRPTW, OTIF, FOB, EOQ, Cross-docking, Bullwhip etkisi gibi konuları kapsayan sorular
- **105 sentetik soru** — GPT-4o mini ile 7 farklı konu grubundan (grup başına ~15 soru) üretilmiş sorular

**Format:**
```json
{
  "soru": "Bir dağıtım merkezinden 40 müşteriye teslimat yapılacaktır...",
  "secenekler": ["Atama problemi", "CVRPTW", "Doğrusal programlama", "...", "..."],
  "cevap": 1,
  "kategori": "Elle Yazılmış"
}
```

- Her sorunun **5 seçeneği** bulunmaktadır (A–E)
- **Rastgele başarı tabanı:** %20
- **Puanlama:** Accuracy (doğru / toplam)

---

## 🤖 Test Edilen Modeller

| # | Model | Tip | Açıklama |
|---|-------|-----|----------|
| 1 | `cihatyldz/lojistik-lora-adapter` | LoRA fine-tuned | Kendi eğittiğim model |
| 2 | `Qwen3-1.7B` | Base model | Karşılaştırma için |
| 3 | `Qwen2.5-1.5B-Instruct` | Instruct model | Farklı nesil Qwen |
| 4 | `Llama-3.2-3B-Instruct` | Instruct model | Meta |
| 5 | `gemma-3-1b-it` | Instruct model | Google |
| 6 | `SmolLM2-1.7B-Instruct` | Instruct model | HuggingFace |

> 🔋 **Bellek yönetimi:** Her model test edildikten sonra GPU belleği `torch.cuda.empty_cache()` ve `gc.collect()` ile temizlenir.

---

## 🔬 Metot

### Cevap Değerlendirme (3 Aşamalı)

Model çıktılarının değerlendirilmesinde 3 aşamalı bir yaklaşım kullanılmıştır:

1. **Doğrudan harf eşleşmesi** — Çıktı tek bir harf ise (A, B, C, D, E)
2. **Harf + ayraç eşleşmesi** — `A:`, `A)`, `A-` gibi formatlar
3. **Anlamsal benzerlik (fallback)** — `paraphrase-multilingual-mpnet-base-v2` modeli ile seçeneklere en yakın cevap bulunur

### Model Yükleme

Tüm modeller **4-bit quantize** (`bnb-4bit`) olarak yüklenerek T4 GPU üzerinde çalıştırılabilir hale getirilmiştir. [Unsloth](https://github.com/unslothai/unsloth) kütüphanesi kullanılmıştır.

---

## 🔄 Proje Akışı

```
1. Kurulum & Token Ayarları
         │
         ▼
2. Eğitim Verisinden %10 Holdout Ayırma
         │
         ▼
3. 15 Elle Yazılmış Soru Hazırlama
         │
         ▼
4. GPT-4o mini ile 105 Sentetik Soru Üretimi
         │
         ▼
5. Benchmark Birleştirme & Doğrulama (120 soru)
         │
         ▼
6. Benchmark'ı HuggingFace'e Yayınlama
         │
         ▼
7. 6 Modeli Benchmark ile Test Etme
         │
         ▼
8. Sonuçları Karşılaştırma & Görselleştirme
         │
         ▼
9. Model Kartını Güncelleme
```

---

## 🔗 Çıktılar ve Bağlantılar

| Çıktı | Bağlantı |
|-------|----------|
| 🤗 Fine-tuned Model | [`cihatyldz/lojistik-lora-adapter`](https://huggingface.co/cihatyldz/lojistik-lora-adapter) |
| 📊 Benchmark Veri Seti | [`cihatyldz/lojistik-benchmark`](https://huggingface.co/datasets/cihatyldz/lojistik-benchmark) |
| 📚 Eğitim Veri Seti | [`cihatyldz/lojistik-soru-cevap`](https://huggingface.co/datasets/cihatyldz/lojistik-soru-cevap) |

**Yerel çıktılar:**
- `benchmark_sonuclari.json` — Tüm modellerin sonuç verileri
- `benchmark_sonuclari.png` — Karşılaştırma grafikleri
- `lojistik_benchmark.jsonl` — Benchmark yerel yedek

---

## ⚙️ Kurulum ve Çalıştırma

### Gereksinimler

- Python 3.10+
- CUDA destekli GPU (T4 veya üstü önerilir)
- Google Colab (önerilen ortam)

### Kurulum

```bash
pip install unsloth
pip install -q datasets huggingface_hub pandas sentence-transformers openai
```

### Ortam Değişkenleri

Notebook, Google Colab `userdata` üzerinden veya manual giriş ile aşağıdaki tokenları bekler:

| Değişken | Açıklama |
|----------|----------|
| `HF_TOKEN` | HuggingFace API token'ı |
| `OPENAI_API_KEY` | OpenAI API anahtarı (sentetik soru üretimi için) |

### Çalıştırma

1. `ozel_benchmark.ipynb` dosyasını **Google Colab** üzerinde açın
2. Runtime → **T4 GPU** seçin
3. Hücreleri sırayla çalıştırın

---

## 📂 Proje Yapısı

```
Ders4/
├── ozel_benchmark.ipynb          # Ana notebook (benchmark oluşturma & test)
├── odev.txt                      # Ödev açıklaması ve kriterleri
├── single_letter_transformers/   # Referans kaynak (LLM benchmark & kuantizasyon)
└── README.md                     # Bu dosya
```

---

## 🛠️ Kullanılan Teknolojiler

| Teknoloji | Kullanım Amacı |
|-----------|----------------|
| [Unsloth](https://github.com/unslothai/unsloth) | Hızlı LoRA fine-tuning ve 4-bit model yükleme |
| [HuggingFace Datasets](https://huggingface.co/docs/datasets) | Veri seti yönetimi ve yayınlama |
| [Sentence Transformers](https://www.sbert.net/) | Anlamsal benzerlik ile cevap değerlendirme |
| [OpenAI API](https://platform.openai.com/) | GPT-4o mini ile sentetik soru üretimi |
| [Matplotlib](https://matplotlib.org/) | Sonuç görselleştirme |
| [SafeTensors](https://github.com/huggingface/safetensors) | Model ağırlık doğrulaması |

---

## 👤 Yazar

**Cihat Yıldız**
- HuggingFace: [`cihatyldz`](https://huggingface.co/cihatyldz)

---

## 📄 Lisans

Bu proje eğitim amaçlıdır. Benchmark veri seti MIT lisansı altında yayınlanmıştır.
