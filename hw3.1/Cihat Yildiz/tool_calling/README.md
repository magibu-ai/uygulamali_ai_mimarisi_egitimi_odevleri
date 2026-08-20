# 🚛 LojistikAI — Tool Calling

Lojistik ve tedarik zinciri sorularını **canlı public API'lere** bağlanarak yanıtlayan tool calling (function calling) sistemi. Model, soruya göre uygun aracı otomatik seçer, gerektiğinde araçları paralel veya zincirleme çağırır ve **hangi araçları hangi parametrelerle çağırdığını kullanıcıya adım adım gösterir**.

🔗 **Canlı demo:** [huggingface.co/spaces/cihatyldz/lojistik-tool-calling](https://huggingface.co/spaces/cihatyldz/lojistik-tool-calling)

---

## 🔧 Araçlar

Dört aracın tamamı ücretsiz ve **API anahtarı gerektirmeyen** kaynaklara bağlanır.

| Araç | Veri Kaynağı | Lojistik Kullanımı |
|------|-------------|--------------------|
| `get_weather` | [Open-Meteo](https://open-meteo.com/) | Sevkiyat koşulları, soğuk zincir riski, rota güvenliği |
| `get_route_distance` | [OSRM](https://project-osrm.org/) | Karayolu mesafe & süre, nakliye maliyeti, teslim planı |
| `get_exchange_rate` | [Frankfurter](https://frankfurter.app/) | Navlun fiyatlandırma, ithalat/ihracat maliyeti |
| `convert_unit` | Yerel hesaplama | Sıcaklık (C/F/K), mesafe (km/mil/nm/ft), ağırlık (kg/ton/lb/oz) |

---

## 💬 Örnek Çalışma Akışları

Aşağıdaki çıktılar sistemin gerçek çalıştırma sonuçlarıdır.

### 1) Paralel + zincirleme araç çağrısı

**Kullanıcı:** *"İstanbul mu daha sıcak Rotterdam mı? Değerleri Fahrenheit olarak da yaz."*

```text
[Turn 1] Araç Çağrıları:
   -> get_weather(city='İstanbul')
   <- {"sehir": "İstanbul", "ulke": "Türkiye Cumhuriyeti", "sicaklik_c": 24.4,
       "yagis_mm": 0.0, "ruzgar_kmh": 20.9, "durum": "açık"}
   -> get_weather(city='Rotterdam')
   <- {"sehir": "Rotterdam", "ulke": "Hollanda", "sicaklik_c": 33.5,
       "yagis_mm": 0.0, "ruzgar_kmh": 7.6, "durum": "açık"}

[Turn 2] Araç Çağrıları:
   -> convert_unit(value=24.4, from_unit='C', to_unit='F')
   <- {"deger": 75.92, "birim": "F", "kaynak": "24.4 C"}
   -> convert_unit(value=33.5, from_unit='C', to_unit='F')
   <- {"deger": 92.3, "birim": "F", "kaynak": "33.5 C"}

[Turn 3] Nihai Yanıt:
İstanbul'un sıcaklığı 24.4°C (75.92°F), Rotterdam'ın sıcaklığı ise 33.5°C (92.3°F).
Bu durumda Rotterdam İstanbul'dan daha sıcak. Lojistik açısından, yüksek sıcaklıklar
özellikle soğuk zincir ürünleri için risk oluşturabilir.
```

İlk turda iki hava durumu **paralel** çağrılıyor; ikinci turda bu turun çıktısı (`sicaklik_c`) `convert_unit`'e **girdi** oluyor.

### 2) Farklı araçların birlikte kullanımı

**Kullanıcı:** *"Mersin'den Hamburg'a karayolu mesafesi ne kadar? Hamburg'da hava sevkiyata uygun mu?"*

```text
[Turn 1] Araç Çağrıları:
   -> get_route_distance(origin='Mersin', destination='Hamburg')
   <- {"kalkis": "Mersin", "varis": "Hamburg", "mesafe_km": 3420.9,
       "sure_dakika": 2042, "sure_okunabilir": "34 sa 2 dk"}
   -> get_weather(city='Hamburg')
   <- {"sehir": "Hamburg", "ulke": "Almanya", "sicaklik_c": 31.2,
       "yagis_mm": 0.0, "ruzgar_kmh": 8.3, "durum": "açık"}

[Turn 2] Nihai Yanıt:
Mersin'den Hamburg'a karayolu mesafesi yaklaşık 3421 km ve tahmini sürüş süresi
34 saat 2 dakikadır. Hamburg'da hava durumu açık, sıcaklık 31.2°C ve yağış yok.
Bu koşullar sevkiyat için uygundur.
```

### 3) Tek araç — navlun maliyeti

**Kullanıcı:** *"2500 EUR navlun bedeli kaç TL eder?"*

```text
[Turn 1] Araç Çağrıları:
   -> get_exchange_rate(from_currency='EUR', to_currency='TRY', amount=2500)
   <- {"kaynak_para": "EUR", "hedef_para": "TRY", "miktar": 2500,
       "sonuc": 134847, "kur": 53.9388, "tarih": "2026-07-29"}

[Turn 2] Nihai Yanıt:
2500 EUR navlun bedeli yaklaşık 134,847 TL eder.
```

---

## 🏗️ Mimari

```
                    Kullanıcı sorusu
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │  gpt-4o-mini  +  TOOLS (JSON Schema)    │
        │  tool_choice = "auto"                   │
        └──────────────────┬──────────────────────┘
                           │
                  tool_calls var mı?
                  ┌────────┴────────┐
                 Evet              Hayır
                  │                  │
                  ▼                  ▼
        ┌──────────────────┐   Nihai yanıt
        │ Fonksiyonu       │   (döngü biter)
        │ çalıştır         │
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │ Public API       │
        │ Open-Meteo /     │
        │ OSRM /           │
        │ Frankfurter      │
        └────────┬─────────┘
                 ▼
        Sonucu mesaj geçmişine
        `tool` rolüyle ekle
                 │
                 └──────► döngüye dön (max 5 tur)
```

Çok turlu döngü sayesinde bir aracın çıktısı başka bir araca girdi olabilir. Model tek turda birden fazla aracı **paralel** de çağırabilir.

---

## 📁 Proje Yapısı

```
├── tool_calling_odev.ipynb   # Uçtan uca notebook: geliştirme → test → yayınlama
├── app.py                    # Gradio arayüzü + araçlar + tool calling döngüsü
├── requirements.txt          # gradio, openai, requests
└── README.md                 # Bu dosya
```

`tool_calling_odev.ipynb` tek başına çalıştırıldığında araçları test eder, Gradio arayüzünü Colab'da açar, `app.py` / `requirements.txt` / `README.md` dosyalarını üretir ve Space'i oluşturup dosyaları yükleyerek yayına alır.

---

## 🚀 Kurulum

### Yerel çalıştırma

```bash
git clone https://github.com/<kullanici>/lojistik-tool-calling.git
cd lojistik-tool-calling
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
python app.py
```

Arayüz `http://localhost:7860` adresinde açılır.

### Colab / notebook üzerinden

`tool_calling_odev.ipynb` dosyasını Colab'da açın ve Secrets bölümüne şu ikisini ekleyin:

| Secret | Amaç |
|--------|------|
| `OPENAI_API_KEY` | Model çağrıları |
| `HF_TOKEN` | Space'e yayınlama (**write** yetkili olmalı) |

Hücreleri sırayla çalıştırın; son bölüm Space'i otomatik oluşturup dosyaları yükler.

### Hugging Face Spaces

> **Not:** Hugging Face artık Gradio Space'lerin ücretsiz `cpu-basic` üzerinde oluşturulmasına izin vermiyor — Static Space'ler herkese açık, Gradio ve Docker Space'ler için PRO gerekiyor. Ücretsiz kişisel hesaplar ZeroGPU üzerinde 2 adede kadar Gradio Space barındırabiliyor. Bu proje `zero-a10g` donanımıyla yayınlanmıştır (uygulama GPU kullanmaz, yalnızca ücretsiz slot gereksinimi nedeniyle).

```python
from huggingface_hub import create_repo, HfApi

SPACE_ID = "kullanici/lojistik-tool-calling"

create_repo(
    repo_id=SPACE_ID,
    repo_type="space",
    space_sdk="gradio",
    space_hardware="zero-a10g",
)

api = HfApi()
for f in ["app.py", "requirements.txt", "README.md"]:
    api.upload_file(path_or_fileobj=f, path_in_repo=f,
                    repo_id=SPACE_ID, repo_type="space")

api.add_space_secret(repo_id=SPACE_ID, key="OPENAI_API_KEY", value="sk-...")
```

---

## ⚙️ Teknik Detaylar

| Konu | Detay |
|------|-------|
| Model | `gpt-4o-mini` (native function calling) |
| Tool tanımı | OpenAI JSON Schema — `name`, `description`, tipli `parameters` |
| Paralel çağrı | Model tek turda birden fazla aracı çağırabilir |
| Zincirleme çağrı | `MAX_TOOL_TURNS = 5` ile sınırlı çok turlu döngü |
| Hata yönetimi | API hataları `{"hata": "..."}` olarak döner, model kullanıcıya açıklar |
| Zaman aşımı | API çağrısı başına 15 saniye |
| Sıcaklık | `temperature = 0.3` (araç seçiminde tutarlılık için) |
| Gradio uyumu | Sürüm tespiti ile Gradio 5 ve 6 arasındaki API farkları yönetilir |

### Gradio 5 / 6 uyumluluğu

Gradio 6'da `theme` parametresi `Blocks()`'tan `launch()`'a taşındı ve `Chatbot(type=...)` kaldırıldı. Kod her iki sürümde de çalışacak şekilde sürüm tespiti yapar:

```python
GRADIO_MAJOR = int(gr.__version__.split(".")[0])

_chatbot_kwargs = {"label": "Sohbet", "height": 440}
if GRADIO_MAJOR < 6:
    _chatbot_kwargs["type"] = "messages"
```

---

## 🔗 İlgili Çalışmalar

Bu proje, aynı lojistik alanı üzerine kurulu bir çalışma serisinin parçasıdır.

| Kaynak | Link |
|--------|------|
| Fine-tuned model (LoRA) | [`cihatyldz/lojistik-lora-adapter`](https://huggingface.co/cihatyldz/lojistik-lora-adapter) |
| Eğitim veri seti | [`cihatyldz/lojistik-soru-cevap`](https://huggingface.co/datasets/cihatyldz/lojistik-soru-cevap) |
| BPE tokenizer | [`cihatyldz/lojistik-bpe-tokenizer`](https://huggingface.co/cihatyldz/lojistik-bpe-tokenizer) |
| Özel benchmark | [`cihatyldz/lojistik-benchmark`](https://huggingface.co/datasets/cihatyldz/lojistik-benchmark) |

---

## 👤 Yazar

**Cihat Yıldız** — Kıdemli Veri Bilimcisi, Lojistik Sektörü
[Hugging Face](https://huggingface.co/cihatyldz)

## 📄 Lisans

MIT
