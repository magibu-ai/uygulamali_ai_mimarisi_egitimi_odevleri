---
title: Tool Calling Saat Dilimi Farki
emoji: 🕐
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
---

# 🕐 Tool Calling Demo — Saat Dilimi Farkı

Bir LLM'in kullanıcı sorusuna göre **doğru fonksiyonları otomatik çağırdığı**
(Tool / Function Calling), ücretsiz ve anahtarsız **timeapi.io** API'sinden
gerçek veri çeken ve **çağrılan araçları arayüzde açıkça gösteren** bir
Gradio uygulaması.

## Ne yapıyor?

Model iki araca erişebilir:

| Araç | Görevi |
|------|--------|
| `get_current_time(timezone)` | Belirtilen IANA zaman diliminde (örn. `Europe/Istanbul`) o anki yerel saati ve UTC farkını döndürür. |
| `time_difference(timezone1, timezone2)` | İki zaman dilimi arasındaki saat farkını hesaplar. |

Kullanıcı şehir adı yazsa bile (ör. "New York", "Tokyo") model bunu doğru IANA
zaman dilimi kimliğine çevirir, gerekli araçları sırayla çağırır ve API'den
gelen veriyle nihai yanıtı üretir. Tüm araç çağrı adımları sağdaki
**"Tool Trace"** panelinde gösterilir.

> **Sağlamlık:** timeapi.io'ya ulaşılamazsa uygulama, Python'un yerleşik
> `zoneinfo` (IANA veritabanı) kütüphanesine otomatik düşer; böylece demo her
> koşulda çalışmaya devam eder.

### Örnek çalışma akışı

```text
Kullanıcı: "New York ile Tokyo arasında kaç saat fark var, şu an oralarda saat kaç?"

[Turn 1] Araç Çağrıları:
   -> get_current_time(timezone='America/New_York')
   <- {'timezone': 'America/New_York', 'local_time': '2026-07-30 08:30:00', 'utc_offset_hours': -4.0}
   -> get_current_time(timezone='Asia/Tokyo')
   <- {'timezone': 'Asia/Tokyo', 'local_time': '2026-07-30 21:30:00', 'utc_offset_hours': 9.0}

[Turn 2] Araç Çağrıları:
   -> time_difference(timezone1='America/New_York', timezone2='Asia/Tokyo')
   <- {'difference_hours': 13.0, 'note': "Asia/Tokyo, America/New_York'dan 13.0 saat ileridedir."}

[Turn 3] Nihai Yanıt:
Tokyo, New York'tan 13 saat ileride. Şu an New York'ta 08:30, Tokyo'da 21:30.
```

## Kurulum ve Yayınlama (Hugging Face Spaces)

1. **Yeni bir Space oluşturun** → SDK olarak **Gradio** seçin.
2. Bu depodaki `app.py`, `requirements.txt` ve `README.md` dosyalarını yükleyin
   (README'nin en üstündeki YAML bloğu Space'in ayarlarını belirler).
3. **Settings → Variables and secrets** bölümünden şunları ekleyin:
   - **`HF_TOKEN`** *(Secret, zorunlu)* — [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
     adresinden alacağınız, "Make calls to Inference Providers" izinli bir token.
   - **`MODEL_ID`** *(Variable, opsiyonel)* — Varsayılan: `openai/gpt-oss-120b`.
     Daha hızlı/ucuz alternatif: `openai/gpt-oss-20b`.
     Diğer seçenekler: `Qwen/Qwen2.5-72B-Instruct`, `meta-llama/Llama-3.3-70B-Instruct`.
   - **`HF_PROVIDER`** *(Variable, opsiyonel)* — Varsayılan `auto` (uygun ilk
     sağlayıcıyı otomatik seçer). İsterseniz `hf-inference`, `together`, `novita` vb.
4. Space otomatik derlenip yayına alınır.

> Seçtiğiniz modelin **tool calling** desteklediğinden ve serverless Inference
> üzerinde sunulduğundan emin olun. Kontrol için: `hf models ls --warm`.

## Yerel çalıştırma

```bash
pip install -r requirements.txt
export HF_TOKEN="hf_xxx"          # kendi token'ınız
python app.py                     # http://127.0.0.1:7860
```

## Mimari

```
Kullanıcı sorusu
      │
      ▼
 ┌──────────────┐   tools=[get_current_time, time_difference]
 │     LLM      │ ─────────────────────────────────────────► tool_calls?
 └──────────────┘                                              │
      ▲                                                        │ evet
      │ tool sonuçları (JSON)                                  ▼
      │                                          ┌──────────────────────────┐
      └──────────────────────────────────────────│ timeapi.io  (yedek: zoneinfo) │
                                                  └──────────────────────────┘
      │ hayır → nihai yanıt
      ▼
 Arayüz: sohbet + araç çağrı adımları (trace)
```

`run_agent()` fonksiyonu, model araç çağırmayı bırakana kadar (en fazla
`MAX_TURNS` tur) döngü kurar; her turda çağrıları yürütür, sonuçları modele
geri besler ve tüm adımları kaydeder.

## Dosyalar

- `app.py` — Gradio arayüzü, araç tanımları (JSON şeması), araç uygulamaları ve agent döngüsü.
- `requirements.txt` — Bağımlılıklar.
- `README.md` — Bu dosya (+ HF Spaces yapılandırması).

## Veri kaynağı

[timeapi.io](https://timeapi.io/) — ücretsiz, API anahtarı gerektirmeyen zaman/saat dilimi servisi.
