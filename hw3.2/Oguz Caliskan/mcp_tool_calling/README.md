---
title: Sondaj Depo Asistanı
emoji: 📦
colorFrom: blue
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
---

# Sondaj Malzeme Depo Yönetim Asistanı

## Senaryo Özeti

Sahadaki mühendislerin, sondaj malzeme/ekipman deposuyla **doğal dilde** etkileşime girebildiği bir tool-calling asistanı. Kullanıcı "9 5/8 casing stokta var mı?" gibi bir soru sorduğunda, model gerçek bir SQLite veritabanını sorgulayıp cevap veriyor; "SABUN-12 için 5 adet centralizer talep et" dediğinde ise gerçek bir talep kaydı oluşturup stoktan düşüyor.

**Neden bu senaryo?** Proje, aynı ekibin daha önce sondaj günlük raporlarına özel fine-tune ettiği "Sondaj Modeli"ni temel alıyor — depo/malzeme takibi, o modelin zaten aşina olduğu operasyonel bağlamla (raporlardaki "X adet malzeme teslim alındı" gibi ifadeler) doğal bir devamlılık sağlıyor.

## Model ve Mimari

- **Model:** `Qwen/Qwen3-8B` (public, fine-tune edilmemiş base model). Ekibin daha önce sondaj raporları için fine-tune ettiği "Sondaj Modeli" ilk denendi, ama domain-özel eğitiminin çok güçlü olması nedeniyle bu genel amaçlı depo görevinde kendi sondaj/kuyu bağlamına "kilitlenip" var olmayan fonksiyon adları uydurduğu (halüsinasyon) gözlendi - bu yüzden tool-calling için daha güvenilir olan base Qwen3-8B'ye geçildi.
- **Çıkarım:** `transformers` (`AutoModelForCausalLM` + `AutoTokenizer`), ZeroGPU üzerinde
- **Tool-calling:** Modelin kendi chat template'i (`apply_chat_template(..., tools=...)`) ile `<tool_call>` formatında üretim; agent loop bunu ayrıştırıp gerçek Python fonksiyonlarını çalıştırır, sonucu tekrar modele besler (maks. 5 tur)
- **Veritabanı:** SQLite (`depo.db`), iki tablo: `malzeme` (envanter) ve `talep` (kuyu bazlı talepler)

### Kod Mimarisi (modüler)

```
mcp_sondaj_depo/
├── db.py          # SQLite bağlantısı, tablo şeması, örnek veri
├── tools.py        # 3 tool fonksiyonu + JSON şemaları (model bunları çağırır)
├── app.py          # Gradio arayüzü + model yükleme + agent loop
├── requirements.txt
└── README.md
```

### Fonksiyonlar (Tool'lar)

| Fonksiyon | Tür | Açıklama |
|---|---|---|
| `get_stok_durumu(malzeme_adi)` | Okuma | Depodaki bir malzemenin stok miktarını/lokasyonunu sorgular |
| `malzeme_talep_olustur(malzeme_adi, adet, kuyu_adi)` | Yazma | Yeni bir talep kaydı oluşturur, stoktan düşer |
| `talep_durumu_sorgula(talep_id)` | Okuma | Bir talebin güncel durumunu sorgular |

### Halüsinasyon Engelleme

- `SYSTEM_PROMPT`, modele veritabanında olmayan bilgiyi **asla uydurmamasını** açıkça talimatlandırıyor.
- Tüm cevaplar, tool fonksiyonlarının **gerçek SQLite sorgu sonucuna** dayanıyor — model kendi başına stok sayısı/talep durumu "hesaplamıyor", sadece tool sonucunu doğal dile çeviriyor.
- `malzeme_talep_olustur`, veritabanında tam olarak eşleşen bir malzeme adı bulamazsa (halüsinasyon riski taşıyan bir senaryo) açık bir hata döner, işlemi gerçekleştirmez.

## Yerelde Çalıştırma

```bash
git clone <bu-repo>
cd mcp_sondaj_depo
pip install -r requirements.txt
export HF_TOKEN=<yazma/okuma izinli token>   # Windows: set HF_TOKEN=...
python app.py
```

Not: `AutoModelForCausalLM` GPU olmadan (`ZeroGPU` dekoratörü Space dışında etkisizdir) CPU'da da çalışır, ama yavaş olur.

## Hugging Face Space (Canlı Demo)

**Demo linki:** _(Space'i oluşturup dosyaları yükledikten sonra buraya eklenecek)_

## Örnek Kullanım

**Kullanıcı girdisi:**
> "9 5/8 casing stokta var mı?"

**Arka planda tetiklenen tool-call (terminal/log çıktısı):**
```
[TOOL CALL] get_stok_durumu({'malzeme_adi': '9 5/8 casing'}) -> '9 5/8" Casing' için 1 sonuç bulundu:
- 9 5/8" Casing (Casing): 120 adet - Batman Depo
```

**Kullanıcı girdisi:**
> "SABUN-12 kuyusu için 5 adet 9 5/8 centralizer talep et"

**Arka planda tetiklenen tool-call:**
```
[TOOL CALL] malzeme_talep_olustur({'malzeme_adi': '9 5/8" Centralizer', 'adet': 5, 'kuyu_adi': 'SABUN-12'}) -> Talep oluşturuldu (Talep ID: 1). 5 adet '9 5/8" Centralizer', SABUN-12 kuyusu için talep edildi. Durum: Onay Bekliyor. Kalan stok: 55 adet.
```

## Bilinen Sınırlamalar

- Modelin fine-tune verisi tool-calling örnekleri içermiyordu; bu yetenek base Qwen3 modelinden kalan genel kapasiteye dayanır, %100 garanti edilmez.
- `do_sample=True` (temperature=0.3) kullanılıyor; düşük ama sıfır olmayan rastgelelik var.
- Bileşik sorular ("hem X'i sorgula hem Y talep et") güvenilirliği düşürebilir; ayrı sorular önerilir.