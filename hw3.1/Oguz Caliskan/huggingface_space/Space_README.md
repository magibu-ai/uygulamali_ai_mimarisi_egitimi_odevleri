---
title: Sondaj
emoji: 🛢️
colorFrom: blue
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
---

# Sondaj

Sondaj günlük raporlarını analiz etmek üzere fine-tune edilmiş bir dil modelinin (Qwen3 tabanlı) Gradio arayüzü. **ZeroGPU** donanımı kullanır, model private bir Hugging Face reposundan (`HF_TOKEN` secret'ı ile) indirilip yüklenir.

## Sekmeler

### 1. Sohbet (Tool Calling)
Genel bir sohbet arayüzü; model, gerektiğinde aşağıdaki araçları çağırabilir:
- **ISS Konumu** — Uluslararası Uzay İstasyonu'nun anlık enlem/boylam bilgisi (Open Notify API, key gerektirmez)
- **Hava Durumu** — verilen şehir için 5 günlük tahmin (Open-Meteo API, key gerektirmez)

Örnek sorular: *"ISS şu an nerede?"*, *"İstanbul'da önümüzdeki hafta hava nasıl olacak?"*

### 2. Rapor Analizi (Structured Output)
Bir günlük sondaj raporu metni yapıştırıp, modelin bunu sabit bir JSON şemasına (`kuyu_adi`, `guncel_faz`, `kacak_var_mi`, `kacak_seviyesi`, `centralizer_gerekli_mi`, `ozet`) göre analiz etmesini sağlar.

## Teknik Notlar

- **Model çıkarımı** doğrudan `transformers` ile yapılır (Ollama kullanılmaz) — ZeroGPU sadece Gradio SDK ile uyumlu olduğu için Docker/Ollama tabanlı bir kuruluma izin vermiyor.
- **Prompt formatı** modelin kendi Jinja chat template'i yerine, Python içinde elle (ChatML formatında) inşa edilir; modelin gömülü chat template'i `tools` parametresiyle birlikte kullanıldığında bir uyumsuzluk hatası veriyordu, bu yüzden bu geçici çözüm uygulandı.
- **Thinking:** Model, eğitimi gereği `<think>...</think>` bloğuyla düşünme eğiliminde olabilir; bu blok kullanıcıya gösterilmeden filtrelenir (model performansını korumak için thinking kapatılmaz, sadece görünürlükten kaldırılır).
- **Structured Output güvencesi sınırlıdır:** `transformers` üzerinden grammar-kısıtlamalı (guaranteed) JSON çıktısı alınamadığı için, prompt-tabanlı bir yaklaşım + `pydantic` doğrulama + en fazla 3 deneme kullanılır. Model her zaman şemaya %100 uygun çıktı üretmeyebilir.
- **Tool calling deneyseldir:** Modelin fine-tune verisinde tool-call örnekleri yoktu; bu yetenek, base Qwen3 modelinden kalan genel kapasiteye dayanır, garanti edilmez.

## Gereksinimler

Bu Space, private bir model reposuna (`HF_TOKEN` secret'ı ile) ve **ZeroGPU** donanımına ihtiyaç duyar (Space Settings → Hardware).

## Bilinen Sınırlamalar

- Cevap kalitesi/tutarlılığı, modelin küçük ölçekli (8B) ve dar bir alanda (sondaj rapor analizi) fine-tune edilmiş olmasından etkilenir; genel konularda base model kadar güçlü olmayabilir.
- İlk istek, ZeroGPU'nun dinamik GPU tahsisi ve modelin GPU'ya taşınması nedeniyle daha yavaş olabilir.
