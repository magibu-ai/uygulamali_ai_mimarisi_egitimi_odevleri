---
license: mit
language:
- tr
tags:
- e-commerce
- ner
- named-entity-recognition
- synthetic
- nemo-data-designer
- deepseek
size_categories:
- 1K<n<10K
task_categories:
- token-classification
- text-classification
---

# 🛒 Natural Turkish E-Commerce NER Dataset (1700 Samples)

Bu veriseti, **NVIDIA NeMo Data Designer** ve **Hugging Face Inference Provider** (`deepseek-ai/DeepSeek-V4-Flash:fireworks-ai`) kullanılarak üretilmiş sentetik ve yüksek kaliteli doğal Türkçe e-ticaret ürün adları ile Named Entity Recognition (NER) etiketlerini içermektedir.

## 📊 Veriseti Özeti

- **Toplam Kayıt Sayısı**: 1700 adet
- **Dil**: Türkçe (TR)
- **Kategoriler**: Ayakkabı, Çanta, Giyim, Aksesuar, Elektronik, Ev & Mutfak, Mobilya & Dekorasyon, Kozmetik, Kişisel Bakım, Spor & Outdoor
- **Format**: JSON Lines (`.jsonl`)

## 🏷️ NER Etiketleri (Entities)

| Etiket | Açıklama | Örnek |
|---|---|---|
| `BRAND` | Marka Adı | *Nike, Samsung, Enza Home, Pierre Cardin* |
| `CATEGORY` | Ürün Kategorisi / Türü | *Spor Ayakkabı, Akıllı Telefon, Masa Örtüsü* |
| `MODEL` | Model veya Ürün Serisi | *Air Max 270, Galaxy S24, Viyana* |
| `COLOR` | Renk Bilgisi | *Siyah, Uzay Grisi, Bej, Lacivert* |
| `SIZE_VARIANT` | Beden / Boyut / Kapasite | *42 Numara, XL, 150x220 cm, 128 GB* |
| `GENDER_TARGET` | Hedef Kitle | *Erkek, Kadın, Çocuk, Unisex* |
| `MATERIAL` | Malzeme / Kumaş Bileşimi | *Pamuk, Deri, Paslanmaz Çelik* |
| `SPECIFICATION` | Nitelik / Teknik Özellik | *Kareli, Kablosuz, Su Geçirmez, Mat Bitiş* |

## 📝 Örnek Veri Formatı

```json
{
  "id": "ecom_ner_00001",
  "product_name": "İstikbal Nova Koltuk Takımı Gri Kumaş 3+1+1",
  "category_domain": "Mobilya & Dekorasyon",
  "entities": [
    {
      "text": "İstikbal",
      "label": "BRAND",
      "start": 0,
      "end": 8
    },
    {
      "text": "Nova",
      "label": "MODEL",
      "start": 9,
      "end": 13
    },
    {
      "text": "Koltuk Takımı",
      "label": "CATEGORY",
      "start": 14,
      "end": 27
    },
    {
      "text": "Gri",
      "label": "COLOR",
      "start": 28,
      "end": 31
    },
    {
      "text": "Kumaş",
      "label": "MATERIAL",
      "start": 32,
      "end": 37
    },
    {
      "text": "3+1+1",
      "label": "SIZE_VARIANT",
      "start": 38,
      "end": 43
    }
  ]
}
```

## 🚀 Kullanım (Hugging Face Datasets)

```python
from datasets import load_dataset

dataset = load_dataset("gururaser/turkish-ecommerce-ner-dataset")
print(dataset["train"][0])
```

## 🛠️ Üretim Detayları

- **Üretici Araç**: NVIDIA NeMo Data Designer (`data-designer`)
- **LLM Model**: `deepseek-ai/DeepSeek-V4-Flash:fireworks-ai`
- **Ofset Doğrulaması**: Karakter başlangıç (`start`) ve bitiş (`end`) konumları tam eşleşme garantili hesaplanmıştır.
