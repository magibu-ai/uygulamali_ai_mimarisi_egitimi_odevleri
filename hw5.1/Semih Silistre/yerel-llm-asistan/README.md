# 🤖 Yerel Asistan — Genel Amaçlı Tool Calling Asistanı

Tamamen **kendi bilgisayarında** çalışan, internete çıkabilen, hesap yapabilen, kod çalıştırabilen ve seni hatırlayan genel amaçlı bir asistan. Hiçbir bulut LLM servisi kullanılmaz; model LM Studio (veya Ollama) üzerinden lokalde koşar.

> Magibu Uygulamalı Yapay Zekâ Mimarisi Eğitimi — **Ödev 5.1**

---

## 🎯 Senaryo

Bu asistan **genel amaçlı** kurgulandı. Dar bir dikeye (hukuk, sağlık, finans) sıkışmak yerine, günlük kullanımda gerçekten ihtiyaç duyulan yetenekleri tek bir terminal arayüzünde topladı:

| İhtiyaç | Nasıl çözüldü |
|---|---|
| "Bu bilgi eğitim verisinden sonra değişmiş olabilir" | `web_search` + `fetch_url` |
| "Küçük modeller aritmetikte yanılır" | `calculator` (AST tabanlı, `eval` yok) |
| "Model bugünün tarihini bilmez" | `current_datetime` |
| "Hava/döviz için arama sonucu güvenilmez" | `get_weather`, `currency_convert` (yapılandırılmış API) |
| "Gerçek hesaplama / veri işleme lazım" | `run_python` (ayrı süreç, zaman aşımlı) |
| "Asistan beni her oturumda sıfırdan tanıyor" | `save_note` + `recall_notes` (SQLite kalıcı hafıza) |

**Ayırt edici tool:** `save_note` / `recall_notes` ikilisi. Çoğu asistan oturum kapanınca her şeyi unutur. Buradaki asistan kullanıcıyla ilgili kalıcı bilgileri (tercihler, hedefler, üzerinde çalıştığı proje) SQLite'a yazar ve sonraki oturumda geri çağırır. Genel amaçlı bir asistanı gerçekten kullanışlı yapan şey bu.

---

## 🧠 Model

| | |
|---|---|
| **Model** | `qwen/qwen3-8b` (Q4_K_M, GGUF) |
| **Çalıştırma** | LM Studio yerel sunucusu (OpenAI uyumlu, `http://localhost:1234/v1`) |
| **Donanım** | Apple M5 Pro / 24 GB RAM |

**Neden bu model?**
1. **Tool calling desteği yerleşik.** Qwen3 ailesi araç çağırma için eğitilmiş; şemaya uygun JSON argüman üretmede 8B seviyesindeki alternatiflerden belirgin şekilde daha kararlı.
2. **Türkçe yeterliliği.** Türkçe soruları anlayıp Türkçe cevap üretiyor; arama sorgusunu Türkçe anahtar kelimeye çevirebiliyor.
3. **Boyut/kalite dengesi.** Q4_K_M yaklaşık 5 GB; 24 GB RAM'de bağlam penceresiyle birlikte rahat sığıyor ve makul hızda üretiyor. Daha agresif kuantizasyonlarda (Q2/Q3) araç argümanlarındaki JSON bozulmaya başlıyor — bu yüzden Q4 tercih edildi.

> Farklı bir model kullanmak için tek yapman gereken `LOCAL_LLM_MODEL` ortam değişkenini değiştirmek. Ollama ile çalıştırmak için `LOCAL_LLM_BASE_URL=http://localhost:11434/v1` yeterli.

---

## 🛠️ Araçlar (9 adet)

