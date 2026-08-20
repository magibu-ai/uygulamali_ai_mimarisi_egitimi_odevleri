# 🚀 Kariyer Copilotu

**Magibu Academy — Tool-Calling Destekli Asistan Geliştirme Ödevi**

Yerel bir LLM (Ollama üzerinde `qwen3.5:9b`) ile çalışan, sistem istemi ve araç
çağrıları (tool calling) üzerinden optimize edilmiş, iş başvurusu takibi ve
kariyer danışmanlığı yapan bir asistan.

---

## 🎯 Senaryo

Kariyer Copilotu, kullanıcının iş arama sürecinde üç şeyi bir arada yapar:

1. **İş başvurusu takibi** — hangi şirkete, hangi pozisyona, ne zaman
   başvurdu; mülakat tarihleri, durumlar (Başvuruldu / Mülakat / Reddedildi
   vb.) ve notlar bir SQLite veritabanında tutulur.
2. **Şirket / sektör araştırması** — kullanıcı bir şirket veya pozisyon
   hakkında güncel bilgi istediğinde internette arama yapar.
3. **Mülakat ve CV hazırlığı** — kullanıcının kendi CV'si ve mülakat çalışma
   notları üzerinde RAG (Retrieval-Augmented Generation) ile anlamsal arama
   yaparak, yalnızca gerçekten var olan bilgilere dayanan cevaplar üretir.

Sistemin en büyük önceliği **halüsinasyon üretmemek**tir: veritabanında
olmayan bir başvuruyu, RAG context'inde geçmeyen bir CV bilgisini veya
teyit edilmemiş bir şirket bilgisini asla uydurmaz.

---

## 🧠 Kullanılan Model

- **Model:** `qwen3.5:9b`, Ollama üzerinden yerel olarak çalıştırılıyor
  (`backend/ollama_client.py` içinde `MODEL_NAME` sabiti).
- **Neden bu model:** tool-calling'i (fonksiyon çağırma) düzgün destekliyor
  ve bilgisayarda sorunsuz çalışabilecek boyutta.
- **Önemli özellik:** bu model bir "thinking" (düşünme) moduna sahip —
  aşağıdaki "Test Sürecinde Karşılaşılan Sorunlar" bölümünde bunun nasıl
  bir soruna yol açtığı ve nasıl çözüldüğü anlatılıyor.
- İstekler arasında modelin bellekte kalması için `keep_alive: "10m"`
  kullanılıyor.

---

## 🗂️ Proje Yapısı

```
Kariyer-Copilotu-Magibu/
├── backend/
│   ├── app.py              # FastAPI uygulaması (REST API)
│   ├── chat.py              # Agent döngüsü + terminal chat modu
│   ├── ollama_client.py     # Ollama /api/chat çağrısı
│   ├── tools.py             # Tool şemaları + dispatch mekanizması
│   ├── db.py                 # SQLite CRUD (başvurular)
│   ├── career_rag.py         # ChromaDB üzerinde RAG araması
│   ├── index_career.py       # CV / mülakat notlarını chunk'layıp indeksleme
│   └── system_prompt.md      # Sistem istemi (32 kural)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js                # Chat arayüzü + tool paneli + istatistik sidebar'ı
├── data/
│   ├── cv.txt                 # RAG için örnek/demo CV
│   └── mulakat_notlari.txt    # RAG için örnek/demo mülakat çalışma notları
├── requirements.txt
└── README.md
```

---

## 🔧 Araçlar (Tools)

Model, kurallara bağlı kalarak toplam **8 araç** arasından seçim yapabiliyor:

| Araç | Ne yapar |
|---|---|
| `web_arama` | DuckDuckGo üzerinden internette güncel bilgi arar (şirketler, pozisyonlar, sektörler). |
| `basvuru_ekle` | Yeni bir iş başvurusunu veritabanına kaydeder (şirket, pozisyon, tarih zorunlu). |
| `basvuru_ara` | Şirket veya pozisyon adına göre kayıtlı başvuruları arar. |
| `basvuru_listele` | Başvuruları durum / şirket / pozisyon filtreleriyle listeler. |
| `basvuru_guncelle` | Mevcut bir başvurunun durumunu, mülakat tarihini veya notunu günceller. |
| `basvuru_istatistikleri` | Toplam başvuru sayısı, duruma göre dağılım, en çok başvurulan pozisyonlar. |
| `yaklasan_mulakatlari_getir` | Belirtilen gün sayısı içindeki yaklaşan mülakatları getirir. |
| `rag_ara` | CV ve mülakat notları üzerinde ChromaDB ile anlamsal arama yapar (`cv` veya `mulakat_notlari` kaynağına göre filtrelenebilir). |

