---
title: Uçuş Rezervasyon Asistanı
emoji: ✈️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.21.0
app_file: app.py
pinned: false
license: mit
short_description: SQLite veritabanli tool-calling ucus rezervasyon asistani
---

# ✈️ Uçuş Rezervasyon Asistanı

Bir dil modelinin **veritabanına erişip işlem yapabildiği** (tool calling)
rezervasyon sistemi. Model kullanıcının isteğine göre uygun aracı seçer,
SQLite veritabanından gerçek veriyi okur ve rezervasyon oluştururken
**veritabanına yazar**: kayıt eklenir ve seferin boş koltuk sayısı düşer.

## Senaryo

Kullanıcı uçuş arar, bulunan seferlerden birine bilet alır ve rezervasyonunu
PNR kodu ile sorgular. Sistemin verdiği her bilgi (uçuş, fiyat, koltuk, PNR)
veritabanından gelir; model bilgi uydurmaz.

## Araçlar

| Araç | Tür | İşlevi |
|---|---|---|
| `search_flights` | okuma | Kalkış, varış ve tarihe göre boş koltuğu olan seferleri listeler |
| `book_ticket` | **yazma** | Rezervasyon oluşturur, PNR üretir ve boş koltuk sayısını düşürür |
| `check_booking` | okuma | PNR kodu ile rezervasyon bilgilerini getirir |

## Mimari

Katmanlı ve modüler bir yapı kullanılmıştır; her dosyanın tek bir sorumluluğu
vardır.

```
app.py        Gradio arayüzü — iş mantığı içermez
   ↓
agent.py      Model çağrısı, araç döngüsü, konuşma hafızası
   ↓
tools.py      Araç fonksiyonları ve JSON şemaları, girdi doğrulama
   ↓
database.py   SQLite işlemleri, transaction yönetimi
```

Bu ayrım sayesinde arayüz, model veya veritabanı bağımsız olarak
değiştirilebilir.

**Model:** `Qwen/Qwen2.5-72B-Instruct`, Hugging Face Inference Providers
üzerinden (OpenAI uyumlu API) çağrılır. Bu sayede uygulamanın çalıştığı
ortamda GPU gerekmez.

## Veritabanı şeması

**seferler**

| Sütun | Tip | Açıklama |
|---|---|---|
| `id` | INTEGER | Birincil anahtar |
| `ucus_kodu` | TEXT | Benzersiz uçuş kodu |
| `firma`, `kalkis`, `varis` | TEXT | Uçuş bilgileri |
| `tarih`, `kalkis_saati`, `varis_saati` | TEXT | Zaman bilgileri |
| `fiyat` | REAL | Kişi başı ücret |
| `bos_koltuk` | INTEGER | `CHECK (bos_koltuk >= 0)` |

**rezervasyonlar**

| Sütun | Tip | Açıklama |
|---|---|---|
| `pnr` | TEXT | Birincil anahtar, 6 karakterlik kod |
| `sefer_id` | INTEGER | `FOREIGN KEY → seferler(id)` |
| `yolcu_adi`, `koltuk_sayisi`, `toplam_fiyat` | — | Rezervasyon detayları |
| `durum`, `olusturma_tarihi` | TEXT | Kayıt bilgileri |

Uygulama ilk çalıştığında 28 örnek sefer otomatik oluşturulur.

### İşlem bütünlüğü (transaction)

Rezervasyon sırasında iki işlem yapılır: kayıt eklenir ve boş koltuk düşürülür.
Bu işlemler tek bir transaction içinde yürütülür; biri başarısız olursa
`ROLLBACK` ile hepsi geri alınır. Aksi hâlde aynı koltuk iki kez satılabilir
veya koltuk sayısı hatalı kalabilirdi.

## Halüsinasyon engelleme

Model veritabanında olmayan bir uçuşu varmış gibi sunamaz. Üç katmanlı bir
savunma uygulanmıştır:

**1. Sistem mesajı (`agent.py`)** — Modele, verdiği her bilginin araç
çıktısına dayanması gerektiği ve `sefer_id` değerini mutlaka arama sonucundan
alması gerektiği açıkça bildirilir.

**2. Araç doğrulaması (`tools.py`)** — Sefer var mı, koltuk yeterli mi, girdiler
geçerli mi denetlenir. Hata durumunda modele yönlendirici bir mesaj döner:

```json
{
  "basarili": false,
  "hata": "8888 numaralı sefer bulunamadı.",
  "oneri": "Geçerli bir sefer_id için önce search_flights aracını kullan."
}
```

Model bu mesajı okuyup kendini düzeltebilir.

**3. Veritabanı kısıtları (`database.py`)** — `FOREIGN KEY` sayesinde var
olmayan bir sefere rezervasyon eklenemez; `CHECK (bos_koltuk >= 0)` koltuk
sayısının eksiye düşmesini engeller.

Ayrıca arama sonuç döndürmediğinde modele açıkça *"sefer uydurma"* bilgisi
iletilir; boş sonuç bir hata olarak değil, bildirilmesi gereken bir durum
olarak ele alınır.

