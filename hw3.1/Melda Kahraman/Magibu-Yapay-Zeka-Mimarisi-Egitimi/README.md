---
title: Kripto ve Doviz Tool Calling Asistani
colorFrom: blue
colorTo: green
sdk: gradio
app_file: app.py
pinned: false
---

# Kripto ve Doviz Tool Calling Asistani

Bu proje, bir Büyük Dil Modelinin (LLM) dış dunya veri kaynaklariyla (CoinGecko ve Frankfurter API) dinamik olarak etkilesime girmesini (Tool Calling / Function Calling) saglayan ReAct mimarisinde gelistirilmis bir uygulamadir. Sistem, Hugging Face Spaces uzerinde canlı olarak hizmet vermektedir.

---

## 1. Mimari ve Kullanilan Teknolojiler

- **Dil Modeli:** Qwen/Qwen2.5-72B-Instruct (Hugging Face Inference API uzerinden)
- **Kripto Veri Kaynagi:** CoinGecko Public API (Anlik kripto fiyat bilgileri)
- **Doviz Kuru Kaynagi:** Frankfurter Public API (Anlik reel doviz kurlari)
- **Kullanici Arayuzu:** Gradio (ChatInterface mimarisi)
- **Gelistirme Ortami:** Python 3.12, Google Colab, Hugging Face Spaces

---

## 2. Gelistirme Sureci ve Uygulanan Yaklasimlar

Proje gelistirme sürecinde modelin sadece metin uretmesi degil, karar mekanizmasi ile dogru mantiksal adimlari izlemesi hedeflenmistir.

1. **JSON Schema Tasarimi:** Modelin kullanabilecegi 3 temel fonksiyon (`get_crypto_price`, `convert_currency`, `calculate_crypto_purchase`) icin veri tiplerini ve zorunlu parametreleri belirten OpenAI/HF uyumlu JSON semalari hazirlanmistir.
2. **Multi-Turn (ReAct) Loop Mantigi:** Modelin ilk adimda tek bir yanit vermek yerine, aldigi veriye gore ikinci veya ucuncu adimlari (Turn 1, Turn 2) tetiklemesini saglayan dinamik bir fonksiyon cagirma dongusu kurulmustur.
3. **Trace Log (Arayuz Transparanligi):** Modelin arka planda hangi araclari, hangi parametrelerle cagirdigi ve API'lerden donen ham veriler arayuzde adim adim kullaniciya sunulmustur.
4. **Veri Tipi Guvenligi (Type Casting):** Model tarafindan sayisal parametrelerin metin (string) formatinda gonderilmesi durumuna karsin Python tarafindan float/int tip donusumleri eklenerek sistemin cokmesi engellenmistir.
5. **Güvenlik (Environment Variables):** API anahtarlarinin kod deposunda acikta kalmamasi icin Hugging Face Secrets mimarisi kullanilmistir.

---

## 3. Test Edilen Senaryolar ve Sistem Performansi

Sistemin kararliligini ve hata toleransini olcmek amaciyla 3 farkli kategoride test gerceklestirilmistir:

### Senaryo A: Cok Adimli Karma Istekler (Multi-Turn Testi)
- **Girdi:** *"5000 TL ile kac Bitcoin alabilirim ve bu kac USD eder?"*
- **Sistem Akisi:**
  - **Turn 1:** `get_crypto_price(coin_id='bitcoin', vs_currency='try')` cagrildi ve anlik TRY fiyati alindi. Ayni adimda `convert_currency(amount=5000, from_code='TRY', to_code='USD')` tetiklendi.
  - **Turn 2:** Ilk adimdan gelen verilerle `calculate_crypto_purchase(amount_fiat=5000, price_per_coin=...)` cagrilarak hassas kuseuratlarda coin miktari hesaplandi.
- **Sonuc:** Basarili. Model kendi kafasindan farazi hesap yapmadan tum verileri API ve fonksiyonlar vasitasiyla topladi.

### Senaryo B: Farkli Birim ve Coin Kombinasyonlari
- **Girdi:** *"1500 Euro ile kac Ethereum alabilirim ve bu miktar kac Sterlin (GBP) eder?"*
- **Sistem Akisi:**
  - **Turn 1:** `get_crypto_price(coin_id='ethereum', vs_currency='eur')` ve `convert_currency(amount=1500, from_code='EUR', to_code='GBP')` paralel cagrildi.
  - **Turn 2:** `calculate_crypto_purchase(amount_fiat=1500, price_per_coin=...)` ile bolme islemi yapildi.
- **Sonuc:** Basarili. Farkli birimler (EUR, GBP) ve farkli kripto varliklar sorunsuz islendi.

### Senaryo C: Negatif ve Hata Toleransi Testleri
- **Girdi 1 (Konu Disi Soru):** *"Fransa'nin baskenti neresidir?"*
  - **Sistem Akisi:** Model hicbir araci tetiklemeden (Turn olusturmadan) dogrudan genel bilgi cevabi verdi.
- **Girdi 2 (Olmayan Varlik Sorgusu):** *"100 Dolar ile kac adet Meldacoin alabilirim?"*
  - **Sistem Akisi:** `get_crypto_price(coin_id='meldacoin')` cagrildi. API'den donen hata cevabini okuyan model, kullaniciya boyle bir kripto paranin bulunmadigini belirten mantikli bir aciklama sundu.
- **Sonuc:** Basarili. Hata durumlarinda sistem cokmemis, zarif bir sekilde hata mesajini islemistir.

---

## 4. Calistirma Talimatlari

Lokal ortamda calistirmak icin:

```bash
git clone [https://huggingface.co/spaces/meldakahramann/kripto-tool-calling-demo](https://huggingface.co/spaces/meldakahramann/kripto-tool-calling-demo)
cd kripto-tool-calling-demo
pip install -r requirements.txt
python app.py