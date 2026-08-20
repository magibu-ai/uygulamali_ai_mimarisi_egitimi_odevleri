# 🚀 Magibu Uygulamalı Yapay Zeka Mimarisi Eğitimi - Ödev Havuzu

**Geliştirici:** Ege Ertekin

Bu depo, **Magibu** tarafından düzenlenen **Uygulamalı Yapay Zeka Mimarisi Eğitimi** boyunca geliştirdiğim yapay zeka projelerini, dil modellerini (LLM) ve sıfırdan inşa edilen mimari bileşenleri içermektedir.

---

## 📅 Haftalık Ödevler ve Projeler

Aşağıdaki tablodan ilgili haftaya tıklayarak o haftanın konusuna, kodlarına ve mimari detaylarına ulaşabilirsiniz.

| Hafta | Ödev Konusu | Kullanılan Model | Durum |
| :--- | :--- | :--- | :---: |
| **1. Ödev** | [TinyQwen ile Türkçe İlçe Adı Türetme](#-1-hafta-tinyqwen-ile-türkçe-i̇lçe-adı-türetme-projesi) | `TinyQwen (Qwen3)` | ✅ Tamamlandı |
| **2. Ödev** | *Gelecek Ödev* | *Eklenecek* | ⏳ Beklemede |

---

## 📍 1. Hafta: TinyQwen ile Türkçe İlçe Adı Türetme Projesi

### 📌 Proje Hakkında
Bu çalışmada, Türkiye'deki ilçe isimlerinin fonetik ve morfolojik yapılarını (örn: *-köy, -tepe, -dağ, -ova* ekleri) matematiksel olarak analiz etmek amacıyla **sıfırdan bir Byte Pair Encoding (BPE) Tokenizer tasarlanmış** ve minyatür **Qwen 3 (TinyQwen)** Transformer mimarisi kullanılarak yeni Türkçe ilçe isimleri üretebilen bir dil modeli eğitilmiştir. Hazır kütüphaneler (örneğin Hugging Face `tokenizers`) kullanılmamış, metin işleme sürecinin tüm arka planı manuel olarak kodlanmıştır.

---

### 🧠 1. Kendi BPE Tokenizer'ımızın İnşası (`bpe_tokenizer.py`)
Modelin kelimeleri ve heceleri anlayabilmesi için harici bir araç kullanılmamış, algoritma doğrudan byte seviyesinde (UTF-8) çalışacak şekilde tarafımızca kodlanmıştır.

* **Frekans Analizi:** Metin önce 0-255 arası byte değerlerine dönüştürülmüş, ardından yan yana en çok gelen sayı çiftleri (bigram) tespit edilmiştir. (Örneğin algoritma, veri setini tarayarak "a" ve "r" harflerinin çok sık yan yana geldiğini istatistiksel olarak keşfetmiştir).
* **Sıkıştırma ve Birleştirme:** Belirlenen **50 birleştirme (merge) adımı** boyunca en popüler çiftler tek bir token (ID) haline getirilmiştir.
* **Sözlük Boyutu (Vocab Size):** Standart 256 byte'ın üzerine modelin kendi kendine öğrendiği 50 yeni hece/kural eklenerek **306 boyutunda** özgün bir kelime dağarcığı oluşturulmuştur.

### 🗂️ 2. Özgün Veri Setimiz (`dataset.txt`)
Modelin eğitimi için internetten hazır bir veri seti indirilmemiş, Türkiye'nin dört bir yanından (Adana'dan Trabzon'a, İstanbul'dan Şanlıurfa'ya) toplam **922 adet ilçe isminin** alt alta eklendiği özel bir veri seti (`dataset.txt`) oluşturulmuştur. Tüm harfler modele standart bir yapı sunmak adına küçük harfe çevrilmiştir.

### ⚙️ 3. Model Mimarisi ve Eğitim (TinyQwen)
Eğitilen kendi tokenizer'ımız, repoda yer alan **TinyQwen** modelinin beynine (`train.py` üzerinden) entegre edilmiştir. 
* **Model Bağlantısı:** Orijinal koddaki ilkel `CharTokenizer` tamamen devre dışı bırakılmış, yerine bizim yazdığımız `encode` ve `decode` fonksiyonları bağlanmıştır.
* **Eğitim Parametreleri:** Model, bağlam uzunluğu `block_size = 16`, paket boyutu `batch_size = 64` ve AdamW optimizasyonu ($lr = 3e-3$) kullanılarak **3000 adım (step)** boyunca eğitilmiştir.
* **Kayıp (Loss) Düşüşü:** Model, eğitime **30.10** gibi yüksek bir kayıp değeriyle başlamış, ancak kendi oluşturduğumuz tokenizer'ın başarısı sayesinde 3000 adımın sonunda bu değeri **0.20** gibi muazzam bir seviyeye indirerek yakınsamıştır.

---

### 🎯 4. Çıkarım (Inference) ve Aşırı Öğrenme Analizi
Eğitim sonucunda model, Türkçe ilçe isimlerinin karakter dizilimini ve hece yapısını kusursuz bir şekilde kavramıştır.

* **Overfitting (Aşırı Öğrenme) Gözlemi:** Veri seti boyutunun nispeten küçük olması (922 satır) ve eğitim adımının uzun tutulması sebebiyle model, Türkçe dil kurallarını öğrenmekle kalmayıp veri setini ezberlemiştir. 
* **Örnek Çıktılar:** Test esnasında model halüsinasyon görmek yerine son derece isabetli bir şekilde doğrudan gerçek ilçeleri üretmiştir:
  * 📍 `araban`
  * 📍 `ergani`
  * 📍 `şehitkamil`
  * 📍 `manavgat`
  * 📍 `maltepe`

> **Geliştirici Notu:** İstenildiği takdirde modelin uydurma (fakat kulağa Türkçe gelen) yeni ilçeler üretmesi için çıkarım fonksiyonundaki sıcaklık (`temperature`) değeri 1.0'ın üzerine çıkarılabilir veya eğitim adım sayısı düşürülerek ezberin önüne geçilebilir.

---
*Bu depo, derin öğrenme ve modern yapay zeka mimarilerinin (Transformers, LLMs) arkasındaki teoriyi pratik kodlama ile birleştirmek amacıyla aktif olarak güncellenmektedir.*
