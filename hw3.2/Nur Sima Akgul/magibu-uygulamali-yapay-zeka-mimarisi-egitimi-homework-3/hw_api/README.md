---
title: Kütüphane Asistanı (Tool-Calling)
emoji: 📚
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
---

# 📚 Kütüphane Asistanı — Tool-Calling Destekli

Kullanıcının doğal dille yaptığı isteklere göre bir dil modelinin **gerçek bir
veritabanına** (SQLite) ve **internete** (Wikipedia) erişerek işlem yaptığı bir
tool-calling (function-calling) sistemidir. Asistan; kitap arar, öneri yapar, ödünç
verme/iade işlemlerini gerçekleştirir ve arka planda çağırdığı araçları adım adım gösterir.

## Canlı Demo

🔗 **Hugging Face Space:** _(https://huggingface.co/spaces/nursimakgul/library-tool-calling)_

## Senaryo

Bir kütüphane görevlisi asistanı. Okuyucular:
- Kitap arayabilir, bir kitabın müsait olup olmadığını sorabilir.
- Türe ve tercihe (yerli/yabancı, ince/kalın) göre **öneri** alabilir.
- Kitap **ödünç alabilir** (sistem 2 hafta sonrasına teslim tarihi atar ve en geç teslim
  tarihini bildirir).
- Kitap **iade edebilir** (sistem erken/zamanında/geç durumunu kaydeder).
- Bir kitabın **konusunu** öğrenebilir (bu bilgi veritabanında tutulmaz, internetten çekilir).

## Model ve Mimari

Kod modüler olarak ayrılmıştır:

| Dosya | Görev |
|-------|-------|
| `db.py` | SQLite veritabanı: kitap envanteri, ödünç/iade kayıtları (okuma + yazma) |
| `tools.py` | 6 tool fonksiyonu + JSON şemaları (modelin çağıracağı fonksiyonlar) |
| `router.py` | **Groq LLM** ile tool-calling (birincil) + kural tabanlı yedek katman |
| `app.py` | Gradio arayüzü, tool-call döngüsü, adım adım gösterim |
| `chat_template.jinja` | Rolleri ve tool-call'ları sarmalayan özel Jinja2 sohbet şablonu |

### Model ve tool-calling

- **Birincil:** [Groq](https://groq.com) üzerinden `llama-3.3-70b-versatile` modeli, gerçek
  function-calling ile. Model kullanıcının niyetini anlayıp doğru tool'u ve parametreleri seçer.
- **Yedek:** LLM kotası dolar ya da servis erişilemezse, sistem otomatik olarak hafif bir
  **kural tabanlı router**'a düşer. Böylece demo her koşulda ayakta kalır (graceful degradation).

### Tool'lar

| Tool | Tür | Açıklama |
|------|-----|----------|
| `kitap_ara` | DB okuma | Başlık/yazara göre arar, durumu döner |
| `kitap_oner` | DB okuma | Tür + filtrelere göre öneri getirir |
| `kitap_odunc_al` | DB yazma | Ödünç verir, 2 hafta teslim tarihi atar |
| `kitap_iade_et` | DB yazma | İade alır, erken/geç durumunu kaydeder |
| `odunc_durumu` | DB okuma | Kitabın müsaitliğini/teslim tarihini bildirir |
| `kitap_konusu` | Web | Kitabın konusunu Wikipedia'dan çeker |

### Halüsinasyon engelleme

Tüm yanıtlar tool'lardan dönen gerçek veriye dayanır. Veritabanında olmayan bir kitap
sorulduğunda sistem "bulunamadı" yanıtı verir; model kendi genel bilgisinden var olmayan
bir kitabı öneremez ya da uyduramaz. Kitap konusu gibi uzun bilgiler veritabanında
tutulmadığı için internetten (Wikipedia) çekilir.

## Yerelde Çalıştırma

```bash
pip install -r requirements.txt
export GROQ_API_KEY="gsk_..."   # https://console.groq.com adresinden ücretsiz alınır
python app.py
```

`GROQ_API_KEY` verilmezse sistem otomatik olarak kural tabanlı yedek katmanla çalışır.
Hugging Face Spaces'te `GROQ_API_KEY`, Space ayarlarından **Secret** olarak eklenmelidir.

---

## Örnek Çalışma (Tool-Call Akışı)

Aşağıda asistanla yapılmış gerçek bir oturum yer alır. Her yanıtın altında, arka planda
tetiklenen tool-call'lar ve bunların veritabanı/web'den döndürdüğü **gerçek veri** gösterilir.

### 1) Türe göre öneri (kitaptan tür çıkarımı)

**Kullanıcı:** ben en son dune serisini okudum ve çok beğendim buna benzer kitap önerisi yapabilir misin

**Asistan:** Bilim kurgu severlerin çok seveceği birkaç kitap bulundu:
- Fahrenheit 451 — Ray Bradbury (256 sayfa)
- Cesur Yeni Dünya — Aldous Huxley (288 sayfa)
- Vakıf — Isaac Asimov (296 sayfa)
- Ben, Robot — Isaac Asimov (320 sayfa)
- 1984 — George Orwell (352 sayfa)
- Marslı — Andy Weir (448 sayfa)

```
[Turn 1] Araç Çağrıları:
   -> kitap_oner(tur='bilim kurgu')
   <- {"bulundu": true, "adet": 6, "oneriler": [
        {"id": 23, "baslik": "Fahrenheit 451", "yazar": "Ray Bradbury", "sayfa": 256},
        {"id": 26, "baslik": "Cesur Yeni Dünya", "yazar": "Aldous Huxley", "sayfa": 288},
        {"id": 25, "baslik": "Vakıf", "yazar": "Isaac Asimov", "sayfa": 296}, ...]}
```
> Önerilen tüm kitaplar veritabanında gerçekten kayıtlıdır; model kitap uydurmaz.

### 2) Kitap konusu (web tool'u — Wikipedia)

**Kullanıcı:** peki fahrenheit 451 in konusu nedir

**Asistan:** Fahrenheit 451, Ray Bradbury'nin 1953'te basılan distopik bir bilimkurgu
romanıdır. Kitapların itfaiyeciler tarafından yakıldığı, düşünmenin yasaklandığı bir
gelecekte geçer. Adı, kâğıdın yaklaşık 451 °F'de tutuşmasından gelir...

```
[Turn 1] Araç Çağrıları:
   -> kitap_konusu(baslik='Fahrenheit 451')
   <- {"bulundu": true, "kitap": "Fahrenheit 451", "konu": "... (Wikipedia'dan)"}
```
> Konu bilgisi veritabanında tutulmaz; internetten (Wikipedia) çekilir.

### 3) Müsaitlik sorgusu (yalnızca bilgi verir, işlem yapmaz)

**Kullanıcı:** şu an boşta mı bu kitap

**Asistan:** Fahrenheit 451 kitabı şu an boşta.

```
[Turn 1] Araç Çağrıları:
   -> kitap_ara(sorgu='Fahrenheit 451')
   <- {"bulundu": true, "kitaplar": [{"id": 23, ..., "durum": "bosta"}]}
```

### 4) Ödünç alma (önce okuyucu adı sorulur — ad uydurulmaz)

**Kullanıcı:** ödünç alabilir miyim

**Asistan:** Kitabı kimin adına ödünç alalım?

**Kullanıcı:** Nur Sima Akgül

**Asistan:** Fahrenheit 451 kitabı Nur Sima Akgül adına 2026-08-03 tarihinde ödünç
verildi. En geç 2026-08-17 tarihinde teslim edilmesi gerekmektedir.

```
[Turn 1] Araç Çağrıları:
   -> kitap_odunc_al(kitap_id=23, okuyucu='Nur Sima Akgül')
   <- {"basarili": true, "kitap": "Fahrenheit 451", "okuyucu": "Nur Sima Akgül",
       "odunc_tarih": "2026-08-03", "en_gec_teslim": "2026-08-17"}
```
> Ödünç alma için okuyucu adı zorunludur; verilmezse asistan sorar, ad uydurmaz.
> Teslim tarihi otomatik olarak 2 hafta sonrasına ayarlanır.

### 5) Ödünç sonrası durum (veritabanı değişikliği kalıcıdır)

**Kullanıcı:** fahrenheit 451 kitabı boşta mı

**Asistan:** Fahrenheit 451 kitabı şu an ödünçte.

```
[Turn 1] Araç Çağrıları:
   -> kitap_ara(sorgu='Fahrenheit 451')
   <- {"bulundu": true, "kitaplar": [{"id": 23, ..., "durum": "oduncte"}]}
```
> Bir önceki adımda yapılan ödünç işlemi veritabanına yazıldığı için kitabın durumu artık
> "ödünçte" görünür. Bu, sistemin gerçek veri okuyup yazdığının kanıtıdır.

### Halüsinasyon engelleme

Veritabanında bulunmayan bir kitap sorulduğunda asistan onu "varmış gibi" sunmaz:

**Kullanıcı:** "İnsanın Esareti" kitabı var mı?

**Asistan:** Maalesef "İnsanın Esareti" kitabı kütüphanede mevcut değil.

```
[Turn 1] Araç Çağrıları:
   -> kitap_ara(sorgu='İnsanın Esareti')
   <- {"bulundu": false, "mesaj": "'İnsanın Esareti' ile eşleşen kitap bulunamadı."}
```

### Dayanıklılık (LLM limitte olduğunda yedek katman)

LLM servisi (Groq) hız limitine takıldığında sistem otomatik olarak kural tabanlı yedek
router'a düşer ve kesintisiz çalışmaya devam eder. Yedek katman, LLM erişilemediğinde arama,
öneri ve durum sorgulama gibi salt-okunur işlemleri karşılar; ödünç/iade gibi veritabanı 
değiştiren kritik işlemler için birincil LLM katmanı gereklidir.

```
[Bilgi] LLM kullanılamadı (RateLimitError), yedek router devrede.
[Yedek Router] Araç Çağrısı:
   -> kitap_oner(tur='polisiye', ...)
   <- {"bulundu": true, "oneriler": [...]}
```