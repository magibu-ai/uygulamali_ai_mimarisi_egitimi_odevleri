"""
Hugging Face Static Space için `index.html` üretir.

HF'de Gradio Space barındırmak PRO abonelik istiyor; Static Space ise ücretsiz.
Bu betik README, örnek konuşmalar ve kaynak kodu tek bir bağımsız HTML sayfasına
gömer — çalışma zamanında hiçbir dosya çekilmez, JS bağımlılığı yoktur.

Kullanım:
    python build_static.py
"""

from __future__ import annotations

import html
import os

import markdown

KOK = os.path.dirname(os.path.abspath(__file__))

KOD_DOSYALARI = [
    ("config.py", "Ayarlar — hepsi ortam değişkeniyle override edilebilir"),
    ("system_prompt.py", "Sistem istemi — araç listesini tools.py'den otomatik üretir"),
    ("tools.py", "9 aracın şeması ve implementasyonu"),
    ("agent.py", "Tool calling döngüsü + sahte araç çağrısı yakalayıcı"),
    ("main.py", "Terminal arayüzü"),
    ("demo_konusmalar.py", "Örnek konuşmaları üreten betik"),
    ("app.py", "Yerel Gradio vitrini (Space'te static HTML kullanılıyor)"),
]

CSS = """
:root {
  --bg: #0d1117; --panel: #161b22; --border: #30363d;
  --fg: #e6edf3; --muted: #8b949e; --accent: #7c8cff; --accent2: #a371f7;
  --code-bg: #0b0f14;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.wrap { max-width: 960px; margin: 0 auto; padding: 32px 20px 80px; }
header {
  background: linear-gradient(135deg, #1c2333 0%, #251b3a 100%);
  border-bottom: 1px solid var(--border); padding: 44px 20px 36px;
}
header .inner { max-width: 960px; margin: 0 auto; }
header h1 { margin: 0 0 10px; font-size: 30px; line-height: 1.25; }
header p { margin: 0; color: var(--muted); max-width: 720px; }
.badges { margin-top: 18px; display: flex; flex-wrap: wrap; gap: 8px; }
.badge {
  background: var(--panel); border: 1px solid var(--border); color: var(--fg);
  border-radius: 999px; padding: 4px 12px; font-size: 13px;
}
.badge.accent { border-color: var(--accent); color: var(--accent); }
.note {
  background: #1f1a08; border: 1px solid #6b5314; border-left: 4px solid #d29922;
  border-radius: 8px; padding: 14px 18px; margin: 24px 0;
}
.note strong { color: #e3b341; }
nav.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 28px 0 22px; }
nav.tabs button {
  background: var(--panel); border: 1px solid var(--border); color: var(--muted);
  padding: 9px 16px; border-radius: 8px; cursor: pointer; font-size: 14px;
  font-family: inherit; transition: .15s;
}
nav.tabs button:hover { color: var(--fg); border-color: var(--accent); }
nav.tabs button.active { background: var(--accent); border-color: var(--accent); color: #0d1117; font-weight: 600; }
section.tab { display: none; }
section.tab.active { display: block; }
h2 { margin-top: 34px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
h3 { margin-top: 26px; color: var(--accent); }
a { color: var(--accent); }
table { border-collapse: collapse; width: 100%; margin: 18px 0; font-size: 14px; display: block; overflow-x: auto; }
th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
th { background: var(--panel); }
code {
  background: var(--panel); padding: 2px 6px; border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .88em;
}
pre {
  background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; overflow-x: auto;
}
pre code { background: none; padding: 0; font-size: 13px; line-height: 1.5; }
blockquote {
  border-left: 3px solid var(--accent2); margin: 18px 0; padding: 2px 0 2px 16px;
  color: var(--muted);
}
details {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  margin: 10px 0; padding: 0;
}
details summary {
  cursor: pointer; padding: 12px 16px; font-weight: 600; list-style: none;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "▸ "; color: var(--accent); }
details[open] summary::before { content: "▾ "; }
details summary span { color: var(--muted); font-weight: 400; font-size: 13px; }
details pre { margin: 0 12px 12px; max-height: 560px; overflow: auto; }
footer { margin-top: 60px; padding-top: 20px; border-top: 1px solid var(--border); color: var(--muted); font-size: 14px; }
hr { border: none; border-top: 1px solid var(--border); margin: 30px 0; }
"""

JS = """
document.querySelectorAll('nav.tabs button').forEach(function (btn) {
  btn.addEventListener('click', function () {
    document.querySelectorAll('nav.tabs button').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('section.tab').forEach(function (s) { s.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});
"""

