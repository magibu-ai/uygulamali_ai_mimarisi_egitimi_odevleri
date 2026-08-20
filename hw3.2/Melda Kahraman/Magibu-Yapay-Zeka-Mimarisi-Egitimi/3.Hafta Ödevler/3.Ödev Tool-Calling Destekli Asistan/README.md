---
title: Çizgi Roman Diyarı Asistanı
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.22.0
app_file: app.py
pinned: false
---

#  Çizgi Roman Diyarı - Tool-Calling Destekli LLM Asistanı

Bu proje, bir dil modelinin (LLM) dış veritabanı (SQLite) ile entegre olarak gerçek zamanlı veri okuma ve yazma işlemlerini (**Tool Calling / Function Calling**) gerçekleştirdiği uçtan uca bir asistandır.

Proje 2 ana ödev bileşeninden oluşmaktadır:
1. **Custom Chat Template (Jinja2):** LLM'in `user`, `system`, `assistant` ve `tool` rollerini doğru ayırt edebilmesi için özel yazılmış şablon.
2. **Tool-Calling Destekli Asistan:** SQLite veritabanına bağlı, halüsinasyonları engellenmiş çizgi roman stok ve sipariş asistanı.

---

##  Proje Bağlantıları (Teslimat Linkleri)

- **Hugging Face Space (Canlı Demo):** [meldakahramann/comic-store-assistant](https://huggingface.co/spaces/meldakahramann/comic-store-assistant)

---

##  Mimari ve Teknik Detaylar

- **Model:** `meta-llama/Llama-3.3-70B-Instruct` (Hugging Face Inference API üzerinden)
- **Arayüz (UI):** Gradio (Python)
- **Veritabanı:** SQLite3 (`comic_store.db`)
- **Şablon Yapısı:** Jinja2 (ChatML + Multi-Tool Calling Desteği)

### Entegre Edilen Fonksiyonlar (Tools)
1. `get_comics_catalog()`: Mağazadaki tüm ürünleri, fiyat ve stok bilgisiyle getirir (*Veri Okuma*).
2. `search_comic(query)`: Çizgi roman adı veya yayıncıya göre veritabanında arama yapar (*Veri Okuma*).
3. `create_order(comic_id, quantity, customer_name)`: Stok kontrolü yaparak siparişi `orders` tablosuna kaydeder ve `comics` tablosundaki stoğu günceller (*Veri Yazma*).

---

##  Halüsinasyon Engelleme & Stok Kontrolü

Sistem, modelin kafasına göre yanıt üretmesini engellemek için **Multi-step Tool Execution** döngüsüyle tasarlanmıştır:
* Kullanıcı bir sipariş verdiğinde model **önce** `search_comic` fonksiyonunu çalıştırıp veritabanından güncel stok durumunu okur.
* Eğer ürün veritabanında yoksa veya `stock: 0` ise model uydurma bir sipariş onayı vermez; veritabanından dönen gerçek bilgiye dayanarak siparişi reddeder.

---


##  Ekran Görüntüleri

### 1. Canlı Gradio Sohbet Ekranı
Aşağıdaki görselde asistanın veritabanını sorgulayarak stoktaki Marvel çizgi romanlarını doğru fiyat ve stok miktarıyla listelediği canlı arayüz görülmektedir:

![Ekran görüntüsü 2026-08-02 140202](https://cdn-uploads.huggingface.co/production/uploads/6a22ec7676260163a19216c1/HDhK-JVxwbVOgKr94YD8X.png)


### 2. Başlangıç Ekranı ve Örnek İstekler
Uygulamanın kullanıcıyı karşıladığı arayüz ve hızlı test seçenekleri:

![Ekran görüntüsü 2026-08-02 140252](https://cdn-uploads.huggingface.co/production/uploads/6a22ec7676260163a19216c1/_vQp3jwPwMOL9z9SL6glM.png)

---
##  Arka Plan Tool-Call Terminal / Log Çıktıları

Aşağıdaki log çıktısı, modelin kullanıcı taleplerini analiz edip arka planda fonksiyonları nasıl tetiklediğini ve veritabanı çıktılarına göre yanıt ürettiğini göstermektedir:

```text
==================================================
Kullanici: Merhaba, mağazadaki Marvel çizgi romanları nelerdir?
[TOOL CALL] Model Fonksiyon Tetikledi: 'search_comic' | Parametreler: {'query': 'Marvel'}
[TOOL OUTPUT] Veritabani Yaniti: [{"id": 1, "title": "Spider-Man: Blue", "publisher": "Marvel", "price": "150.0 TL", "stock": 9}, {"id": 7, "title": "X-Men: Dark Phoenix Saga", "publisher": "Marvel", "price": "210.0 TL", "stock": 2}]
Asistan: Mağazamızda Marvel çizgi romanları olarak "Spider-Man: Blue" ve "X-Men: Dark Phoenix Saga" bulunmaktadır. "Spider-Man: Blue" 150.0 TL fiyatla 9 adet stokta mevcut iken, "X-Men: Dark Phoenix Saga" 210.0 TL fiyatla 2 adet stokta mevcuttur.

==================================================
Kullanici: Spider-Man: Blue çizgi romanından 2 adet sipariş vermek istiyorum. Adım Melda Kahraman.
[TOOL CALL] Model Fonksiyon Tetikledi: 'search_comic' | Parametreler: {'query': 'Spider-Man: Blue'}
[TOOL OUTPUT] Veritabani Yaniti: [{"id": 1, "title": "Spider-Man: Blue", "publisher": "Marvel", "price": "150.0 TL", "stock": 9}]
[TOOL CALL] Model Fonksiyon Tetikledi: 'create_order' | Parametreler: {'customer_name': 'Melda Kahraman', 'comic_id': 1, 'quantity': 2}
[TOOL OUTPUT] Veritabani Yaniti: {"status": "Başarılı", "order_id": 2, "customer_name": "Melda Kahraman", "comic_title": "Spider-Man: Blue", "quantity": 2, "total_price": "300.0 TL", "remaining_stock": 7}
Asistan: Siparişiniz başarıyla oluşturuldu. Sipariş numaranız 2. Toplam tutar: 300.0 TL.

==================================================
Kullanici: Akira Vol. 1 kitabından 1 adet sipariş vermek istiyorum. Adım Melda.
[TOOL CALL] Model Fonksiyon Tetikledi: 'search_comic' | Parametreler: {'query': 'Akira Vol. 1'}
[TOOL OUTPUT] Veritabani Yaniti: [{"id": 6, "title": "Akira Vol. 1", "publisher": "Kodansha", "price": "450.0 TL", "stock": 0}]
Asistan: Merhaba Melda, maalesef Akira Vol. 1 kitabımız stokta bulunmamaktadır. Sipariş oluşturamıyorum.
```
---
##  Projeyi Yerelde Çalıştırma Adımları

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları takip edebilirsiniz:

1. **Depoyu klonlayın:**
```bash
   git clone [https://huggingface.co/spaces/meldakahramann/comic-store-assistant](https://huggingface.co/spaces/meldakahramann/comic-store-assistant)
   cd comic-store-assistant
  ```
2. **Gerekli kütüphaneleri yükleyin:**
```bash
   pip install -r requirements.txt
  ```
3. **Hugging Face API Token'ınızı tanımlayın:**
* Linux / macOS için:
  ```bash
   export HF_TOKEN="hf_token_adresiniz"
  ```
* Windows (CMD) için:
 ```bash
   set HF_TOKEN="hf_token_adresiniz"
  ```
4. **Uygulamayı çalıştırın:**
```bash
   python app.py
  ```