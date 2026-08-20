# ⚡ Turkish E-Commerce NER: Unsloth Qwen3-0.6B Fine-Tuning & 5-Model SOTA Benchmark

Bu çalışma, **1.700 adetlik doğal Türkçe e-ticaret NER veriseti** (`gururaser/turkish-ecommerce-ner-dataset`) kullanılarak **`Qwen/Qwen3-0.6B`** modelinin **Unsloth** ile A100 GPU üzerinde 1.500 veriyle fine-tune edilmesini, elde edilen modelin **GLiNER**, **GLiNER2**, **BERT-Turkish-NER** ve **Base Qwen3-0.6B** modelleriyle 200 adetlik hold-out test setinde benchmark edilmesini ve Hugging Face Hub'a yüklenmesini içermektedir.

---

## 📊 Karşılaştırılan 5 Model Kadrosu

1. **`gururaser/qwen3-0.6b-turkish-ecommerce-ner`**: Bizim Unsloth + LoRA ile 1.500 veride eğittiğimiz model.
2. **GLiNER2 (`fastino/gliner2-base-v1`)**: Zero-Shot Bütünleşik Bilgi Çıkarımı Modeli.
3. **GLiNER (`urchade/gliner_multi-v2.1`)**: Zero-Shot Çift Yönlü Transformer NER Modeli.
4. **BERT-Turkish-NER (`savasy/bert-base-turkish-ner-cased`)**: Geleneksel Türkçe BERT Token Classifier.
5. **Base Qwen3-0.6B (`Qwen/Qwen3-0.6B`)**: Eğitilmemiş taban model (Zero-Shot baseline).

---

## 🏷️ NER Etiket Standardı (8 Anahtar)

- **`BRAND`**: Marka (*Nike, Samsung, İstikbal*)
- **`CATEGORY`**: Ürün Türü (*Spor Ayakkabı, Akıllı TV, Koltuk Takımı*)
- **`MODEL`**: Model / Seri (*Air Max 270, Galaxy S24, Nova*)
- **`COLOR`**: Renk (*Siyah, Beyaz, Uzay Grisi*)
- **`SIZE_VARIANT`**: Beden / Boyut / Kapasite (*42 Numara, 128 GB, 3+1+1*)
- **`GENDER_TARGET`**: Hedef Kitle (*Erkek, Kadın, Çocuk*)
- **`MATERIAL`**: Kumaş / Malzeme (*Deri, Pamuk, Granit*)
- **`SPECIFICATION`**: Nitelik / Özellik (*Su Geçirmez, Kablosuz, Mat Bitiş*)

---

## 📁 Proje Yapısı

```
les4/unsloth_ecommerce_ner_benchmark/
├── turkish_ecommerce_ner_unsloth.ipynb # Uçtan uca Fine-Tuning & 5 Modelli Benchmark Notebook'u
├── requirements.txt                    # Bağımlılıklar (unsloth, gliner, gliner2, seqeval vb.)
└── README.md                           # Proje dokümantasyonu ve metrik raporu
```

---

## 🚀 Çalıştırma Talimatları

A100 GPU ortamında sanal ortamınızı aktif ettikten sonra Jupyter Notebook'u çalıştırın:

```bash
source .venv/bin/activate
pip install -r les4/unsloth_ecommerce_ner_benchmark/requirements.txt
jupyter notebook les4/unsloth_ecommerce_ner_benchmark/turkish_ecommerce_ner_unsloth.ipynb
```
