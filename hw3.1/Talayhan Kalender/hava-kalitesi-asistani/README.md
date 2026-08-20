---
title: Tool Calling Air Quality Demo
emoji: 🌫️
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# 🌫️ Tool Calling Ödevi — Hava Kalitesi Asistanı

Bir LLM'in **Tool Calling / Function Calling** yeteneğini kullanarak açık bir
Public API'den (OpenAQ) hava kirliliği verisi çekmesini ve bu veriyi işleyerek
kullanıcıya doğal dilde yanıt vermesini gösteren uçtan uca bir örnek.

## 1. Kullanılan Public API

**[OpenAQ v3](https://docs.openaq.org/)** — dünya çapında, gerçek zamanlı, resmi
hava kirliliği ölçüm verisi sunan açık kaynaklı (nonprofit) bir platform.

> ⚠️ **Önemli not:** OpenAQ v1/v2 ücretsiz ve keysiz kullanılıyordu, ancak
> **v3'te API key zorunlu hale geldi** (v1/v2, Ocak 2025'te tamamen kapatıldı).
> Key hâlâ **tamamen ücretsiz**, sadece kayıt gerektiriyor — bkz. aşağıdaki
> "OpenAQ API Key Alma" bölümü.

Ayrıca şehir ismini enlem/boylama çevirmek için **Open-Meteo Geocoding API**
(tamamen keysiz) yardımcı olarak kullanılıyor, çünkü OpenAQ şehir ismiyle değil
konum (nokta + yarıçap) bazlı sorgu yapıyor.

## 2. Tool / Function Şemaları

| Tool | Açıklama | Parametreler | API çağırır mı? |
|---|---|---|---|
| `get_air_quality` | Bir şehre en yakın OpenAQ istasyonundaki güncel PM2.5 değerini (µg/m³) getirir | `city: string` | ✅ OpenAQ + Open-Meteo geocoding |
| `interpret_aqi` | Bir PM2.5 değerini ABD EPA kategorilerine göre yorumlar (İyi/Orta/Sağlıksız...) ve tavsiye verir | `pm25_ugm3: number` | ❌ Saf hesaplama (local) |

## 3. Model Entegrasyonu

Model olarak **Hugging Face Inference Providers** üzerinden, OpenAI-uyumlu
Chat Completions endpoint'i ile `openai/gpt-oss-120b` kullanılıyor.

```python
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)
```

`run_agent()` fonksiyonu klasik **tool-calling döngüsünü** uygular:

1. Kullanıcı mesajı + tool şemaları modele gönderilir.
2. Model `tool_calls` döndürürse, ilgili Python fonksiyonu gerçekten
   çalıştırılır (OpenAQ'ya HTTP isteği atılır) ve sonucu `role: "tool"`
   mesajı olarak tekrar modele geri beslenir.
3. Model tekrar çağrılır; gerekirse ikinci tool'u (`interpret_aqi`) çağırır,
   yoksa nihai doğal dil cevabını üretir.
4. Tüm adımlar bir **trace log**'a yazılır ve arayüzde "🔧 Tool çağrı adımları"
   bölümünde şeffaf şekilde gösterilir.

### `get_air_quality` içindeki API akışı (detay)

```
1) Open-Meteo Geocoding : "İstanbul" -> (lat, lon)
2) GET /v3/locations?coordinates={lat},{lon}&radius=25000
   -> en yakın istasyonlar + her istasyonun sensör listesi (pm25 var mı?)
3) GET /v3/locations/{id}/latest
   -> istasyondaki tüm sensörlerin en güncel ölçümleri (sensorsId ile)
4) sensorsId eşleştirilerek PM2.5 değeri ve ölçüm zamanı bulunur
```

### Örnek çalışma akışı

```
Kullanıcı: "İstanbul'un hava kalitesi bugün nasıl, dışarıda spor yapmak güvenli mi?"

[Turn 1] Araç Çağrıları:
   -> get_air_quality(city='İstanbul')
   <- {'city': 'İstanbul', 'station': 'Sultangazi', 'distance_km': 4.2,
       'pm25_ugm3': 38.6, 'unit': 'µg/m³', 'measured_at_utc': '2026-07-30T09:00:00Z'}

[Turn 2] Araç Çağrıları:
   -> interpret_aqi(pm25_ugm3=38.6)
   <- {'pm25_ugm3': 38.6, 'category': 'Hassas Gruplar İçin Sağlıksız',
       'advice': 'Çocuklar, yaşlılar ve solunum hastaları dışarıda yoğun aktiviteden kaçınmalı.'}

[Turn 3] Nihai Yanıt:
İstanbul'da (Sultangazi istasyonu) PM2.5 şu an 38.6 µg/m³ ile "Hassas Gruplar
İçin Sağlıksız" seviyesinde. Genel dışarı aktiviteler sorun değil ama
çocuklar, yaşlılar ve solunum hastalarının yoğun egzersizden kaçınması önerilir.
```

## 4. OpenAQ API Key Alma (ücretsiz)

1. [explore.openaq.org/register](https://explore.openaq.org/register) adresinden ücretsiz kayıt ol.
2. [explore.openaq.org/account](https://explore.openaq.org/account) sayfasından API key'ini kopyala.
3. Bu key'i `OPENAQ_API_KEY` ortam değişkeni / secret olarak kullan.

## 5. Yerelde Çalıştırma

```bash
git clone <bu-repo>
cd openaq-tool-calling-hw
pip install -r requirements.txt

export HF_TOKEN="hf_xxx..."          # https://huggingface.co/settings/tokens
export OPENAQ_API_KEY="xxx..."       # https://explore.openaq.org/register

python app.py
```

Uygulama `http://127.0.0.1:7860` adresinde açılır.

## 6. Hugging Face Spaces'e Deploy

1. [huggingface.co/new-space](https://huggingface.co/new-space) → **SDK: Gradio**, ücretsiz CPU basic
2. `app.py`, `requirements.txt`, `README.md` dosyalarını Space reposuna yükle
3. Space **Settings → Variables and secrets** kısmına iki secret ekle:
   - `HF_TOKEN` (Inference Providers izinli HF access token)
   - `OPENAQ_API_KEY` (yukarıdaki adımdan alınan ücretsiz key)
4. Space otomatik build olup yayına alınır
5. Yayın linkini ödev teslim formuna ekle

## 7. Dosya Yapısı

```
openaq-tool-calling-hw/
├── app.py             # Gradio arayüzü + tool-calling mantığı
├── requirements.txt   # Bağımlılıklar
└── README.md          # Bu dosya
```

## 8. Bilinen Sınırlamalar / Genişletme Fikirleri

- Yarıçap sorgusu maksimum 25 km ile sınırlı (OpenAQ API kısıtı); çok küçük
  şehirlerde veya istasyonu az bölgelerde sonuç bulunamayabilir — bu durumda
  `get_air_quality` açık bir `error` mesajı döndürür.
- `interpret_aqi` yalnızca PM2.5 üzerinden basitleştirilmiş bir kategori
  hesaplıyor; gerçek AQI hesaplaması PM10, O3, NO2, SO2, CO gibi diğer
  kirleticileri de birleştirir. İstenirse `get_air_quality` diğer sensörleri
  de (loc'daki `sensors` listesinden) döndürecek şekilde genişletilebilir.
- `MODEL_ID` değiştirilerek Inference Providers'daki başka tool-calling
  destekli modeller (örn. `Qwen/Qwen2.5-72B-Instruct`) denenebilir.
