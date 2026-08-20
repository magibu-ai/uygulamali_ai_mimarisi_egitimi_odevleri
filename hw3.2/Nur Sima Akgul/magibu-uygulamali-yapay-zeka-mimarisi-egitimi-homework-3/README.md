# 3. Hafta Ödevleri — Chat Template & Tool-Calling Asistanı

Bu depo, eğitimin 3. haftasındaki iki ödevi içerir. Her ödev kendi klasöründe, kendi
README dosyasıyla birlikte yer alır.

## İçindekiler

| Klasör | Ödev | Açıklama |
|--------|------|----------|
| [`hw_template/`](./hw_template) | Ödev 1 — Custom Chat Template | Türkçe BPE tokenizer için Jinja2 chat template |
| [`hw_api/`](./hw_api) | Ödev 2 — Tool-Calling Asistanı | Veritabanına ve web'e erişen kütüphane asistanı |

---

## Ödev 1: Custom Chat Template (Jinja2)

**Amaç:** Bir dil modelinin kullanıcı, sistem ve asistan mesajlarını doğru ayırt
edebilmesi ve çıktıyı beklenen formatta üretebilmesi için bir Chat Template (Jinja2)
hazırlamak.

**Ne yaptım:** Sıfırdan eğittiğim Türkçe BPE tokenizer için, `system` / `user` /
`assistant` / `tool` rollerini ve tool-calling parametrelerini doğru sarmalayan bir
`chat_template.jinja` yazdım. Şablon belirli bir model ailesine bağımlı değildir; rol
sınırlarını evrensel `<|im_start|>` / `<|im_end|>` etiketleriyle belirtir ve tool
çağrılarını `<tool_call>` / `<tool_response>` biçiminde sarmalar.

**Konum:** [`hw_template/`](./hw_template) — `chat_template.jinja` ve açıklayıcı README.

---

## Ödev 2: Tool-Calling Destekli Asistan

**Amaç:** Bir dil modelinin dış dünyaya (veritabanı / API) erişip işlem yapabildiği
(tool-call) küçük bir sistem kurmak.

**Ne yaptım:** Bir **kütüphane asistanı** geliştirdim. Kullanıcı doğal dille kitap arar,
öneri ister, ödünç alır/iade eder; asistan bir dil modeli (Groq `llama-3.3-70b`) üzerinden
doğru fonksiyonu (tool) çağırır. Sistem gerçek bir **SQLite veritabanından** veri okur
(arama, öneri, durum) ve yazar (ödünç verme, iade — durum ve teslim tarihi güncellenir).
Ayrıca kitap konusu gibi veritabanında tutulmayan bilgiler için internete (Wikipedia)
erişen bir tool içerir.

**Öne çıkan özellikler:**
- **Halüsinasyon engelleme:** Yanıtlar tamamen tool'dan dönen gerçek veriye dayanır;
  veritabanında olmayan kitap "yok" olarak bildirilir, uydurulmaz.
- **Modüler mimari:** veritabanı (`db.py`), tool'lar (`tools.py`), yönlendirme
  (`router.py`) ve arayüz (`app.py`) ayrı katmanlardadır.
- **Dayanıklılık:** LLM servisi limitte olduğunda sistem otomatik olarak kural tabanlı
  bir yedek katmana düşer ve çalışmaya devam eder.

**Canlı demo:** https://huggingface.co/spaces/nursimakgul/library-tool-calling

**Konum:** [`hw_api/`](./hw_api) — tüm kaynak kodlar ve detaylı README.

---

## Depo Yapısı

```
.
├── README.md              # bu dosya — genel bakış
├── hw_template/           # Ödev 1
│   ├── chat_template.jinja
│   └── README.md
└── hw_api/                # Ödev 2
    ├── app.py             # Gradio arayüzü
    ├── db.py              # SQLite veritabanı katmanı
    ├── tools.py           # tool fonksiyonları + JSON şemaları
    ├── router.py          # LLM (Groq) + kural tabanlı yedek yönlendirme
    ├── requirements.txt
    └── README.md
```