GIRIS_HTML = """
<div class="note">
  <strong>⚠️ Bu Space'te neden canlı sohbet yok?</strong><br>
  Ödevin şartı modelin <b>yerel olarak</b> (LM Studio veya Ollama üzerinde) çalışması.
  HF Space'in ücretsiz donanımında 8B'lik bir modeli barındırmak mümkün değil, ayrıca
  Gradio Space barındırmak PRO abonelik gerektiriyor. Bu yüzden burada canlı demo yerine
  <b>gerçek yerel oturumlardan alınmış çıktılar</b> ve kaynak kodun tamamı sunuluyor.
  Projeyi kendi makinende çalıştırmak birkaç komut sürüyor — <b>Kurulum</b> sekmesine bak.
</div>

<h2>Özet</h2>
<table>
<tr><td><b>Model</b></td><td><code>qwen3-8b</code> (Q4_K_M, GGUF) — LM Studio yerel sunucusu</td></tr>
<tr><td><b>Donanım</b></td><td>Apple M5 Pro / 24 GB RAM</td></tr>
<tr><td><b>Araç sayısı</b></td><td>9 — hiçbiri API anahtarı istemiyor</td></tr>
<tr><td><b>Arayüz</b></td><td>Terminal (REPL + tek-soru modu)</td></tr>
<tr><td><b>Ayırt edici tool</b></td><td>SQLite kalıcı hafıza — asistan seni oturumlar arası hatırlıyor</td></tr>
</table>

<h2>Araçlar</h2>
<p>
<code>web_search</code> · <code>fetch_url</code> · <code>calculator</code> ·
<code>current_datetime</code> · <code>get_weather</code> · <code>currency_convert</code> ·
<code>run_python</code> · <code>save_note</code> · <code>recall_notes</code>
</p>

<h2>Neden genel amaçlı?</h2>
<p>
Dar bir dikeye (hukuk, sağlık, finans) sıkışmak yerine günlük kullanımda gerçekten ihtiyaç
duyulan yetenekler tek bir terminal arayüzünde toplandı. Asistanı diğerlerinden ayıran şey
<b>kalıcı hafıza</b>: çoğu asistan oturum kapanınca her şeyi unutur, buradaki asistan
kullanıcıyla ilgili bilgileri SQLite'a yazar ve sonraki oturumda geri çağırır.
</p>
"""

KURULUM_MD = """
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

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LOCAL_LLM_BASE_URL` | `http://localhost:1234/v1` | LM Studio / Ollama endpoint'i |
| `LOCAL_LLM_MODEL` | `qwen3-8b` | Yüklü model kimliği |
| `LOCAL_LLM_TEMPERATURE` | `0.3` | Araç argümanı uydurulmasın diye düşük |
| `LOCAL_LLM_MAX_TOKENS` | `4096` | Düşünme bloğu + cevap birlikte sığsın |
| `ENABLE_THINKING` | `1` | `0` yaparsa isteme `/no_think` eklenir |
| `MAX_TOOL_ROUNDS` | `6` | Bir soru için azami ardışık araç turu |
| `MAX_HISTORY_MESSAGES` | `24` | Bağlamda tutulan son mesaj sayısı |
| `DEFAULT_CITY` | `İstanbul` | Şehir belirtilmezse hava durumu için |
"""


def oku(ad: str) -> str:
    try:
        with open(os.path.join(KOK, ad), encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return f"_{ad} bulunamadı._"


def md2html(metin: str) -> str:
    return markdown.markdown(metin, extensions=["fenced_code", "tables", "nl2br"])


def readme_govdesi() -> str:
    """README'nin HF YAML başlığını atar."""
    metin = oku("README.md")
    if metin.startswith("---"):
        parcalar = metin.split("---", 2)
        if len(parcalar) == 3:
            return parcalar[2].strip()
    return metin


def main() -> None:
    kod_bloklari = []
    for ad, aciklama in KOD_DOSYALARI:
        icerik = html.escape(oku(ad))
        kod_bloklari.append(
            f"<details><summary>{ad} <span>— {aciklama}</span></summary>"
            f"<pre><code>{icerik}</code></pre></details>"
        )

    sayfa = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yerel Asistan — Genel Amaçlı Tool Calling Asistanı</title>
<style>{CSS}</style>
</head>
<body>
<header><div class="inner">
  <h1>🤖 Yerel Asistan — Genel Amaçlı Tool Calling Asistanı</h1>
  <p>Tamamen kendi bilgisayarında çalışan, internete çıkabilen, hesap yapabilen,
     kod çalıştırabilen ve seni hatırlayan genel amaçlı bir asistan.
     Hiçbir bulut LLM servisi kullanılmaz.</p>
  <div class="badges">
    <span class="badge accent">Magibu — Ödev 5.1</span>
    <span class="badge">qwen3-8b</span>
    <span class="badge">LM Studio / Ollama</span>
    <span class="badge">9 araç</span>
    <span class="badge">API anahtarı gerekmez</span>
  </div>
</div></header>

<div class="wrap">
  <nav class="tabs">
    <button class="active" data-tab="t-giris">🏠 Genel Bakış</button>
    <button data-tab="t-ornek">💬 Örnek Konuşmalar</button>
    <button data-tab="t-dok">📖 Dokümantasyon</button>
    <button data-tab="t-kurulum">🚀 Kurulum</button>
    <button data-tab="t-kod">💻 Kaynak Kod</button>
  </nav>

  <section class="tab active" id="t-giris">{GIRIS_HTML}</section>

  <section class="tab" id="t-ornek">
    <p>Aşağıdaki çıktıların tamamı <code>demo_konusmalar.py</code> ile
       <b>gerçek yerel oturumdan</b> alındı; elle yazılmadı.</p>
    {md2html(oku("ornek_konusmalar.md"))}
  </section>

  <section class="tab" id="t-dok">{md2html(readme_govdesi())}</section>

  <section class="tab" id="t-kurulum">{md2html(KURULUM_MD)}</section>

  <section class="tab" id="t-kod">
    <p>Projenin tamamı 7 dosya. Başlıklara tıklayarak açabilirsin.</p>
    {"".join(kod_bloklari)}
  </section>

  <footer>
    Magibu Uygulamalı Yapay Zekâ Mimarisi Eğitimi — Ödev 5.1 ·
    Model yerel çalışır, bu sayfa yalnızca vitrindir.
  </footer>
</div>

<script>{JS}</script>
</body>
</html>
"""

    hedef = os.path.join(KOK, "index.html")
    with open(hedef, "w", encoding="utf-8") as fh:
        fh.write(sayfa)
    print(f"✅ Yazıldı: {hedef} ({len(sayfa):,} bayt)")


if __name__ == "__main__":
    main()
