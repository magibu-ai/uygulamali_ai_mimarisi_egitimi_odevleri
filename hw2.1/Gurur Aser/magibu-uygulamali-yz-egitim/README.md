---
base_model: unsloth/qwen3-4b-instruct-2507-unsloth-bnb-4bit
tags:
- text-generation-inference
- transformers
- unsloth
- qwen3
- mmlu
- evaluation
license: cc-by-nc-4.0
language:
- tr
datasets:
- gururaser/ithaki-bilimkurgu-klasikleri
- alibayram/yapay_zeka_turkce_mmlu_model_cevaplari
---

# Qwen3 4B Bilimkurgu - Türkçe MMLU Benchmark & Model Kartı

- **Geliştirici:** [gururaser](https://huggingface.co/gururaser)
- **Lisans:** cc-by-nc-4.0
- **Eğitildiği Taban Model:** [unsloth/qwen3-4b-instruct-2507-unsloth-bnb-4bit](https://huggingface.co/unsloth/qwen3-4b-instruct-2507-unsloth-bnb-4bit)
- **Eğitim Veri Seti:** [gururaser/ithaki-bilimkurgu-klasikleri](https://huggingface.co/datasets/gururaser/ithaki-bilimkurgu-klasikleri)
- **Model Linki:** [gururaser/qwen3-4b-bilimkurgu](https://huggingface.co/gururaser/qwen3-4b-bilimkurgu)

---

## 📈 Türkçe MMLU Benchmark Test Sonuçları

Model, [alibayram/yapay_zeka_turkce_mmlu_model_cevaplari](https://huggingface.co/datasets/alibayram/yapay_zeka_turkce_mmlu_model_cevaplari) test seti kullanılarak Türkçe MMLU benchmark değerlendirmesine tabi tutulmuş ve taban model ile karşılaştırılmıştır:

### 📊 Türkçe MMLU Benchmark Karşılaştırma Tablosu

| Model Türü | Model Adı | Genel Başarı (%) | Doğru / Toplam Soru | Test Süresi (sn) |
|---|---|---|---|---|
| Base Model | `unsloth/qwen3-4b-instruct-2507-unsloth-bnb-4bit` | **%26.21** | 1625 / 6200 | 218.40s |
| Fine-Tuned Model | `gururaser/qwen3-4b-bilimkurgu` | **%34.35** | 2130 / 6200 | 251.23s |

---

### 🧪 Test Metodolojisi ve Detaylar

- **Değerlendirme Kodu:** `alibayram/yapay_zeka_turkce_mmlu_bolum_sonuclari/olcum.py` mantığı temel alınmıştır.
- **Anlamsal Karşılaştırma:** `paraphrase-multilingual-mpnet-base-v2` modeli ile üretilen cevabın doğru şık / harf ile anlamsal vektör benzerliği kontrol edilmiştir.
- **Ortam:** Google Colab T4 GPU (4-bit NF4 Quantization)
- **Test Veri Seti:** `alibayram/yapay_zeka_turkce_mmlu_model_cevaplari`

[<img src="https://raw.githubusercontent.com/unslothai/unsloth/main/images/unsloth%20made%20with%20love.png" width="200"/>](https://github.com/unslothai/unsloth)