Modelin argüman isimlerinde küçük yazım hataları yapması (ör. `posisyon`
yerine `pozisyon`) `tools.py` içindeki `_arguments_duzelt` fonksiyonu ile
tolere ediliyor.

---

## 📜 Sistem İstemi Mantığı

`system_prompt.md`, 32 kuraldan oluşan detaylı bir sistem istemi. Öne çıkan
prensipler:

- Başvuru bilgileri hakkında **asla tahmin yürütülmez** — mutlaka ilgili
  araç çağrılır.
- Yeni başvuru için şirket / pozisyon / tarih bilgisi eksikse, aracı
  çağırmadan önce kullanıcıdan istenir.
- Bir görev birden fazla araç gerektiriyorsa, agent döngüsü içinde araçlar
  sırayla gerçekten çağrılır — "çağıracağım" demek yetmez.
- RAG kullanılan sorularda cevap **yalnızca** `rag_ara` sonucundaki
  context'e dayanır; modelin kendi genel bilgisiyle tamamlama yapılmaz.
- Kullanıcı "CV'ye göre" veya "mülakat notlarına göre" derse yalnızca o
  kaynak kullanılır.
- Model, RAG/context kullandığını kullanıcıya asla açıklamaz — sonuç doğal
  bir cevap olarak sunulur.

---

## ⚙️ Kurulum ve Çalıştırma

### 1. Depoyu klonla ve bağımlılıkları kur

```bash
git clone https://github.com/Rashad2173/Kariyer-Copilotu-Magibu.git
cd Kariyer-Copilotu-Magibu

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Ollama'yı hazırla

```bash
ollama pull qwen3.5:9b
```

Ollama'nın `http://localhost:11434` adresinde çalıştığından emin ol
(genelde kurulumla birlikte arka planda otomatik başlar).

### 3. RAG index'ini oluştur (ilk çalıştırmada bir kez)

```bash
cd backend
python index_career.py
```

Bu komut `data/cv.txt` ve `data/mulakat_notlari.txt` dosyalarını okuyup
parçalara ayırır, embedding'lerini üretir ve `backend/chroma_db/` klasörüne
kaydeder.

### 4a. Terminalden çalıştır

```bash
cd backend
python chat.py
```

### 4b. Web arayüzünden çalıştır

```bash
# Terminal 1 — backend
cd backend
uvicorn app:app --reload --port 8000

# Terminal 2 — frontend (basit bir static server ile aç, CORS sorunlarını önler)
cd frontend
python -m http.server 5500
```

Tarayıcıda `http://localhost:5500` adresine gidip Kariyer Copilotu ile
sohbet edebilirsin. Veritabanı tabloları (`kariyer.db`) uygulama ilk
başladığında otomatik oluşturulur.

---

## 💬 Örnek Konuşmalar

### Örnek 1 — Şirket araştırması (`web_arama`)

**Kullanıcı:** *"Magibu sirketi ile ilgili bana bilgi ver"*

**🔧 Çağrılan araç:**
```json
{
  "name": "web_arama",
  "arguments": {
    "query": "MAGIBU şirket hakkında genel bilgi",
    "sonuc_sayisi": 5
  }
}
```

**Asistan:**

> Magibu AI hakkında şu bilgileri öğrendim:
>
> **Şirket Hakkında:**
> - Türkiye merkezli bir yapay zeka şirketi olup, Türkçe foundation (temel)
>   modelleri ve embedding modellerini geliştiriyor.
> - Kurum içlerinde çalışan, güvenli ve ölçülebilir yapay zekâ
>   sistemlerine odaklanıyorlar.
> - Doğal Dil İşleme (NLP), Büyük Dil Modelleri (LLM) ve Yapay Zeka (AI)
>   alanlarında uzmanlaşmış bir araştırmacı gruptur.
>
> **İş Birlikleri:**
> Verilere sahip olan kurumlarla çalışmayı hedefliyorlar, Türkçe dilinin
> yapay zekâ ekosistemine entegrasyonunu destekliyorlar.

### Örnek 2 — Yapı Kredi Bankası (thinking-mode düzeltmesi sonrası doğrulama)

**Kullanıcı:** *"Yapı kredi bankasiyla ilgili bana bilgi ver"*

