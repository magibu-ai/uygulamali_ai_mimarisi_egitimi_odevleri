---
title: Deprem Asistanı
emoji: 🌍
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: 5.34.1
app_file: app.py
pinned: false
---

# 🌍 Deprem Asistanı

Doğal dilde sorduğunuz deprem sorularını, **USGS Earthquake API**'sinden
gerçek veri çekerek yanıtlayan bir Tool Calling uygulaması.

## Ne yapar?

Bir dil modeli (Llama-3.3-70B), sorunuza göre arka planda doğru fonksiyonları
çağırır (Tool Calling), gerçek veriyi çeker ve yanıtı üretir. Hangi araçların
hangi sırayla çağrıldığı ekranda açıkça gösterilir.

## Örnek sorular

- İstanbul'a yakın son bir haftada 4+ deprem oldu mu?
- Antalya'da son 3 günde deprem oldu mu?
- Dünyada son 24 saatte 5+ büyüklüğünde deprem oldu mu?

## Kullanılan araçlar

- `get_coordinates` — şehir adını koordinata çevirir (Open-Meteo)
- `get_earthquakes_near` — bir konuma yakın depremleri getirir (USGS)
- `get_recent_earthquakes` — dünya genelinde son depremleri getirir (USGS)

## Yerelde çalıştırma

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="..."   # kendi Groq anahtarınız
python app.py
