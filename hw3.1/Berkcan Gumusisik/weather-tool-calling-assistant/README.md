---
title: SkyBrief Weather Tool Calling
emoji: 🌤️
colorFrom: blue
colorTo: yellow
sdk: gradio
sdk_version: 6.21.0
app_file: app.py
pinned: false
license: mit
short_description: Open-Meteo tool-calling weather briefing agent
---

# SkyBrief — Weather Tool Calling Assistant

SkyBrief, kullanıcı sorularına göre **Open-Meteo** açık API'lerini çağıran bir tool-calling (function calling) hava durumu asistanıdır. Klasik "şehir sıcaklığını göster" örneğinin ötesine geçer: konum çözümleme, anlık atmosfer verisi, çok günlük ufuk tahmini, hava kalitesi ve açık hava aktivite uygunluk skorunu tek bir çok adımlı akışta birleştirir — ve bu adımların her birini kullanıcıya canlı olarak gösterir.

## Bağlantılar

- **GitHub deposu:** https://github.com/berkcangumusisik/weather-tool-calling-assistant
- **Hugging Face Space:** https://huggingface.co/spaces/berkcangumusisik/skybrief-weather-tool-calling

## Özellikler

- **5 araç / JSON şema:** `resolve_location`, `get_atmosphere_snapshot`, `get_horizon_forecast`, `get_air_quality_index`, `rank_outdoor_viability` (tam şemalar `tools.py` içinde, OpenAI function-calling formatında).
- **Görünür araç izi:** Her yanıt öncesi hangi aracın hangi parametrelerle çağrıldığı ve API'den ne döndüğü, sağ paneldeki "araç konsolu"nda `Turn 1 / Turn 2 / ...` şeklinde canlı gösterilir; "Ham iz" bölümünde kopyalanabilir düz metin olarak da sunulur.
- **Çok adımlı planlama:** Karşılaştırma sorularında (ör. "Tokyo mu Berlin mi daha sıcak") her şehir için ayrı araç çağrı zincirleri yürütülür, ardından karşılaştırmalı ve doğal bir Türkçe yanıt üretilir.
- **İki çalışma modu:**
  - *Varsayılan:* API anahtarı gerektirmeyen, aynı JSON şemalarını kullanan çok adımlı çevrimdışı planlayıcı.
  - *İsteğe bağlı:* `GROQ_API_KEY` tanımlıysa Groq (`llama-3.3-70b-versatile`) üzerinden gerçek LLM function-calling döngüsü devreye girer.
- **Modern arayüz:** Gradio ile hazırlanmış, koyu temalı "gözlemevi konsolu" tasarımı; sohbet ve araç konsolu yan yana.

## Örnek çalışma akışı

Kullanıcı: *"İstanbul'da bugün koşuya çıkılır mı? Hava kalitesi de önemli."*

```text
[Turn 1] Araç Çağrıları:
   -> resolve_location(place_name='İstanbul')
   <- {"name": "İstanbul", "latitude": 41.01, "longitude": 28.95, ...}
   -> get_atmosphere_snapshot(latitude=41.01, longitude=28.95)
   <- {"temperature_c": 24.2, "condition": "parçalı bulutlu", ...}
   -> get_air_quality_index(latitude=41.01, longitude=28.95)
   <- {"european_aqi": 32, "category": "iyi", ...}

[Turn 2] Araç Çağrıları:
   -> rank_outdoor_viability(temperature_c=24.2, wind_kmh=14.0, ..., activity='koşu')
   <- {"score": 78, "verdict": "uygun", ...}

[Turn 3] Nihai Yanıt:
İstanbul'da şu anda hava parçalı bulutlu, sıcaklık 24°C civarında...
Koşu için bu hava gayet uygun (puan: 78/100). Hava kalitesi iyi.
```

## Araçlar (JSON şema)

| Araç | Ne yapar |
|---|---|
| `resolve_location` | Yer adını enlem/boylama çevirir (Geocoding API) |
| `get_atmosphere_snapshot` | Anlık sıcaklık, nem, rüzgar, UV, hava durumu |
| `get_horizon_forecast` | 1–7 günlük kısa vadeli tahmin |
| `get_air_quality_index` | Avrupa AQI, ABD AQI, PM2.5, PM10, ozon |
| `rank_outdoor_viability` | Toplanan veriden açık hava uygunluk skoru (yerel hesaplama, API çağırmaz) |

Şemaların tam hâli `tools.py` içinde, ayrıca arayüzdeki "Şemalar ve veri kaynağı" bölümünde görüntülenebilir.

## Proje yapısı

```text
app.py              # Gradio arayüzü
agent.py            # Tool-calling ajan döngüsü + iz formatı
tools.py            # Open-Meteo araçları ve JSON şemaları
requirements.txt
README.md
```

## Yerel çalıştırma

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Tarayıcıda `http://127.0.0.1:7860` açılır.

### İsteğe bağlı: gerçek LLM function-calling

```bash
export GROQ_API_KEY=gsk_...
python app.py
```

## Veri kaynağı

- [Open-Meteo Forecast API](https://open-meteo.com/en/docs)
- [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)

API anahtarı gerekmez, tüm uçlar ücretsiz ve herkese açıktır.