| Araç | Ne yapar | Sağlayıcı |
|---|---|---|
| `web_search` | DuckDuckGo'da arama; sorguyu anahtar kelimeye indirger | ddgs (anahtar gerekmez) |
| `fetch_url` | Sayfanın metnini indirir, HTML'i temizler, kırpar | requests |
| `calculator` | Aritmetik ifade değerlendirir | AST (güvenli) |
| `current_datetime` | Tarih/saat, gün ekleme-çıkarma, **hedef tarihe kalan gün** | stdlib |
| `get_weather` | Güncel hava + 3 günlük tahmin | Open-Meteo (anahtar gerekmez) |
| `currency_convert` | Güncel/geçmiş kurla döviz çevrimi | Frankfurter / ECB (anahtar gerekmez) |
| `run_python` | Python kodunu ayrı süreçte çalıştırır | subprocess |
| `save_note` | Kalıcı not kaydeder | SQLite |
| `recall_notes` | Kayıtlı notları arar | SQLite |

**Not:** Hiçbir araç API anahtarı istemez. Repoyu klonlayan kişi `.env` doldurmadan doğrudan çalıştırabilir.

### Güvenlik önlemleri
- `calculator` **`eval` kullanmaz**; ifadeyi AST'ye çevirip sadece sayı ve aritmetik operatör düğümlerine izin verir. `__import__("os").system("ls")` denemesi reddedilir.
- `run_python` ayrı süreçte, geçici dizinde, zaman aşımıyla çalışır; `shutil.rmtree`, `os.remove`, `os.system`, `subprocess`, `socket` içeren kod reddedilir.
- Araçlar exception fırlatmaz; `"HATA: ..."` metni döndürür. Model hatayı okuyup kendini toparlayabilir (ör. yanlış şehir adını düzeltip yeniden çağırır).

---

## 🧾 Sistem İstemi (System Prompt) Tasarımı

Küçük yerel modellerde kaliteyi belirleyen asıl yer burası. İstem üç bölümden oluşuyor: **rol**, **araç yönlendirmesi**, **sınırlar**.

Öne çıkan tercihler:

1. **Araç listesi elle yazılmıyor.** `tools.py` içindeki kayıttan üretiliyor (`tool_summaries()`), böylece yeni araç eklendiğinde istem otomatik güncelleniyor; şema ile istem asla ayrışmıyor.
2. **Her araç için "ne zaman çağır" kuralı var.** Küçük modeller araç seçiminde tahmin yürütür; istem bunu ortadan kaldırıyor:
   > "Hava/döviz için arama yerine `get_weather` ve `currency_convert` kullan; daha doğru ve yapılandırılmış sonuç verirler."
3. **Arama sorgusu için örnekli kural.** Model kullanıcının cümlesini olduğu gibi aratmasın diye kötü/iyi örnek verildi:
   > Kötü: "acaba yarın İstanbul'da hava nasıl olacak merak ediyorum"
   > İyi: "İstanbul hava durumu yarın"
4. **"Gereksiz çağrı yok" maddesi.** Tanım, çeviri, özet, sohbet sorularında araç çağırmaması açıkça söylendi — aksi halde küçük modeller her soruda arama yapmaya meyilli.
5. **Tarih gömülü.** Modelin eğitim kesim tarihine güvenmemesi için bugünün tarihi isteme yazılıyor.
6. **`temperature=0.3`.** Araç argümanı üreten bir asistanda yüksek sıcaklık uydurma parametreye yol açıyor.
7. **"Araç çağrısını taklit etme" kuralı.** Model, aracı gerçekten çağırmak yerine cevabın içine `calculator("23863 * 0.82")` yazıp sonucunu uydurmaya çalışıyordu. İsteme açık yasak eklendi; ayrıca `agent.py` bu kalıbı yakalayıp gerçek çağrı yaptırıyor (aşağıda).
8. **Araç adları kullanıcıdan gizli.** "save_note ile kaydedeyim mi" yerine "not alayım mı" demesi istendi.

---

## 📁 Dosya Yapısı

