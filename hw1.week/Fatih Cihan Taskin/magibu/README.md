---
license: mit
task_categories:
- text-generation
language:
- tr
- en
tags:
- giresun
- culture
- turkish
- question-answering
- finetuning
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: turkish
    path: data/turkish.parquet
  - split: english
    path: data/english.parquet
---

# Giresun Kültürü Veri Seti

Giresun ilinin kültürel özellikleri üzerine soru-cevap veri seti. Model fine-tune (identity/domain adaptasyonu) çalışmaları için hazırlanmıştır. Format, `alibayram/identity_finetune_magibu_q3` veri setinin yapısıyla aynıdır.

## Yapı

Veri seti `DatasetDict` olarak iki split içerir:

- **turkish**: Türkçe soru-cevap örnekleri (330 örnek)
- **english**: İngilizce karşılık örnekler (275 örnek)

Her örnek tek bir `messages` alanından oluşur; bu alan bir kullanıcı ve bir asistan mesajı içerir:

```json
{
  "messages": [
    {"content": "<soru>", "images": null, "role": "user", "thinking": null, "tool_calls": null},
    {"content": "<cevap>", "images": null, "role": "assistant", "thinking": null, "tool_calls": null}
  ]
}
```

## Kapsam

Örnekler Giresun'un şu kültürel başlıklarını kapsar: coğrafya ve ilçeler, tarih, fındık kültürü, Giresun Adası (Aretias) ve efsaneleri, Aksu Festivali, horon ve kemençe müzik geleneği, yöresel mutfak, ıslık dili (UNESCO somut olmayan kültürel miras), yöresel kıyafetler, tarihi yerler ve yaylalar, türküler ve geleneksel görenekler.

## Oluşturma Yöntemi

1. **Web scraping** (`scrape.py`): Kamuya açık kaynaklardan (Giresun Valiliği, Doğu Karadeniz Kültür Envanteri, Vikipedi vb.) Giresun kültürüne dair ham metin toplanır.
2. **Olgu tabanı** (`facts.py`): Toplanan metinlerden doğrulanmış olgu cümleleri derlenir.
3. **Q&A üretimi** (`qa_pairs.py`): Olgulara bağlı soru-cevap çiftleri elle yazılır; her soru doğal dil ön ekleriyle çoğaltılır.
4. **Formatlama** (`build_dataset.py`): Çiftler hedef `messages` formatına sarılır ve parquet olarak yazılır.

## Yükleme

```python
from datasets import load_dataset

ds = load_dataset("<kullanici>/<repo>")
print(ds["turkish"][0])
```

## Kaynaklar

- T.C. Giresun Valiliği (giresun.gov.tr)
- Doğu Karadeniz Kültür Envanteri Projesi (karadeniz.gov.tr)
- Vikipedi — Giresun Adası
- Giresun İl Kültür ve Turizm Müdürlüğü kaynaklı derlemeler
- Yerel basın (gastronomi ve kemençe/horon festivalleri)

## Lisans

MIT