**🔧 Çağrılan araç:** `web_arama` (query: "Yapı Kredi Bankası şirket
profili, sektörlere bakış ve iş fırsatları 2026")

**Asistan (özet):** kuruluş yılı (1944), kurucusu (Kazım Taşkent) ve 2026
ilk yarı itibarıyla yaklaşık 4 trilyon TL'lik aktif büyüklüğü gibi güncel,
web aramasından gelen bilgileri kapsayan, doğal akışta bir Türkçe cevap
üretti.

> Bu test aşağıda anlatılan "thinking modu" düzeltmesinin gerçekten
> çalıştığını doğrulamak için kullanıldı — düzeltmeden önce aynı soru,
> modelin cevabı üretememesi yüzünden hata mesajıyla sonuçlanıyordu.

---

## 🐞 Test Sürecinde Karşılaşılan Sorunlar ve Çözümler

### 1. `qwen3.5:9b` thinking modu — `content` alanı boş kalıyordu

**Sorun:** `web_arama` aracı sorunsuz çalışıp sonuçları döndürüyordu, ama
tool sonucu modele geri gönderildiğinde bazı sorularda ("Yapı Kredi
bankasıyla ilgili bilgi ver" gibi) asistan boş bir cevapla dönüyor, bu iki
tur üst üste tekrarlanınca da `chat.py`'nin agent döngüsü *"Model görevi
tamamlayamadı. Lütfen isteğinizi tekrar deneyin."* mesajıyla hata veriyordu.

**Teşhis:** `qwen3.5:9b`, "thinking" (düşünme) özellikli bir model.
`ollama_client.py`, Ollama isteğine modelin düşünme modunu kapatan bir
parametre göndermiyordu. Sonuç olarak model, tool sonucunu aldıktan sonra
çıktı bütçesinin tamamını görünmeyen bir iç muhakeme metnine (`thinking`
alanı) harcıyor, kullanıcıya gösterilecek asıl `content` alanını boş
bırakıyordu. `chat.py` yalnızca `content`'e baktığı için bunu "boş cevap"
sayıyordu. Bu, doğrudan Ollama'ya istek atılıp `assistant_message`'ın ham
hâli incelenerek doğrulandı: `content: ""`, `thinking` alanında ise uzun
bir iç muhakeme metni bulunuyordu.

**Çözüm:** `ollama_client.py` içindeki Ollama isteğine `"think": False`
parametresi eklendi. Böylece model muhakemeye takılıp boş kalmadan doğrudan
cevap yazıyor.

**Doğrulama:** Aynı soru (`"Yapı kredi bankasiyla ilgili bana bilgi ver"`)
gerçek akıştan (`kariyer_chat`) tekrar çalıştırıldı — artık `basarili: True`
dönüyor ve web aramasından gelen gerçek bilgilerle düzgün bir Türkçe cevap
üretiyor (bkz. Örnek 2).

### 2. Türkçe karakterlerde büyük/küçük harf duyarsız arama — bulundu ve çözüldü

**Sorun:** `basvuru_ara` ve `basvuru_listele` içindeki SQL sorgularında
kullanılan `COLLATE NOCASE`, SQLite'ta yalnızca ASCII harfleri (a-z)
case-fold ediyor; Türkçe'ye özgü **ş/Ş, ğ/Ğ, ü/Ü, ö/Ö, ç/Ç, ı/İ**
karakterlerini case-insensitive hâle getirmiyor. Örneğin veritabanında
`"PAŞA Bank"` kayıtlıyken, kullanıcı küçük harfle `"paşa"` diye arattığında
bu kayıt bulunamıyor; yalnızca tam büyük/küçük harf eşleşmesi veya ASCII
harflerden oluşan kelimeler (`"bank"` gibi) doğru çalışıyordu.

**Çözüm:** `db.py` içine, Türkçe'ye duyarlı küçük harfe çeviren bir Python
fonksiyonu (`turkce_kucuk_harf`) eklendi ve bu fonksiyon `TR_LOWER` adıyla
özel bir SQLite fonksiyonu olarak kaydedildi (`conn.create_function`).
Sorgularda `COLLATE NOCASE` yerine `TR_LOWER(sirket) LIKE TR_LOWER(?)`
kullanılarak Ş/ğ/ü/ö/ç/İ gibi harfler de artık doğru eşleşiyor.

**Doğrulama:** `"paşa"` ve `"öztürk"` gibi tamamen küçük harfli Türkçe
aramalar artık ilgili kayıtları (`"PAŞA Bank"`, `"Öztürk Yazılım"`) doğru
buluyor; eski davranışlar (büyük harf, ASCII kelimeler) da bozulmadan
çalışmaya devam ediyor.

---