```
HAFTA 5.1/
├── config.py          # Tüm ayarlar (endpoint, model, limitler) — ortam değişkeniyle override edilebilir
├── system_prompt.py   # Sistem istemi; araç listesini tools.py'den otomatik üretir
├── tools.py           # 9 aracın şeması + implementasyonu (@tool dekoratörü)
├── agent.py           # Tool calling döngüsü (çağır → çalıştır → geri besle)
├── main.py            # Terminal arayüzü (REPL + tek-soru modu)
├── demo_konusmalar.py # README'deki örnek konuşmaları üretir
├── build_static.py    # HF Static Space için tek dosyalık index.html derler
├── push_to_hf.py      # Space'e yükler (README'ye HF YAML başlığını ekleyerek)
├── app.py             # Yerel Gradio vitrini (opsiyonel)
├── hf_header.yaml     # HF Space ayarları — GitHub README'sini kirletmesin diye ayrı
├── requirements.txt
└── README.md
```

### Tool calling döngüsü nasıl çalışıyor?

```
kullanıcı mesajı
      ↓
  model çağrısı  ──────────────────┐
      ↓                            │
  tool_calls var mı?               │
   ├── hayır → cevabı döndür       │
   └── evet  → araçları çalıştır   │
               sonuçları geçmişe ekle
                          └────────┘  (en fazla MAX_TOOL_ROUNDS tur)
```

- Asistanın `tool_calls` içeren mesajı geçmişe **aynen** ekleniyor; ardından her çağrı için `role: "tool"` mesajı geliyor. Bu sıra bozulursa OpenAI uyumlu sunucular hata verir.
- Tek turda birden fazla araç çağrısı (paralel tool calling) destekleniyor.
- Tur limiti dolarsa model araçsız bir son turla eldeki bilgiyle cevaplamaya zorlanıyor — sonsuz döngü yok.
- Geçmiş `MAX_HISTORY_MESSAGES` ile kırpılıyor ki 8B modelin bağlamı şişmesin.

### Sahte araç çağrısı yakalayıcı

Testlerde modelin tekrarlayan bir kusuru görüldü: aracı gerçekten çağırmak yerine cevabın içine `calculator("23863 * (1 - 0.18)")` gibi bir çağrı **yazıp** sonucunu uyduruyordu. Uydurulan sonuç da yanlış çıkıyordu (19.475,94 — doğrusu 19.567,66).

`agent.py` bunu bir regex ile yakalıyor: cevap metninde kayıtlı bir araç adının hemen ardından `(` ve tırnak/süslü parantez geliyorsa, model uyarılıp aracı gerçekten çağırması isteniyor. Uyarı **soru başına yalnızca bir kez** veriliyor, aksi halde döngüye girme riski var.

```
🔧 [1] currency_convert({"from_currency":"USD","to_currency":"TRY","amount":500})
↩️  500 USD = 23863.0000 TRY
⚠️  Cevapta sahte araç çağrısı var, gerçek çağrı isteniyor.
🔧 [3] calculator({"expression":"23863 * (1 - 0.18)"})
↩️  23863 * (1 - 0.18) = 19567.66     ← artık gerçek sonuç
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Yerel modeli hazırla (LM Studio)

```bash
# Modeli indir
lms get qwen/qwen3-8b

# Sunucuyu başlat ve modeli yükle
lms server start
lms load qwen/qwen3-8b

