---
language:
- tr
license: other
task_categories:
- text-generation
tags:
- e-ticaret
- musteri-hizmetleri
- turkce
- trendyol
- chain-of-thought
pretty_name: Trendyol Marangoz Ürünleri Soru-Cevap Asistanı
size_categories:
- 1K<n<10K
---

# Trendyol Marangoz Ürünleri Soru-Cevap Asistanı

Bu veri kümesi, Trendyol'daki marangozluk/ahşap ürün kategorisindeki
"Satıcıya Sor" bölümünden toplanan gerçek müşteri sorusu ve satıcı cevabı
çiftlerinden oluşur. Her örneğe, satıcının cevaba nasıl vardığını gösteren,
`google/gemma-4-31b-it:nitro` modeli ile (OpenRouter üzerinden) üretilmiş sentetik bir
`thinking` (iç muhakeme) alanı eklenmiştir.

## İçerik

- **Toplam örnek sayısı:** 1211
- **Sütun:** `conversations` — `[user_mesajı, assistant_mesajı]` şeklinde
  iki mesajlık bir liste. Her mesaj `content`, `images`, `role`,
  `thinking`, `tool_calls` alanlarını içerir.
- `user` mesajının `thinking` alanı her zaman `null`'dır.
- `assistant` mesajının `content` alanı **gerçek** satıcı cevabıdır;
  `thinking` alanı ise LLM tarafından üretilmiş **sentetik** bir
  muhakeme zinciridir (satıcının gerçek iç sesi değildir).

## Üretim süreci

1. Ürün sayfaları ve "Satıcıya Sor" soru-cevapları Selenium ile scrape
   edildi (`TrendyolScrapper.py`).
2. Her soru-cevap için, ürün özellikleri bağlam olarak verilerek
   OpenRouter API'si üzerinden bir LLM'e "bu cevaba varmadan önceki iç
   muhakemeyi yaz" görevi verildi (`fill_thinking.py`).
3. Sonuçlar `conversations` sütunu altında JSONL formatında birleştirildi.

## Kullanım alanı ve sınırlamalar

- Bu veri kümesi eğitim/araştırma ve portföy amaçlıdır.
- `thinking` alanları sentetik olup gerçek satıcı düşüncesini yansıtmaz;
  model çıktısı olarak değerlendirilmelidir.
- Veriler halka açık bir e-ticaret platformundan toplanmıştır; ticari
  kullanım öncesi ilgili platformun kullanım şartlarını gözden
  geçirmeniz önerilir.
