---
title: Cinema AI
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
---

# 🎬 Cinema-AI — Tool-Calling Film Asistanı + Custom Chat Template

[![Hugging Face Space](https://img.shields.io/badge/🤗%20Hugging%20Face-Canlı%20Demo-yellow)](https://huggingface.co/spaces/berkcangumusisik/cinema-ai)
[![GitHub](https://img.shields.io/badge/GitHub-Kaynak%20Kod-181717?logo=github)](https://github.com/berkcangumusisik/cinema-ai)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Gradio](https://img.shields.io/badge/Gradio-5.x-FF7C00)
![Tests](https://img.shields.io/badge/tests-14%20passed-brightgreen)

Bu depo iki ana bileşeni **tek proje içinde** birleştirir:

1. **Custom Chat Template (Jinja2):** `system` / `user` / `assistant` rollerini
   ve tool-calling akışını doğru sarmalayan, ChatML tarzı özel şablon →
   [`chat_template.jinja`](chat_template.jinja)
2. **Tool-Calling Destekli Asistan:** Dil modelinin gerçek bir SQLite
   veritabanına tool-call ile erişip **hem okuduğu hem yazdığı**, halüsinasyon
   engelli bir film öneri & izleme listesi asistanı.

> ### 🔴 Canlı Demo → **[huggingface.co/spaces/berkcangumusisik/cinema-ai](https://huggingface.co/spaces/berkcangumusisik/cinema-ai)**
> API anahtarı olmadan da çalışır (yerel mock model); Groq anahtarı eklenince gerçek LLM devreye girer.

---

## 📌 Senaryo Özeti

Kullanıcı doğal dille film arar ("8.5 üstü bir bilim kurgu öner"), beğendiğini
izleme listesine ekler ve listesini sorgular. Model bu isteklerin hiçbirini
kendi hafızasından **uydurmaz**; her yanıt, veritabanından tool-call ile çekilen
gerçek satırlara dayanır.

**Örnek akış:**

```
👤 "Bana 8.7 üstü bir bilim kurgu filmi öner"
   → model  search_movies(genre="Bilim Kurgu", min_rating=8.7)  çağırır
   → DB gerçek 3 film döndürür
🎬 "Başlangıç (2010, 8.8), Yıldızlararası (2014, 8.7)... öneriyorum"

👤 "Başlangıç'ı listeme ekle"
   → model  add_to_watchlist(movie_id=4)  çağırır  → DB'ye YAZAR
🎬 "Eklendi ✅"
```

---

## 🧠 Kullanılan Model & Mimari

- **Model (provider-agnostic):** Kod, OpenAI-uyumlu herhangi bir endpoint ile
  çalışır (`base_url` + `model` + `api_key`). Varsayılan sağlayıcı **Groq**
  (ücretsiz) ve model **`llama-3.3-70b-versatile`** — native tool-calling destekli
  açık kaynak bir Llama modeli. `.env` ile OpenAI / HF Router / yerel vLLM-TGI'ye
  saniyeler içinde geçilebilir.
- **Tool-calling döngüsü:** Model → tool çağrısı → gerçek Python fonksiyonu
  çalışır → sonuç `role:"tool"` olarak geri beslenir → final yanıta kadar tekrar.

```
┌──────────┐   mesaj + tool şemaları   ┌───────────┐
│  Kullanıcı│ ────────────────────────▶ │    LLM    │
└──────────┘                            └─────┬─────┘
      ▲                                       │ tool_calls
      │ final yanıt (yalnız gerçek veriye     │
      │             dayalı)                   ▼
      │                              ┌─────────────────┐
      │                              │  TOOL_REGISTRY  │
      │                              │ search_movies   │
      │           tool sonucu        │ add_to_watchlist│
      └──────────────────────────────┤ get_watchlist   │
                                     └────────┬────────┘
                                              ▼
                                       ┌─────────────┐
                                       │   SQLite    │
                                       │  cinema.db  │
                                       └─────────────┘
```

### Proje yapısı

```
cinema-ai/
├── chat_template.jinja      # Özel ChatML + tool-calling şablonu
├── app.py                   # Gradio arayüzü (HF Space giriş noktası)
├── src/
│   ├── config.py            # ortam değişkenleri (provider-agnostic)
│   ├── database.py          # SQLite şema + otomatik seed
│   ├── tools.py             # tool fonksiyonları (gerçek DB okuma/yazma)
│   ├── schemas.py           # tool JSON şemaları + fonksiyon registry'si
│   ├── llm.py               # OpenAI-uyumlu client + tool-calling döngüsü
│   └── agent.py             # orkestrasyon + anti-halüsinasyon system prompt
├── data/seed_movies.json    # ~40 film seed verisi (TR + dünya sineması)
├── scripts/
│   ├── render_template.py   # şablonu örnek sohbetle render eder
│   └── demo_cli.py          # uçtan uca terminal demosu (--offline destekli)
└── tests/                   # tool okuma/yazma + şablon render testleri
```

### Tool'lar

| Fonksiyon | Tür | Açıklama |
|-----------|-----|----------|
| `search_movies(query, genre, min_rating, year)` | 📖 Okuma | Katalogda arama; eşleşme yoksa boş liste |
| `get_movie_details(movie_id)` | 📖 Okuma | Tek filmin detayları |
| `add_to_watchlist(movie_id, user)` | ✍️ **Yazma** | Filmi izleme listesine ekler (önce varlığını doğrular) |
| `get_watchlist(user)` | 📖 Okuma | Kullanıcının izleme listesi |

---

## 🚫 Halüsinasyon Engelleme Yaklaşımı

1. **Güçlü system prompt** (`src/agent.py`): "Yalnızca araçlardan dönen gerçek
   veriye dayan; film adı/puan/yönetmen UYDURMA; bulunamazsa dürüstçe söyle."
2. **Tool katmanı gerçeği zorlar** (`src/tools.py`): Fonksiyonlar yalnız DB'de
   var olan satırları döndürür. `add_to_watchlist`, yazmadan önce `movie_id`'nin
   gerçekten var olduğunu doğrular; yoksa `{"error": "not_found"}` döner.
3. **Düşük sıcaklık** (`temperature=0.2`) ile kararlı, uydurmaya kapalı yanıtlar.
4. Model olmayan bir film sorulduğunda araç boş liste döndürür ve asistan
   *"Veritabanımızda böyle bir film bulamadım"* der — var gibi davranmaz.

---

## 🧪 API'siz Geliştirme & Test (Mock Mod)

Kodu yazarken/geliştirirken **API anahtarına ihtiyacın yok.** `LLM_API_KEY`
boşsa proje otomatik olarak yerel, kural tabanlı bir **MOCK model** kullanır
([`src/mock_llm.py`](src/mock_llm.py)). Mock, gerçek OpenAI istemcisinin yanıt
şeklini birebir taklit eder; böylece **agent + tool-calling döngüsü + veritabanı
akışı hiç değişmeden**, tamamen çevrimdışı çalışır ve test edilir.

```bash
python scripts/demo_cli.py --offline   # her şeyi API'siz çalıştırır
pytest -q                              # 14 test, tamamı API'siz geçer
python app.py                          # Gradio arayüzü de mock ile açılır
```

Anahtar eklediğinde tek satır değişmeden gerçek Groq modeline geçersin
(`LLM_BACKEND=auto`). İstersen `LLM_BACKEND=mock` ile anahtar varken bile mock'u
zorlayabilirsin.

| Backend | Ne zaman | Nasıl |
|---------|----------|-------|
| `auto` (varsayılan) | Anahtar varsa gerçek model, yoksa mock | `.env`'de bırak |
| `mock` | Her zaman API'siz test | `LLM_BACKEND=mock` |
| `openai` | Her zaman gerçek model | `LLM_BACKEND=openai` + anahtar |

---

## 💻 Yerelde Çalıştırma

```bash
# 1) Bağımlılıklar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Ortam değişkenleri (opsiyonel — anahtarsız da çalışır, bkz. Mock Mod)
cp .env.example .env
# .env içine Groq API anahtarınızı yazın (ücretsiz: https://console.groq.com/keys)

# 3) Chat template'in çalıştığını gör (API'siz)
python scripts/render_template.py

# 4) Uçtan uca terminal demosu
python scripts/demo_cli.py            # anahtar varsa gerçek model, yoksa mock
python scripts/demo_cli.py --offline  # API'siz mock ile tool + DB akışı

# 5) Gradio arayüzü
python app.py                         # http://localhost:7860

# 6) Testler (API'siz)
pytest -q
```

---

## 🖥️ Örnek Kullanıcı Girdisi & Tetiklenen Tool-Call Çıktısı

Aşağıdaki çıktı `python scripts/demo_cli.py --offline` ile üretilmiştir
(tool'lar gerçek SQLite verisini kullanır):

```text
👤 KULLANICI: Bana 8.7 üstü bir bilim kurgu filmi öner.
🛠  ARKA PLAN (tetiklenen tool-call'lar):
   [1] 🔧 TOOL-CALL: search_movies({"genre": "Bilim Kurgu", "min_rating": 8.7})
       ↩︎  SONUÇ: {"count": 3, "movies": [{"id": 4, "title": "Başlangıç", ...}]}
🎬 CINEMA-AI: Sana 'Başlangıç' (2010, 8.8) filmini öneririm.
----------------------------------------------------------------------
👤 KULLANICI: 'Başlangıç' filmini izleme listeme ekle.
🛠  ARKA PLAN (tetiklenen tool-call'lar):
   [1] 🔧 TOOL-CALL: add_to_watchlist({"movie_id": 4, "user": "demo"})
       ↩︎  SONUÇ: {"status": "added", "movie": {"id": 4, "title": "Başlangıç", ...}}
🎬 CINEMA-AI: 'Başlangıç' izleme listene eklendi.
----------------------------------------------------------------------
👤 KULLANICI: 'Uzaylı Kediler 7' filmini bul.
🛠  ARKA PLAN (tetiklenen tool-call'lar):
   [1] 🔧 TOOL-CALL: search_movies({"query": "Uzaylı Kediler 7"})
       ↩︎  SONUÇ: {"count": 0, "movies": []}
🎬 CINEMA-AI: Bu tarife uyan bir şey çıkmadı. (uydurma yapılmaz)
```

> 📸 **Belgeleme için:** Yukarıdaki komutu kendi makinenizde çalıştırıp
> terminal çıktısının ekran görüntüsünü bu bölüme ekleyebilirsiniz.

---

## 📝 Chat Template Detayı

`chat_template.jinja` ChatML tarzı, `<|im_start|>{rol} ... <|im_end|>` sınırlayıcıları
kullanır ve şunları destekler:

- **Roller:** `system`, `user`, `assistant`, `tool`.
- **Tool tanımları:** `tools` değişkeni verilirse system bloğuna JSON şemalar eklenir.
- **Tool çağrısı:** asistan mesajındaki `tool_calls`, `<tool_call>{json}</tool_call>`
  bloğu olarak yazılır.
- **Tool sonucu:** `tool` rolü `<tool_response>{json}</tool_response>` ile sarılır.
- `add_generation_prompt=True` → sonda asistan turu başlatılır.
- Sıkı whitespace kontrolü ve `tojson`'un Markup-escape sorununa karşı ayrık çıktı blokları.

`python scripts/render_template.py` bu şablonu örnek bir sohbet (system → user →
assistant tool-call → tool response → assistant final) ile render eder.

---

## 🚀 Hugging Face Space Dağıtımı

Proje canlıda: **[huggingface.co/spaces/berkcangumusisik/cinema-ai](https://huggingface.co/spaces/berkcangumusisik/cinema-ai)**

Space, README frontmatter'ından (`sdk: gradio`, `app_file: app.py`) otomatik
yapılandırılır. Kendi kopyanı yayınlamak için:

```bash
# 1) HF'te yeni bir Gradio Space aç (huggingface.co/new-space)
# 2) Bu repoyu Space'e remote olarak ekle ve gönder:
git remote add space https://huggingface.co/spaces/<KULLANICI>/cinema-ai
git push space main
# Parola sorulunca HF "Write" token'ını gir: https://huggingface.co/settings/tokens
```

- Space **secret olmadan** açılır ve mock modda çalışır.
- Gerçek LLM için: Space → **Settings → Variables and secrets** →
  `LLM_API_KEY = <Groq anahtarın>` ekle; arayüzdeki rozet otomatik güncellenir.

---

## 🧾 Lisans

Eğitim amaçlı örnek projedir. Film verileri statik seed'dir (harici API bağımlılığı yok).