# Kontrol
lms ps
curl http://localhost:1234/v1/models
```

> **Ollama kullanıyorsan:**
> ```bash
> ollama pull qwen3:8b && ollama serve
> export LOCAL_LLM_BASE_URL=http://localhost:11434/v1
> export LOCAL_LLM_MODEL=qwen3:8b
> ```

### 2. Bağımlılıklar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Çalıştır

```bash
python main.py              # sohbet modu
python main.py --quiet      # araç çağrılarını gizle
python main.py "dolar kaç TL?"   # tek soru sor, çık
```

Sohbet içi komutlar: `/araclar`, `/sifirla`, `/cikis`

---

## 💬 Örnek Konuşmalar (lokalde test edildi)

Aşağıdaki çıktıların tamamı `python demo_konusmalar.py` ile **gerçek oturumdan** alındı; elle yazılmadı. Ham hâli: [`ornek_konusmalar.md`](ornek_konusmalar.md)

### 1. Araç çağırmadan cevap

**👤** Transformer mimarisindeki attention mekanizmasını iki cümleyle anlat.

_(araç çağrısı yok — istemdeki "gereksiz çağrı yok" kuralı çalışıyor)_

**🤖** Transformer mimarisinde **attention mekanizması**, bir kelimenin diğer kelimelerle olan ilişkisini dinamik olarak ölçerek bağlamı anlamaya yardımcı olur. Bu sayede model, cümle içindeki önemli unsurları öncelikli şekilde işler ve daha etkili bir şekilde anlamlarını çıkarır.

---

### 2. Hava durumu

**👤** Yarın Trabzon'a gideceğim, yanıma mont almalı mıyım?

```
🔧 get_weather({"city":"Trabzon"})
↩️  Trabzon, Türkiye Cumhuriyeti — şu an: 27.1°C, az bulutlu, nem %75, rüzgâr 7.2 km/s
    Tahmin: 12.08 Çarşamba: 21.8–27.4°C, parçalı bulutlu | 13.08 Perşembe: 22.6–26.5°C, hafif sağanak …
