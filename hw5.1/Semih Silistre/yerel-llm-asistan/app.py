"""
Hugging Face Space vitrini.

Bu asistan yerel bir modelle (LM Studio / Ollama) çalışır; HF Space'te GPU
üzerinde bir LLM barındırılmadığı için burada canlı sohbet yoktur. Space,
projenin dokümantasyonunu, gerçek oturumdan alınmış örnek konuşmaları ve
kaynak kodu okunabilir biçimde sunar.

Yerel çalıştırma için: README > Kurulum ve Çalıştırma
"""

from __future__ import annotations

import os

import gradio as gr

KOK = os.path.dirname(os.path.abspath(__file__))

KOD_DOSYALARI = [
    ("config.py", "Ayarlar — hepsi ortam değişkeniyle override edilebilir"),
    ("system_prompt.py", "Sistem istemi — araç listesini tools.py'den otomatik üretir"),
    ("tools.py", "9 aracın şeması ve implementasyonu"),
    ("agent.py", "Tool calling döngüsü + sahte araç çağrısı yakalayıcı"),
    ("main.py", "Terminal arayüzü"),
    ("demo_konusmalar.py", "Örnek konuşmaları üreten betik"),
]


def oku(ad: str) -> str:
    yol = os.path.join(KOK, ad)
    try:
        with open(yol, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return f"_{ad} bulunamadı._"


def readme_govdesi() -> str:
    """README'nin YAML başlığını atıp gövdesini döndürür."""
    metin = oku("README.md")
    if metin.startswith("---"):
        parcalar = metin.split("---", 2)
        if len(parcalar) == 3:
            return parcalar[2].strip()
    return metin


GIRIS = """
# 🤖 Yerel Asistan — Genel Amaçlı Tool Calling Asistanı

Tamamen **kendi bilgisayarında** çalışan, internete çıkabilen, hesap yapabilen, kod çalıştırabilen
ve seni hatırlayan genel amaçlı bir asistan. Hiçbir bulut LLM servisi kullanılmaz.

> **Magibu Uygulamalı Yapay Zekâ Mimarisi Eğitimi — Ödev 5.1**

---

### ⚠️ Bu Space'te neden canlı sohbet yok?

Ödevin şartı modelin **yerel olarak** (LM Studio veya Ollama üzerinde) çalışması. HF Space'in
ücretsiz donanımında 8B'lik bir modeli barındırmak mümkün olmadığı için burada canlı demo yerine
**gerçek yerel oturumlardan alınmış çıktılar** sunuluyor. Projeyi kendi makinende çalıştırmak
birkaç komut sürüyor — "Kurulum" sekmesine bak.

---

### Özet

| | |
|---|---|
| **Model** | `qwen3-8b` (Q4_K_M, GGUF) — LM Studio yerel sunucusu |
| **Donanım** | Apple M5 Pro / 24 GB RAM |
| **Araç sayısı** | 9 (hiçbiri API anahtarı istemiyor) |
| **Arayüz** | Terminal (REPL + tek-soru modu) |
| **Ayırt edici tool** | SQLite kalıcı hafıza — asistan seni oturumlar arası hatırlıyor |

### Araçlar

`web_search` · `fetch_url` · `calculator` · `current_datetime` · `get_weather` ·
`currency_convert` · `run_python` · `save_note` · `recall_notes`
"""

KURULUM = """
## 🚀 Yerel Kurulum

### 1. Modeli hazırla (LM Studio)

```bash
lms get qwen/qwen3-8b
lms server start
lms load qwen3-8b --context-length 8192
lms ps          # kontrol
```

**Ollama tercih edersen:**

```bash
ollama pull qwen3:8b && ollama serve
export LOCAL_LLM_BASE_URL=http://localhost:11434/v1
export LOCAL_LLM_MODEL=qwen3:8b
```

### 2. Bağımlılıklar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Çalıştır

```bash
python main.py                    # sohbet modu
python main.py --quiet            # araç çağrılarını gizle
python main.py "dolar kaç TL?"    # tek soru sor, çık
```

Sohbet içi komutlar: `/araclar` · `/sifirla` · `/cikis`

### Yapılandırma

Tüm ayarlar ortam değişkeniyle değiştirilebilir:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LOCAL_LLM_BASE_URL` | `http://localhost:1234/v1` | LM Studio / Ollama endpoint'i |
| `LOCAL_LLM_MODEL` | `qwen3-8b` | Yüklü model kimliği |
| `LOCAL_LLM_TEMPERATURE` | `0.3` | Araç argümanı uydurulmasın diye düşük |
| `LOCAL_LLM_MAX_TOKENS` | `4096` | Düşünme bloğu + cevap birlikte sığsın |
| `ENABLE_THINKING` | `1` | `0` yaparsa isteme `/no_think` eklenir |
| `MAX_TOOL_ROUNDS` | `6` | Bir soru için azami ardışık araç turu |
| `DEFAULT_CITY` | `İstanbul` | Şehir belirtilmezse hava durumu için |
"""


with gr.Blocks(title="Yerel Asistan — Ödev 5.1") as demo:
    gr.Markdown(GIRIS)

    with gr.Tabs():
        with gr.Tab("💬 Örnek Konuşmalar"):
            gr.Markdown(
                "Aşağıdaki çıktıların tamamı `demo_konusmalar.py` ile **gerçek yerel oturumdan** "
                "alındı; elle yazılmadı."
            )
            gr.Markdown(oku("ornek_konusmalar.md"))

        with gr.Tab("📖 Dokümantasyon"):
            gr.Markdown(readme_govdesi())

        with gr.Tab("🚀 Kurulum"):
            gr.Markdown(KURULUM)

        with gr.Tab("💻 Kaynak Kod"):
            for ad, aciklama in KOD_DOSYALARI:
                with gr.Accordion(f"{ad} — {aciklama}", open=False):
                    gr.Code(value=oku(ad), language="python", label=ad)


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
