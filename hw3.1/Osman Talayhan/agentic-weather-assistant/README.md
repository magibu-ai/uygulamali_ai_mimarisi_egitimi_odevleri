---
title: Magibu Agentic Weather Assistant
emoji: ⛅
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.36.1
app_file: app.py
pinned: false
---

# Agentic Weather Assistant (Tool Calling Architecture)

Bu proje, açık kaynaklı bir yapay zeka modelinin (Qwen 2.5 3B) dış dünyadan gerçek zamanlı veri çekebilmesini (Tool Calling / Function Calling) sağlayan bir uygulamadır. 

Ödevin isterleri doğrultusunda, **Open-Meteo Public API**'si kullanılmış ve uygulamanın arka plandaki tüm "Düşünce Adımları" (Araç çağırma süreçleri) Gradio arayüzünde şeffaf bir şekilde kullanıcıya sunulmuştur.

## Kullanılan Teknolojiler
- **Model:** Qwen/Qwen2.5-3B-Instruct (ZeroGPU üzerinde çalışmaktadır)
- **API:** Open-Meteo (Hava Durumu API'si)
- **Arayüz:** Gradio
- **Altyapı:** Hugging Face Spaces & `@spaces.GPU`

## Fonksiyonlar (Tools)
Modelin kullanımına iki adet JSON şemasıyla tanımlanmış araç (tool) sunulmuştur:
1. `get_weather(city)`: Belirtilen şehrin koordinatlarını bulur ve anlık sıcaklık değerini Celsius cinsinden getirir.
2. `convert_temperature(value, to_unit)`: Sıcaklık değerini Fahrenheit veya Celsius'a çevirir.

## Çalışma Akışı
Kullanıcı bir soru sorduğunda model doğrudan cevap vermek yerine önce araca ihtiyaç duyup duymadığını analiz eder. İhtiyaç duyarsa özel XML formatında bir araç çağrısı (`<tool_call>`) üretir. Python kodu bu çağrıyı yakalar, API'ye istek atar ve sonucu modele geri besler. Model elde ettiği gerçek verilerle **[Nihai Yanıt]**'ı üretir.
