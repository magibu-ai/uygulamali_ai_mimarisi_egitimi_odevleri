---
language:
- tr
license: other
task_categories:
- question-answering
- multiple-choice
tags:
- e-ticaret
- musteri-hizmetleri
- turkce
- trendyol
- benchmark
pretty_name: Trendyol Marangoz Satıcı Asistanı Benchmark
size_categories:
- n<1K
---

# Trendyol Marangoz Satıcı Asistanı Benchmark

Bu veri kümesi, [SalihHub/trendyol-marangoz-urun-asistan-qa](https://huggingface.co/datasets/SalihHub/trendyol-marangoz-urun-asistan-qa)
ile aynı yöntemle ama **eğitim verisinde bulunmayan 6 farklı üründen** toplanan
alıcı sorusu / satıcı cevabı çiftlerinden türetilmiş, çoktan seçmeli bir
değerlendirme (benchmark) setidir. Fine-tune edilmiş satıcı asistanı modelini
ve diğer genel amaçlı modelleri aynı senaryo üzerinden karşılaştırmak için
hazırlanmıştır.

## İçerik

- **Toplam soru sayısı:** 139
- **Sütunlar:**
  - `urun_id`: Kaynak Trendyol ürün kimliği.
  - `urun_aciklamasi`: Modelin bağlam olarak göreceği ürün özellikleri metni.
  - `kategori`: Sorunun konusu (malzeme, olcu, renk, aksesuar_parca, stok_varyant,
    kargo_lojistik, garanti, kurulum, diger).
  - `soru`: Alıcının sorusu (gerekiyorsa, ürün bilgisinde yer almayan bir bilgi
    alıcının zaten öğrenmiş/duymuş olduğu doğal bir cümleyle sorunun içine
    gömülmüştür; bkz. Üretim Süreci).
  - `soru_orijinal`: Bu gömme işleminden önceki, veri setindeki orijinal soru.
  - `secenekler`: `A`-`D` harfleriyle etiketlenmiş 4 şık.
  - `dogru_secenek`: Doğru şıkkın harfi.

## Şıkların tasarımı

Her soru için 4 şık, sadece doğru/yanlış bilgiyle değil **üslupla** da ayrışacak
şekilde tasarlandı:
- Doğru şık: gerçek veriyle tutarlı, kibar ve müşteriyi (bilgi olumsuz olsa bile)
  kırmadan/ilgisini canlı tutarak yanıtlayan bir cevap.
- Bir yanlış şık: aynı kibar üslupta ama gerçek bilgiyle çelişen yanlış bir cevap.
- Bir yanlış şık: doğru bilgiyi içeren ama kaba/soğuk, ikna çabası olmayan bir cevap.
- Bir yanlış şık: konuyla ilgisiz, veri setindeki gerçek kalıp/otomatik mesajlara
  benzer bir şablon cevap.

## Üretim süreci

1. Trendyol'un "Satıcıya Sor" bölümünden 6 üründen ham soru-cevap verisi
   Selenium ile toplandı (bkz. `Ders2/DataCollection-Scrapping/TrendyolScrapper.py`).
2. Ham veri, ürün başına tek bir LLM çağrısıyla analiz edilip şablon/otomatik
   cevaplar elenerek tutarlı bir soru havuzuna indirgendi
   (`Ders4/BenchmarkSoruHavuzuAnalizi.ipynb`).
3. Her soru, gerekiyorsa ürün bilgisinde yer almayan bilgiyi doğal bir cümleyle
   içine alacak şekilde genişletildi, ardından 1 doğru + 3 yanlış şık üretildi
   ve şıklar rastgele harflere dağıtıldı (`Ders4/CoktanSecmeliBenchmarkOlustur.ipynb`).

## Kullanım alanı ve sınırlamalar

- Bu veri kümesi eğitim/araştırma ve portföy amaçlıdır.
- Şıklar bir LLM tarafından üretildiği için nadiren hatalı/tutarsız olabilir.
- Veriler halka açık bir e-ticaret platformundan toplanmıştır; ticari kullanım
  öncesi ilgili platformun kullanım şartlarını gözden geçirmeniz önerilir.