```

**🤖** Yarın Trabzon'da hafif sağanak ve 22.6–26.5°C arası sıcaklık bekleniyor. Mont mutlaka faydalı olur, özellikle yağışlı hava nedeniyle. Gök gürültülü fırtına (14.08) öncesi de soğuk bir rüzgâr etkisi olabilir. Hafif mont + şapka yeterli olur. 🌧️

---

### 3. Zincirleme: döviz → hesap (sahte çağrı yakalayıcı devrede)

**👤** Elimde 500 dolar var, bugünün kuruyla kaç TL eder? Bunun %18'ini vergiye ayırırsam elimde ne kalır?

```
🔧 currency_convert({"from_currency":"USD","to_currency":"TRY","amount":500})
↩️  500 USD = 23863.0000 TRY (kur tarihi: 2026-08-11, kaynak: ECB/Frankfurter)
⚠️  Cevapta sahte araç çağrısı var, gerçek çağrı isteniyor.
🔧 calculator({"expression":"23863 * (1 - 0.18)"})
↩️  23863 * (1 - 0.18) = 19567.66
```

**🤖** 500 dolar bugün 23.863 TL'ye eşittir (kaynak: ECB/Frankfurter). %18 vergi için 4.295,34 TL kesilir (23.863 × 0,18). Vergi sonrası kalan tutar: **19.567,66 TL**.

> Bu örnek yakalayıcının işini gösteriyor: model önce sonucu metinde uydurmaya kalktı, uyarıldı, aracı gerçekten çağırdı.

---

### 4. İnternet araması

**👤** Türkiye'nin en son açıklanan yıllık enflasyon oranı kaç?

```
🔧 web_search({"query":"Türkiye enflasyon oranı 2026","max_results":5})
↩️  1. Enflasyon Oranları (TEFE - ÜFE — TÜFE Oranları) … URL: https://legalbank.net/belge/enf…
```

**🤖** Türkiye'nin 2026 yılı Temmuz ayı yıllık enflasyon oranı %31,75'tir. Bu oran, Haziran ayındaki %32,11'den bir miktar düştüğü belirtilmiş. (Kaynak: https://www.sbb.gov.tr/enflasyon/)

> Modelin kullanıcının uzun cümlesini `"Türkiye enflasyon oranı 2026"` anahtar kelimesine indirgemesi, istemdeki 2. kuralın sonucu.

---

### 5. Sayfa okuma

**👤** https://tr.wikipedia.org/wiki/Kayseri sayfasını aç ve Kayseri'nin rakımı ile plaka kodunu söyle.

```
🔧 fetch_url({"url":"https://tr.wikipedia.org/wiki/Kayseri"})
↩️  Kayseri - Vikipedi İçeriğe atla Ana menü … (HTML temizlenmiş metin, 4000 karaktere kırpılmış)
```

**🤖** Kayseri'nin rakımı **1054 metre** ve plaka kodu **38**'dir. (https://tr.wikipedia.org/wiki/Kayseri)

---

### 6. Tarih hesabı

**👤** Bugün ayın kaçı ve 2027 yılbaşına kaç gün kaldı?

```
🔧 current_datetime({"until_date":"2027-01-01"})
↩️  12.08.2026 Çarşamba, saat 16:28 (yerel saat). 01.01.2027 tarihine 142 gün var.
```

**🤖** 12 Ağustos 2026 Çarşamba. 2027 yılbaşı (1 Ocak 2027) için **142 gün** kaldı.

---

### 7. Kod çalıştırma

**👤** 1'den 1000'e kadar olan asal sayıların toplamını hesapla.

```
🔧 run_python({"code":"def sum_primes(limit):\n    total = 0\n    for num in range(2, limit + 1):\n        is_prime = True\n        for i in range(2, int(num**0.5) + 1):\n            if num % i == 0:\n                is_prime = False\n                break\n        if is_prime:\n            total += num\n    return total\n\nprint(sum_primes(1000))"})
↩️  76127
```

**🤖** 1'den 1000'e kadar olan asal sayıların toplamı **76127**'dir. Hesaplama için her sayının kareköküne kadar olan bölenleri denetlendi.

---

### 8. Kalıcı hafıza — kaydetme

**👤** Not al: sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum.

```
🔧 save_note({"topic":"kahve tercihi","content":"sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum"})
↩️  Not kaydedildi (#1, konu: kahve tercihi).
```

**🤖** Not kaydedildi (#1, konu: kahve tercihi). Dilersen başka bir not daha ekleyebilirsin!

---

### 9. Kalıcı hafıza — hatırlama

**👤** Bana kahve tercihimi söyler misin?

```
🔧 recall_notes({"query":"kahve tercihi"})
↩️  [2026-08-12] kahve tercihi: sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum
```

**🤖** Kahve tercihin: Sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum. (Not #1)

> Hafızanın kalıcılığı **ayrı süreçlerde** doğrulandı: not bir `python main.py` çağrısında kaydedildi, tamamen yeni bir çağrıda geri okundu.

---

## ⚙️ Yapılandırma

Tüm ayarlar ortam değişkeniyle değiştirilebilir (`config.py`):

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `LOCAL_LLM_BASE_URL` | `http://localhost:1234/v1` | LM Studio / Ollama endpoint'i |
| `LOCAL_LLM_MODEL` | `qwen/qwen3-8b` | Yüklü model kimliği |
| `LOCAL_LLM_TEMPERATURE` | `0.3` | Düşük tutuluyor: araç argümanı uydurulmasın |
| `LOCAL_LLM_MAX_TOKENS` | `4096` | Düşünme bloğu + cevap birlikte sığsın |
| `ENABLE_THINKING` | `1` | `0` yaparsa isteme `/no_think` eklenir; hızlı ama zincirleme zayıflar |
| `MAX_TOOL_ROUNDS` | `6` | Bir soru için azami ardışık araç turu |
| `MAX_HISTORY_MESSAGES` | `24` | Bağlamda tutulan son mesaj sayısı |
| `SEARCH_MAX_RESULTS` | `5` | Arama sonucu sayısı |
| `SEARCH_REGION` | `tr-tr` | DuckDuckGo bölgesi |
| `FETCH_MAX_CHARS` | `4000` | `fetch_url` kırpma sınırı |
| `PYTHON_TIMEOUT` | `10` | `run_python` zaman aşımı (saniye) |
| `DEFAULT_CITY` | `İstanbul` | Şehir belirtilmezse hava durumu için |
| `MEMORY_DB` | `./memory.db` | Kalıcı not veritabanı |

---

## 🧪 Öğrenilenler / Notlar

- **Sistem istemi, model boyutundan daha belirleyici.** İsteme "hava/döviz sorularında arama yerine şu araçları kullan" kuralı yazılmadan önce model, hava durumu sorularında bile `web_search` çağırıyordu. Kuralı eklemek araç seçimini düzeltti.
- **Araçlar hata fırlatmamalı.** Exception yerine `"HATA: ..."` metni döndürmek modelin kendini toparlamasına izin veriyor: yanlış şehir adı verdiğinde hatayı okuyup düzeltilmiş adla yeniden çağırıyor. Exception ise döngüyü kırardı.
- **Şema ile istemi tek kaynaktan üretmek** ikisinin zamanla ayrışmasını engelliyor. `tools.py`'ye yeni bir araç eklendiğinde istem kendiliğinden güncelleniyor.
- **`temperature` araç argümanlarını doğrudan etkiliyor.** Yüksek sıcaklıkta model şemada olmayan parametreler uydurmaya başlıyordu; 0.3 bunu bitirdi.

### 🔬 Ölçüm: "thinking" modu araç çağrısını nasıl etkiliyor?

Qwen3 varsayılan olarak cevaptan önce uzun bir düşünme bloğu üretiyor. Bu blok tool calling'i hem iyileştiriyor hem bozuyor — ikisi de ölçüldü.

**Thinking açıkken sorun:** düşünme bloğu tek soruda **1.247 reasoning token** yiyordu; `max_tokens=2048` ile cevaba yer kalmıyor ve asistan **boş cevap** dönüyordu.

**Thinking'i kapatma denemesi:** OpenAI uyumlu `chat_template_kwargs={"enable_thinking": False}` parametresi LM Studio'da **işe yaramadı** (reasoning token 2.046'ya çıktı, araç çağrısı hiç yapılmadı). Sistem isteminin sonuna Qwen3'ün resmî `/no_think` etiketini eklemek ise çalıştı: reasoning **0 token**, doğru araç çağrısı, toplam 30 token.

**Ama kapalıyken yeni bir sorun çıktı.** Çok adımlı soruda model araca eksik argüman göndermeye başladı:

| | Thinking KAPALI | Thinking AÇIK |
|---|---|---|
| `currency_convert` argümanı | `{from, to}` — **amount hiç yok** | `{from, to, amount: 500}` ✅ |
| Dönen değer | 1 USD = 47.72 TRY (yanlış temel) | 500 USD = 23.863 TRY ✅ |
| `calculator` çağrısı | hiç yapılmadı | yapıldı ✅ |
| Nihai cevap | 19.574,63 TL ❌ | 19.567,66 TL ✅ |

Bu yüzden **varsayılan thinking açık** bırakıldı ve `max_tokens` 4096'ya çıkarıldı. Hız/maliyet öncelikliyse `ENABLE_THINKING=0` ile kapatılabilir.

### ⚠️ Kalan sınırlar (dürüstçe)

1. **Araç seçimi tutarsız olabiliyor.** KDV/taksit sorusu tek başına sorulduğunda model `calculator`'ı çağırıyor, ancak demo dizisi içinde aynı soruyu kafadan hesapladı (sonuç doğru çıktı ama araç kullanılmadı). İstemde "sayısal her sonucu `calculator` ile üret" kuralı var; 8B seviyesinde kurala uyum %100 değil.
2. **Araç adları cevaba sızabiliyor.** "Araç adlarını kullanıcıya söyleme" kuralına rağmen cevapta zaman zaman `calculator("...")` ifadesi görünüyor.
3. **Web araması çelişkili kaynakları ayıklamıyor.** Enflasyon sorusunda farklı kaynaklardan farklı oranlar geldiğinde model bunları birleştirmekte zorlandı; bir kaynağı seçip diğerini eleyecek bir güven sıralaması yok.

Üçü de aynı yere işaret ediyor: daha büyük bir model (14B+) ya da cevabı son bir doğrulama turundan geçiren ek bir katman. Bir sonraki adım burası.
