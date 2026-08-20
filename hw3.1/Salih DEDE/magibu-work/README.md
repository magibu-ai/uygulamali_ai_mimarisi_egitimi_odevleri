---
title: Tool Calling Karşılaştırması
emoji: 🛠️
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 6.21.0
app_file: app.py
pinned: false
short_description: Güçlü/zayıf model, araç açık/kapalı karşılaştırması
---

# Tool Calling Karşılaştırması

Magibu Ders5 ödevi: bir modelin dış veri kaynaklarıyla (Public API) **Tool Calling /
Function Calling** üzerinden etkileşime girmesini sağlayan, ve bunu Hugging Face
Spaces üzerinde canlıya alan bir sistem.

Tek bir soru üç ayrı yapılandırmaya aynı anda gönderilir ve sonuçlar canlı olarak
yan yana akar:

| Panel | Model | Araçlar | Amaç |
|---|---|---|---|
| **A** | güçlü model (`google/gemma-4-26b-a4b-it:nitro`) | açık | doğru araçları seçip çok turlu zincirle doğru cevap verir |
| **B** | aynı güçlü model | kapalı | güncel veriyi bilemediğini itiraf eder / tahmine gider |
| **C** | küçük model (`meta-llama/llama-3.1-8b-instruct`) | açık | araç çağırmayı dener ama tutarsız/hatalı sonuçlar üretir |

**A vs B** tool calling'in kattığı değeri, **A vs C** ise araç verilse bile model
kapasitesinin belirleyici olduğunu gösterir.

## Araçlar

| Araç | Sağlayıcı | Ne yapar |
|---|---|---|
| `hava_durumu` | Open-Meteo | Bir şehrin anlık hava durumu |
| `doviz_cevir` | Frankfurter / ECB | Güncel kurla para birimi çevrimi |
| `sicaklik_cevir` | yerel hesap | C/F/K sıcaklık çevrimi (zincirleme aracı) |
| `kripto_fiyat` | CoinGecko | Kripto para fiyatı ve 24s değişim |
| `wikipedia_ara` | Wikipedia | Ansiklopedik özet |
| `son_depremler` | USGS | Son depremler, büyüklüğe göre |

Her araç çağrısı için model tarafından üretilen argümanlar, API'den dönen ham
yanıt, süre ve durum (başarılı/hatalı) arayüzde canlı olarak gösterilir.

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
