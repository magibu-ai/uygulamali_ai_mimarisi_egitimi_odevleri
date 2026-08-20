# Ödev 5.1 — Teslim

## 🔗 Linkler

**GitHub (asıl teslim):** https://github.com/unkownpr/yerel-llm-asistan

**Hugging Face Space (vitrin):** https://huggingface.co/spaces/ssilistre/yerel-llm-asistan
Doğrudan sayfa: https://ssilistre-yerel-llm-asistan.static.hf.space

---

## 📝 Teslim Notu (paylaşım için kısa metin)

> **Ödev 5.1 — Yerel LLM Asistanı**
> **Repo:** https://github.com/unkownpr/yerel-llm-asistan
> **Canlı vitrin:** https://huggingface.co/spaces/ssilistre/yerel-llm-asistan
>
> **Senaryo:** Genel amaçlı asistan. Dar bir dikeye sıkışmak yerine günlük kullanımda gerçekten ihtiyaç duyulan yetenekleri tek terminal arayüzünde topladım. Asistanı ayıran şey **kalıcı hafıza**: çoğu asistan oturum kapanınca her şeyi unutur, bu asistan kullanıcıyla ilgili bilgileri SQLite'a yazıp sonraki oturumda geri çağırıyor (`save_note` / `recall_notes`).
>
> **Model:** `qwen3-8b` (Q4_K_M, GGUF), LM Studio yerel sunucusunda — Apple M5 Pro / 24 GB. Tool calling'de 8B seviyesindeki en kararlı seçenek olduğu ve Türkçe ürettiği için seçildi.
>
> **9 araç, hiçbiri API anahtarı istemiyor:** `web_search` (DuckDuckGo), `fetch_url`, `calculator` (AST tabanlı, `eval` yok), `current_datetime` (hedef tarihe kalan günü de hesaplıyor), `get_weather` (Open-Meteo), `currency_convert` (Frankfurter/ECB), `run_python` (ayrı süreç + zaman aşımı + yıkıcı kod filtresi), `save_note`, `recall_notes`. Repoyu klonlayan kişi hiçbir `.env` doldurmadan çalıştırabiliyor.
>
> **System prompt tarafında yaptıklarım:** Araç listesi elle yazılmıyor, `tools.py`'deki kayıttan üretiliyor — yeni araç eklendiğinde istem otomatik güncelleniyor, ikisi asla ayrışmıyor. Her araç için "ne zaman çağır" kuralı, arama sorgusu için kötü/iyi örnek, ve "gereksiz çağrı yok" maddesi var.
>
> **Yol boyunca ölçtüğüm 3 şey (README'de tablolarıyla duruyor):**
> 1. LM Studio'da `chat_template_kwargs={"enable_thinking": False}` **çalışmıyor**. Qwen3 thinking'ini kapatmanın yolu isteme `/no_think` eklemek: 1247 reasoning token → 0.
> 2. Ama thinking kapalıyken model çok adımlı soruda araca eksik argüman göndermeye başladı (`currency_convert`'e `amount` hiç gitmedi, sonuç yanlış çıktı). Karşılaştırma tablosunu README'ye koydum; varsayılanı **açık** bıraktım.
> 3. Model araç çağrısını gerçekten yapmak yerine cevap metnine `calculator("...")` yazıp sonucu **uyduruyordu** (19.475,94 — doğrusu 19.567,66). `agent.py`'ye bu kalıbı yakalayan bir kontrol + soru başına tek seferlik düzeltme turu ekledim; artık aracı gerçekten çağırıp doğru sonucu veriyor.
>
> **Örnek konuşmalar** elle yazılmadı — `demo_konusmalar.py` gerçek oturumu koşup çıktıyı Markdown'a döküyor, 9 senaryonun tamamı Space'te "Örnek Konuşmalar" sekmesinde.
>
> README'de "Kalan sınırlar" diye bir bölüm de var: araç seçimindeki tutarsızlık, araç adlarının cevaba sızması ve çelişkili web kaynaklarını ayıklayamama. 8B'nin sınırları, gizlemek yerine yazdım.

---

## ⚠️ Not: Neden hem GitHub hem Hugging Face, neden canlı demo yok?

- **Asıl teslim GitHub reposu** (ödev metninin istediği biçim). Hugging Face Space ise projenin tarayıcıdan gezilebilir vitrini: dokümantasyon, örnek konuşmalar ve kaynak kodun tamamı sekmeli tek sayfada.
- **Canlı sohbet yok, çünkü ödevin şartı modelin yerel çalışması.** HF'nin ücretsiz donanımında 8B model barındırılamıyor; ayrıca Gradio Space açmak artık PRO abonelik istiyor (`402 Payment Required`). Bu yüzden **Static Space** kullanıldı: `build_static.py`, README + örnek konuşmalar + kaynak kodun tamamını tek bir bağımsız `index.html`'e gömüyor. Sayfa sekmeli, JS bağımlılığı yok.
- **README ikiye ayrılmadı ama başlığı ayrıldı.** HF Space ayarlarını README'nin YAML başlığından okur; GitHub aynı başlığı sayfanın tepesinde metadata tablosu olarak gösteriyordu. Çözüm: repodaki README YAML'sız, başlık `hf_header.yaml`'da; `push_to_hf.py` yüklerken ikisini birleştiriyor.
- **`app.py` repoda duruyor** — yerelde `python app.py` ile Gradio vitrini de açılabiliyor, ama Space static olarak yayında.

---

## 📂 Dosyalar

| Dosya | Ne yapar |
|---|---|
| `config.py` | Tüm ayarlar, ortam değişkeniyle override edilebilir |
| `system_prompt.py` | Sistem istemi; araç listesini `tools.py`'den üretir |
| `tools.py` | 9 aracın şeması + implementasyonu (`@tool` dekoratörü) |
| `agent.py` | Tool calling döngüsü + sahte araç çağrısı yakalayıcı |
| `main.py` | Terminal arayüzü (REPL + tek-soru modu) |
| `demo_konusmalar.py` | Örnek konuşmaları gerçek oturumdan üretir |
| `build_static.py` | HF Static Space için `index.html` derler |
| `push_to_hf.py` | Space'e yükler; README'ye HF YAML başlığını ekleyerek |
| `hf_header.yaml` | HF Space ayarları — GitHub README'sini kirletmesin diye ayrı |
| `app.py` | Yerel Gradio vitrini (opsiyonel) |
| `ornek_konusmalar.md` | Üretilmiş örnek oturum çıktıları |
| `README.md` | Proje dokümantasyonu (YAML başlığı ayrı dosyada) |

## 🚀 Yerelde çalıştırma

```bash
lms server start && lms load qwen3-8b --context-length 8192
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
