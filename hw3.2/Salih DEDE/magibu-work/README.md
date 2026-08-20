# THY Seyahat Asistanı

Magibu Ders6 ödevi. Fikir basit: kullanıcı gitmek istediği bir yeri söylüyor,
model tool-calling ile gerçek verilere bakıyor, uçuş buluyor, bilet kesiyor ve
gün gün bir gezi planı çıkarıyor.

🔗 **Canlı demo:** https://huggingface.co/spaces/SalihHub/thy-seyahat-asistani

TR'ye özel kurdum: tüm uçuşlar İstanbul'dan kalkıyor, sadece havalimanı olan
**48 il** varış noktası (Adana'dan Zonguldak'a). Uçuşlar sabit seed ile
rastgele üretiliyor (`db.py::_ucus_tohumu_uret`), her il için 1-3 uçuş,
1 ay içine yayılmış tarih/saat/fiyat/boş koltuk.

## Senaryo

> "Kapadokya'ya gitmek istiyorum, gün gün bir plan yapar mısın?"

1. `wikipedia_arastir` — mekanın hangi ilde olduğunu buluyor (Kapadokya → Nevşehir)
2. `ucus_ara` — o ile giden müsait THY uçuşlarını SQLite'tan getiriyor
3. Kullanıcı bir uçuş seçince `bilet_al` koltuğu düşürüyor, PNR üretiyor,
   bakiyeden düşüyor (gerekirse önce döviz çeviriyor)
4. Kısa bir tebrik + Wikipedia'dan öğrendiği gerçek bilgiyle gün gün gezi rotası

Bakiyeyi başta hangi para biriminde tutmak istediğini (TRY/EUR/USD/GBP)
kendin seçiyorsun. Bilet fiyatları DB'de her zaman TRY, `bilet_al` gerekli
kur çevrimini kendisi yapıyor. Ara sorular (bakiye, döviz, saat) da aynı
kutudan serbestçe sorulabiliyor.

Arayüzde her tool çağrısının girdi/çıktısını da açık şekilde gösteriyorum
(chat içindeki katlanabilir bloklar) — modelin "uydurmadığını", gerçekten
DB'den/API'den veri çektiğini görebiliyorsun.

## Mimari

| Dosya | Görev |
|---|---|
| `db.py` | SQLite uçuş kataloğu + bilet yazma (gerçek okuma/yazma burada) |
| `tools.py` | Araç şemaları ve gerçek uygulamaları |
| `app.py` | OpenRouter tool-calling döngüsü + Gradio arayüzü |

## Araçlar

| Araç | Tür | Kaynak | Ne yapıyor |
|---|---|---|---|
| `wikipedia_arastir` | okuma | Wikipedia API | Sorulan yer/eser hakkında özet bilgi çeker; model bununla hangi ilde olduğunu ve gezi rotasında nereleri önereceğini çıkarır. |
| `sehir_saat` | okuma | timeapi.io | Türkiye'nin güncel yerel tarih/saatini döner (tüm ülke tek dilimde: Europe/Istanbul). |
| `ucus_ara` | okuma | SQLite (`thy.db`) | Girilen ile giden, koltuğu dolmamış THY uçuşlarını (sefer no, tarih, saat, fiyat) listeler. |
| `doviz_cevir` | okuma | Frankfurter / ECB | Güncel kurla bir para birimini diğerine çevirir; `bilet_al` da bunu iç mekanizma olarak kullanıyor. |
| `bakiye_sorgula` | okuma | oturum durumu | Kullanıcının o oturumdaki güncel bakiyesini, kendi seçtiği para biriminde döner. |
| `bilet_al` | **yazma** | SQLite (`thy.db`) + oturum durumu | Seçilen uçuşun koltuğunu bir azaltır, PNR üretir, TRY fiyatı gerekirse kullanıcının para birimine çevirip bakiyeden düşer. |

Bakiye ve alınan biletler oturuma özel (`gr.State`) — her tarayıcı sekmesi
kendi seçtiği para birimi/tutarla başlıyor, kullanıcılar birbirini
etkilemiyor. Uçuş kataloğu ve koltuk sayıları herkes için ortak.

Sistem promptunda modele sadece araçlardan dönen veriyi kullanması,
DB'de olmayan bir uçuşu ya da bilgiyi asla uydurmaması söylendi.

## Karşılaştığım zorluklar

1. **THY entegrasyonu** — İlk planım gerçek THY MCP sunucusunu (Digital Lab'in
   deneysel projesi) kullanmaktı. Baktım ki erişim Miles&Smiles hesabı ve
   OAuth login gerektiriyor, yani anonim bir HF Space ziyaretçisi bunu hiç
   kullanamaz. Bunun yerine kendi SQLite veritabanımı kurdum: 1 aylık gerçekçi
   uçuş verisini (tarih, saat, fiyat, koltuk) rastgele ama tutarlı şekilde
   üretip THY API'sinin yerine koydum.

2. **HF Space ücretsiz kotası** — Hesabımda Gradio/Docker Space'i normal
   cpu-basic donanımla açmak PRO abonelik istiyor. Ücretsiz tek seçenek
   ZeroGPU donanımıydı, ama ZeroGPU çalışma zamanı başlarken en az bir
   `@spaces.GPU` fonksiyonu görmek istiyor, yoksa Space'i hiç ayağa
   kaldırmıyor. Ben projede hiç GPU kullanmıyorum (her şey OpenRouter
   üzerinden API çağrısı), o yüzden gerçek iş yapmayan, sadece `True`
   dönen boş bir fonksiyonu `@spaces.GPU` ile işaretleyip "kandırdım" —
   işe yaradı, Space ZeroGPU donanımında ücretsiz çalışıyor.

## Yerel çalıştırma

```bash
pip install -r requirements.txt
cp .env.example .env   # OPENROUTER_API_KEY değerini doldurun
python3 app.py
```

## Ortam değişkenleri

`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` — Hugging Face
Spaces üzerinde *Settings → Repository secrets* kısmından ayarlanır; yerelde
`.env` dosyasından okunur.
