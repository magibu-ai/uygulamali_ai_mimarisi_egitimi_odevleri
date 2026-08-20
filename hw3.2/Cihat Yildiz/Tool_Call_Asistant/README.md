# 🚚 LojistikAI — Kargo Sevkiyat Asistanı

Tool-calling destekli, **SQLite veritabanına hem okuma hem yazma** yapan kargo operasyon asistanı. Model kullanıcının isteğine göre uygun fonksiyonu çağırır; yanıtlar tamamen veritabanından dönen gerçek veriye dayanır.

Proje ayrıca sıfırdan yazılmış bir **Jinja2 chat template** içerir — rol sarmalama ve tool calling formatını tanımlar.

🔗 **Canlı demo:** [huggingface.co/spaces/cihatyldz/lojistik-kargo-asistani](https://huggingface.co/spaces/cihatyldz/lojistik-kargo-asistani)

---

## 📋 Senaryo

Bir kargo firmasının operasyon asistanı. Kullanıcı şunları yapabilir:

- Hizmet listesi ve fiyat sorgulama (kategoriye göre filtreleme)
- Yeni sevkiyat oluşturma — takip numarası üretilir, uygun araca atanır, **kapasiteden düşülür**
- Takip numarasıyla gönderi durumu sorgulama
- Sevkiyat durumu güncelleme — iptal/teslimde **araç kapasitesi serbest bırakılır**

Sistem ağırlık limiti aşımı, müsait araç bulunmaması ve geçersiz hizmet kodu gibi durumları veritabanı seviyesinde doğrular.

---

## 🧩 Mimari

```
                     Kullanıcı
                         │
                         ▼
                ┌─────────────────┐
                │     app.py      │  Gradio arayüzü
                │  (3 sekmeli UI) │  sohbet · tool log · prompt · DB
                └────────┬────────┘
                         ▼
                ┌─────────────────┐
                │    agent.py     │  tool calling döngüsü
                │                 │  prompt yönetimi (max 6 tur)
                └────────┬────────┘
                    ┌────┴────┐
                    ▼         ▼
          ┌──────────────┐  ┌──────────────────────┐
          │  tools.py    │  │ chat_template.jinja  │
          │ 4 fonksiyon  │  │ rol sarmalama +      │
          │ JSON Schema  │  │ tool call formatı    │
          └──────┬───────┘  └──────────────────────┘
                 ▼
          ┌──────────────┐
          │ database.py  │  SQLite
          │              │  hizmetler · araclar · siparisler
          └──────────────┘
```

| Dosya | Sorumluluk | Satır |
|-------|-----------|-------|
| `chat_template.jinja` | Rol sarmalama, tool call formatı | ~130 |
| `database.py` | SQLite şeması, CRUD, kapasite yönetimi | ~280 |
| `tools.py` | Araç fonksiyonları + JSON şemaları | ~220 |
| `agent.py` | Tool calling döngüsü, sistem promptu | ~200 |
| `app.py` | Gradio arayüzü | ~190 |

---

## 📝 Ödev 1: Custom Chat Template

`chat_template.jinja` dört rolü ayrı ayrı sarmalar. Araç şemaları sistem mesajının içine gömülür, tool call'lar ve sonuçları özel işaretlerle ayrılır.

| Rol | Sarmalama |
|-----|-----------|
| `system` | `<\|im_start\|>system` … `<\|im_end\|>` (+ araç şemaları) |
| `user` | `<\|im_start\|>user` … `<\|im_end\|>` |
| `assistant` | `<\|im_start\|>assistant` … `<\|tool_call\|>{…}<\|/tool_call\|>` … `<\|im_end\|>` |
| `tool` | `<\|im_start\|>tool` `<\|tool_response\|>{…}<\|/tool_response\|>` `<\|im_end\|>` |

### Üretilen prompt (gerçek çıktı)

```text
<|im_start|>system
Sen LojistikAI'sın.

# Kullanılabilir Araçlar

Aşağıdaki araçları kullanabilirsin. Bir aracı çağırmak için şu formatı kullan:
<|tool_call|>{"name": "araç_adı", "arguments": {"parametre": "değer"}}<|/tool_call|>

Araç tanımları (JSON Schema):
{"name": "get_services", "description": "Kargo hizmetlerini listeler",
 "parameters": {"type": "object", "properties": {"kategori": {"type": "string"}},
 "required": []}}

Önemli: Yanıtlarını yalnızca araçlardan dönen gerçek veriye dayandır.
Veritabanında olmayan bir bilgiyi varmış gibi sunma.<|im_end|>
<|im_start|>user
Özel hizmetleri göster<|im_end|>
<|im_start|>assistant
<|tool_call|>{"name": "get_services", "arguments": {"kategori": "ozel"}}<|/tool_call|><|im_end|>
<|im_start|>tool
[get_services] <|tool_response|>{"hizmet_sayisi": 2, "hizmetler": [{"kod": "SGK"},
{"kod": "KRM"}]}<|/tool_response|><|im_end|>
<|im_start|>assistant
Soğuk zincir ve kırılabilir eşya hizmetlerimiz var.<|im_end|>
<|im_start|>user
Sevkiyat oluşturmak istiyorum<|im_end|>
<|im_start|>assistant
```

### Hata yönetimi

Şablon tanımsız rol geldiğinde `raise_exception` ile durur:

```text
✓ Geçersiz rol yakalandı:
  Desteklenmeyen rol: hacker. Geçerli roller: system, user, assistant, tool
```

Sistem mesajı verilmezse varsayılan bir sistem mesajı üretir:

```text
<|im_start|>system
Sen LojistikAI'sın — kargo ve sevkiyat işlemlerinde yardımcı olan bir asistansın.<|im_end|>
<|im_start|>user
Merhaba<|im_end|>
<|im_start|>assistant
```

Arayüzdeki **📝 Chat Template** sekmesinde her mesaj için formatlanmış prompt canlı görüntülenir.

---

## 🗄 Veritabanı

```sql
hizmetler (kod, ad, kategori, birim_fiyat, max_agirlik_kg, teslim_gun, aktif)
araclar   (plaka, tip, kapasite_kg, dolu_kg, sehir)
siparisler(takip_no, hizmet_kod, gonderici, alici, cikis_sehir, varis_sehir,
           agirlik_kg, tutar, durum, olusturma, tahmini_teslim, arac_plaka)
```

### Başlangıç verisi

```text
HİZMETLER
  EKS: Ekspres Kargo          18.5 TL/kg  max     30 kg
  STD: Standart Kargo          9.0 TL/kg  max     30 kg
  EKO: Ekonomik Kargo          6.5 TL/kg  max     50 kg
  PLT: Palet Taşıma            4.2 TL/kg  max   1200 kg
  SGK: Soğuk Zincir           28.0 TL/kg  max    200 kg
  KRM: Kırılabilir Eşya       22.0 TL/kg  max     40 kg
  ULS: Uluslararası Kargo     45.0 TL/kg  max    100 kg

ARAÇLAR
  34 LJ 1001  İstanbul         0/1500    kg
  34 LJ 1002  İstanbul       320/1500    kg
  06 LJ 2001  Ankara        1200/8000    kg
  35 LJ 3001  İzmir            0/1500    kg
  33 LJ 4001  Mersin        8400/22000   kg
```

---

## 🔧 Araçlar

| Araç | Açıklama | DB İşlemi |
|------|----------|-----------|
| `get_services(kategori?)` | Hizmet ve fiyat listesi | SELECT |
| `create_shipment(...)` | Sevkiyat kaydı + araç ataması | INSERT + UPDATE |
| `track_shipment(takip_no)` | Durum sorgulama | SELECT (JOIN) |
| `update_shipment_status(...)` | Durum güncelleme + kapasite iadesi | UPDATE |

---

## 💬 Örnek Akışlar (gerçek çıktılar)

### 1) Hizmet listesi — okuma

**Kullanıcı:** *"Hangi kargo hizmetleri var, fiyatları nedir?"*

```text
[Turn 1] Araç Çağrıları:
   -> get_services()
   <- {"hizmet_sayisi": 7, "hizmetler": [{"kod": "PLT", "ad": "Palet Taşıma",
       "kategori": "agir", "birim_fiyat_tl_kg": 4.2, "max_agirlik_kg": 1200.0,
       "teslim_suresi_gun": 4}, {"kod": "EKO", ...}]}

[Turn 2] Nihai yanıt üretildi.

YANIT:
Mevcut kargo hizmetleri ve fiyatları aşağıdaki gibidir:
1. Palet Taşıma (PLT) — 4.2 TL/kg, max 1200 kg, 4 gün
2. Ekonomik Kargo (EKO) — 6.5 TL/kg, max 50 kg, 5 gün
...
```

### 2) Sevkiyat oluşturma — DB'ye yazma

```text
   -> create_shipment(hizmet_kod='EKS', gonderici='Ege Tekstil',
                      alici='Anadolu Market', cikis_sehir='İstanbul',
                      varis_sehir='Ankara', agirlik_kg=15.5)
   <- {
        "takip_no": "LJ2608VIJA",
        "hizmet": "Ekspres Kargo",
        "guzergah": "İstanbul → Ankara",
        "agirlik_kg": 15.5,
        "tutar_tl": 286.75,
        "durum": "hazirlaniyor",
        "tahmini_teslim": "2026-08-05",
        "atanan_arac": "34 LJ 1002"
      }
```

Araç kapasitesi otomatik güncellenir:

```text
34 LJ 1002:  320.0 → 335.5 / 1500.0 kg
```

### 3) Halüsinasyon engelleme — olmayan kayıt

**Kullanıcı:** *"SAHTE999 numaralı kargom nerede?"*

```text
[Turn 1] Araç Çağrıları:
   -> track_shipment(takip_no='SAHTE999')
   <- {"hata": "'SAHTE999' takip numaralı sevkiyat bulunamadı"}

[Turn 2] Nihai yanıt üretildi.

YANIT:
'SAHTE999' takip numaralı sevkiyat bulunamadı. Lütfen takip numarasını
kontrol edin veya başka bir numara ile tekrar deneyin.
```

Model kayıt uydurmuyor, bulunamadığını açıkça bildiriyor.

### 4) İş kuralı doğrulama — ağırlık limiti

**Kullanıcı:** *"İstanbul'dan Ankara'ya 500 kg ekspres gönderi oluştur."*

```text
[Turn 1] Araç Çağrıları:
   -> get_services()
   <- {"hizmet_sayisi": 7, "hizmetler": [...]}

[Turn 2] Nihai yanıt üretildi.

YANIT:
Ekspres gönderi için uygun hizmet kodu "EKS"dir. Ancak bu hizmetin maksimum
ağırlığı 30 kg'dır. 500 kg'lık bir gönderi için bu hizmeti kullanamam.

Alternatif olarak "Palet Taşıma" hizmetini kullanabiliriz. Bu hizmetin
maksimum ağırlığı 1200 kg'dır. Devam edelim mi?
```

Model önce hizmet listesini çekiyor, limiti kontrol ediyor ve veritabanında **gerçekten var olan** bir alternatif öneriyor.

### 5) Durum güncelleme — kapasite iadesi

```text
  yolda   → {'takip_no': 'LJ2608VIJA', 'onceki_durum': 'hazirlaniyor', 'yeni_durum': 'yolda'}
  iptal   → {'takip_no': 'LJ2608VIJA', 'onceki_durum': 'yolda', 'yeni_durum': 'iptal'}

Kapasite serbest bırakıldı mı?
  34 LJ 1002: 320.0 kg      ← 335.5'ten geri döndü
```

---

## 🛡 Halüsinasyon Engelleme

Üç katmanlı koruma uygulanmıştır.

**Sistem promptu seviyesinde** — model fiyat, hizmet veya kayıt bilgisi verirken araç çağırmak zorunda; eksik parametreyi kendi doldurmak yerine kullanıcıya sorması isteniyor:

```text
1. Fiyat, hizmet, takip numarası veya sevkiyat bilgisi verirken MUTLAKA
   ilgili aracı çağır. Hiçbir koşulda kendi bilginle fiyat veya hizmet uydurma.
2. Araç bir kayıt bulamazsa ("hata" alanı dönerse), bunu kullanıcıya açıkça
   söyle. Var gibi davranma, alternatif uydurma.
3. Sevkiyat oluşturmak için gereken bilgilerden biri eksikse ÖNCE kullanıcıya sor.
```

**Araç seviyesinde** — bulunamayan kayıtlar boş liste değil `{"hata": …}` döndürür. Doğrulama testleri:

```text
1) Olmayan takip numarası:
   {'hata': "'SAHTE999' takip numaralı sevkiyat bulunamadı"}

2) Ağırlık limiti aşımı:
   {'hata': 'Ekspres Kargo için maksimum ağırlık 30.0 kg, siz 500.0 kg girdiniz'}

3) Olmayan hizmet kodu:
   {'hata': "'XYZ' kodlu hizmet bulunamadı"}

4) Müsait araç olmayan şehir:
   {'hata': 'Erzurum şehrinde 900.0 kg için müsait araç yok'}

5) Geçersiz durum:
   {'hata': 'Geçersiz durum. Seçenekler: hazirlaniyor, yolda, dagitimda,
             teslim_edildi, iptal'}
```

**Şablon seviyesinde** — sistem mesajının sonuna otomatik olarak *"Yanıtlarını yalnızca araçlardan dönen gerçek veriye dayandır"* kuralı eklenir.

---

## 🚀 Yerelde Çalıştırma

```bash
git clone https://github.com/<kullanici>/lojistik-kargo-asistani.git
cd lojistik-kargo-asistani

pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
python app.py
```

Arayüz `http://localhost:7860` adresinde açılır. Veritabanı (`lojistik.db`) ilk çalıştırmada otomatik oluşturulur.

### Veritabanını sıfırlama

```python
import database as db
db.veritabani_kur(sifirla=True)
```

### Farklı model kullanma

```bash
export LOJISTIK_MODEL="gpt-4o"
python app.py
```

### Notebook ile

`chat_template_ve_agent.ipynb` dosyası tüm geliştirme sürecini içerir: şablon yazımı ve testi, veritabanı kurulumu, araç testleri, tool calling testleri, Gradio arayüzü ve Space'e yayınlama. Colab'da açıp Secrets bölümüne `OPENAI_API_KEY` ve `HF_TOKEN` eklemek yeterlidir.

---

## ☁️ Hugging Face Spaces

> **Not:** Hugging Face artık Gradio Space'lerin ücretsiz `cpu-basic` üzerinde oluşturulmasına izin vermiyor — Static Space'ler herkese açık, Gradio ve Docker için PRO gerekiyor. Ücretsiz kişisel hesaplar ZeroGPU üzerinde 2 adede kadar Gradio Space barındırabiliyor. Bu proje `zero-a10g` ile yayınlanmıştır; uygulama GPU kullanmaz, `app.py` içindeki `@spaces.GPU` yer tutucusu yalnızca platform şartını karşılar.

```python
from huggingface_hub import create_repo, HfApi

SPACE_ID = "kullanici/lojistik-kargo-asistani"

create_repo(repo_id=SPACE_ID, repo_type="space",
            space_sdk="gradio", space_hardware="zero-a10g")

api = HfApi()
for f in ["app.py", "agent.py", "tools.py", "database.py",
          "chat_template.jinja", "requirements.txt", "README.md"]:
    api.upload_file(path_or_fileobj=f, path_in_repo=f,
                    repo_id=SPACE_ID, repo_type="space")

api.add_space_secret(repo_id=SPACE_ID, key="OPENAI_API_KEY", value="sk-...")
```

---

## ⚙️ Teknik Detaylar

| Konu | Değer |
|------|-------|
| Model | `gpt-4o-mini` (native function calling) |
| Veritabanı | SQLite (`lojistik.db`, otomatik oluşturulur) |
| Tool sayısı | 4 (2 okuma, 2 yazma) |
| Max tool turu | 6 |
| Sıcaklık | 0.2 (araç seçiminde tutarlılık) |
| Şablon motoru | Jinja2 |
| Gradio | 5 ve 6 uyumlu (sürüm tespiti ile) |

### Gradio 5 / 6 uyumluluğu

Gradio 6'da `Chatbot(type=...)` parametresi kaldırıldı. Kod her iki sürümde de çalışır:

```python
_chatbot_kwargs = {"label": "Sohbet", "height": 430}
if int(gr.__version__.split(".")[0]) < 6:
    _chatbot_kwargs["type"] = "messages"
chatbot = gr.Chatbot(**_chatbot_kwargs)
```

---

## 📁 Dosya Yapısı

```
├── chat_template_ve_agent.ipynb   # Uçtan uca notebook (geliştirme + yayınlama)
├── app.py                         # Gradio arayüzü
├── agent.py                       # Tool calling döngüsü + prompt yönetimi
├── tools.py                       # Araç fonksiyonları + JSON şemaları
├── database.py                    # SQLite katmanı
├── chat_template.jinja            # Özel Jinja2 chat template
├── requirements.txt
└── README.md
```

---

## 🔗 İlgili Çalışmalar

| Kaynak | Link |
|--------|------|
| Tool calling (public API) demosu | [`cihatyldz/lojistik-tool-calling`](https://huggingface.co/spaces/cihatyldz/lojistik-tool-calling) |
| Fine-tuned model (LoRA) | [`cihatyldz/lojistik-lora-adapter`](https://huggingface.co/cihatyldz/lojistik-lora-adapter) |
| Eğitim veri seti | [`cihatyldz/lojistik-soru-cevap`](https://huggingface.co/datasets/cihatyldz/lojistik-soru-cevap) |
| Özel benchmark | [`cihatyldz/lojistik-benchmark`](https://huggingface.co/datasets/cihatyldz/lojistik-benchmark) |

---

## 👤 Yazar

**Cihat Yıldız** — Kıdemli Veri Bilimcisi, Lojistik Sektörü
[Hugging Face](https://huggingface.co/cihatyldz)

## 📄 Lisans

MIT