## Örnek çalışma akışı

**Kullanıcı:** *"İstanbul'dan Ankara'ya uçuş bul"*

```
[Tur 1] Araç çağrıları:
   -> search_flights(kalkis='İstanbul', varis='Ankara')
   <- {"sonuc_sayisi": 4, "seferler": [
        {"sefer_id": 21, "ucus_kodu": "IS1964", "firma": "Ege Air",
         "kalkis": "İstanbul", "varis": "Ankara", "tarih": "2026-08-05",
         "kalkis_saati": "06:30", "fiyat_tl": 1087.37, "bos_koltuk": 15}, ...]}

[Tur 2] Nihai yanıt:
İstanbul-Ankara arası 4 uçuş buldum. En ucuzu IS1964, 1.087 TL.
```

**Kullanıcı:** *"Ona Mustafa Türk adına 2 kişilik bilet al"*

```
[Tur 1] Araç çağrıları:
   -> book_ticket(sefer_id=21, yolcu_adi='Mustafa Türk', koltuk_sayisi=2)
   <- {"basarili": true, "rezervasyon": {
        "pnr": "QNSL1X", "ucus_kodu": "IS1964", "firma": "Ege Air",
        "kalkis": "İstanbul", "varis": "Ankara", "tarih": "2026-08-05",
        "yolcu_adi": "Mustafa Türk", "koltuk_sayisi": 2,
        "toplam_fiyat": 2174.74, "kalan_koltuk": 13}}

[Tur 2] Nihai yanıt:
Rezervasyon tamamlandı. PNR kodunuz: QNSL1X
```

Veritabanı durumu bu işlem sonrasında değişir:

```
Önce  : 28 sefer · 682 boş koltuk · 0 rezervasyon
Sonra : 28 sefer · 680 boş koltuk · 1 rezervasyon
```

İkinci istekte kullanıcı *"ona"* diyerek önceki turdaki uçuşa atıf yapmıştır;
model bunu konuşma hafızası sayesinde anlar.

### Halüsinasyon denemesi

Model uydurma bir `sefer_id` gönderdiğinde:

```
[Tur 1] -> book_ticket(sefer_id=777, yolcu_adi='Test Kişi')
        <- {"basarili": false, "hata": "777 numaralı sefer bulunamadı.",
            "oneri": "Geçerli bir sefer_id için önce search_flights aracını kullan."}

[Tur 2] -> search_flights(kalkis='İzmir')      ← model kendini düzeltti
        <- {"sonuc_sayisi": 0, "seferler": [],
            "bilgi": "Bu kriterlere uyan sefer bulunamadı... sefer uydurma."}
```

İşlem reddedilir, veritabanı değişmez ve model doğru yola yönlendirilir.

## Yerelde çalıştırma

```bash
git clone <depo-adresi>
cd <klasör>

pip install -r requirements.txt

export HF_TOKEN=hf_...          # Windows: set HF_TOKEN=hf_...
python app.py
```

Uygulama `http://127.0.0.1:7860` adresinde açılır. Veritabanı (`ucus.db`) ilk
çalıştırmada otomatik oluşturulur ve örnek seferlerle doldurulur.

Veritabanını sıfırlamak için `ucus.db` dosyasını silmek yeterlidir.

### Ortam değişkenleri

| Değişken | Açıklama |
|---|---|
| `HF_TOKEN` | Hugging Face erişim anahtarı (zorunlu) |
| `MODEL_ADI` | Kullanılacak model (varsayılan `Qwen/Qwen2.5-72B-Instruct`) |
| `DB_YOLU` | Veritabanı dosya yolu (varsayılan `ucus.db`) |

Seçilecek modelin function calling desteklemesi gerekir:
<https://huggingface.co/inference-providers/models>

## Hugging Face Spaces üzerinde

Space oluşturulduktan sonra erişim anahtarı tanımlanmalıdır:

**Settings → Variables and secrets → New secret**

| Alan | Değer |
|---|---|
| Name | `HF_TOKEN` |
| Value | Hugging Face erişim anahtarı |

Secret eklendikten sonra **Settings → Restart this Space** ile yeniden
başlatılmalıdır.

**Canlı demo:** `<SPACE_LINKI>`

> Not: Spaces ortamında veritabanı geçicidir; Space yeniden başlatıldığında
> örnek verilerle sıfırlanır.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `app.py` | Gradio arayüzü |
| `agent.py` | Model çağrısı, araç döngüsü, konuşma hafızası |
| `tools.py` | Araç fonksiyonları ve JSON şemaları |
| `database.py` | SQLite işlemleri ve şema |
| `requirements.txt` | Bağımlılıklar |

## Sınırlamalar

Model en fazla 6 tur araç çağrısı yapabilir; bu sınır sonsuz döngüyü önlemek
içindir.

Rezervasyon iptali bulunmamaktadır; sistem yalnızca arama, rezervasyon ve
sorgulama işlemlerini kapsar.

Bu bir eğitim projesidir; gerçek bilet satışı yapılmaz.

## Lisans

MIT
