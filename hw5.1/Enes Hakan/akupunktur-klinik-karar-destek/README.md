# Akupunktur Klinik Karar Destek Asistanı

Hekimin girdiği endikasyonları ve muayene bulgularını Giovanni Maciocia'nın *The Foundations of Chinese Medicine* kitabında arayan; olası TCM paternlerini ve doğrulanmış akupunktur noktası adaylarını Türkçe sunan, tamamen yerel çalışan bir klinik karar destek sistemidir. Terminalden veya Streamlit web arayüzünden kullanılabilir.

> Eğitim amaçlı klinik karar desteğidir. Kesin tanı koymaz, hekimin kararının veya acil tıbbi değerlendirmenin yerini almaz.

## Projenin çıkış noktası

Bu proje, akupunktur tedavisi uygulayan bir hekimin muayene sırasında farklı bulguları birlikte yorumlama, olası TCM paternlerini karşılaştırma ve seçilecek noktaların kaynak bilgisini hızlıca doğrulama ihtiyacından doğdu. Bin sayfayı aşan bir başvuru kitabında aynı anda semptom, dil, nabız, patern ve nokta ilişkilerini aramak klinik iş akışını yavaşlatabiliyor. Sistem hekimin yerine karar vermek için değil; kitabı vaka bağlamında tarayan, olası seçenekleri gerekçelendiren ve ilgili sayfayı gösteren ikinci bir okuma katmanı sağlamak için geliştirildi.

## Ne yapar?

Hekim şu bilgileri girer:

- Ana şikâyet ve süresi
- Dil bulgusu
- Nabız bulgusu
- Diğer önemli bulgular ve mevcut tanılar
- Varsa ek not

Asistan bunlardan İngilizce bir arama sorgusu oluşturur, kitabın yerel vektör indeksini tarar, olası TCM paternlerini çıkarır ve aday akupunktur noktalarını kitapta ayrıca doğrular. Sonuç; patern, kısa gerekçe, doğrulanmış nokta adayları ve kitap/PDF sayfalarıyla sunulur. Kaynak PDF sayfası PNG olarak oluşturularak hekimin doğrudan incelemesine açılır.

## Mimari

`Türkçe vaka → Qwen3 tool calling → bge-m3 + ChromaDB → İngilizce kitap parçaları → Türkçe kaynaklı yanıt`

Araçlar:

- `kitapta_ara`: İngilizce kitapta patern ve bulgu arar.
- `nokta_bilgisi_getir`: aday noktanın konum, işlev, endikasyon ve uyarılarını kitapta doğrular.

İnternet araması yoktur. PDF ve üretilen Chroma indeksi telif/boyut nedeniyle repoya eklenmez.

## RAG bilgi kaynağı

RAG sisteminin tek bilgi kaynağı aşağıdaki kitaptır:

> Maciocia, Giovanni. *The Foundations of Chinese Medicine: A Comprehensive Text*. 3. baskı. Churchill Livingstone/Elsevier, 2015.

Kullanılan PDF 1.319 sayfadır. Kitap; Çin tıbbının temel teorisini, organ ve kanal işlevlerini, hastalık nedenlerini, tanı yöntemlerini, patern ayrımını, akupunktur noktalarını ve tedavi ilkelerini aynı kaynakta topladığı için seçildi. Böylece modelin farklı ve kalitesi belirsiz internet sayfalarından bilgi birleştirmesi yerine, cevaplar tek ve kapsamlı bir referansa dayandırıldı.

### Kaynak nasıl indekslendi?

1. PDF metni `pypdf` ile sayfa sayfa çıkarıldı.
2. Metin, 50 kelimelik bindirme içeren yaklaşık 260 kelimelik parçalara ayrıldı.
3. Her parça `bge-m3` ile vektöre dönüştürüldü.
4. Vektörler; basılı kitap sayfası ve PDF sayfası metadatasıyla ChromaDB'ye kaydedildi.
5. Tam kitap yerel testte 3.766 aranabilir parçaya dönüştürüldü.
6. Türkçe vaka sorgusu çok dilli embedding modeli sayesinde İngilizce kitap parçalarıyla eşleştirildi.

`kitapta_ara` semantik benzerlikle ilgili patern ve bulgu bölümlerini getirir. `nokta_bilgisi_getir` ise semantik sonuca güvenmek yerine kitapta nokta kodunu tam metin eşleşmesiyle doğrular. Yanıtta hem kitabın basılı sayfa numarası hem PDF sayfa numarası gösterilir; ilgili PDF sayfası yerelde PNG olarak üretilebilir.

Kaynak PDF telifli ve büyük bir dosya olduğu için GitHub reposuna eklenmemiştir. Kullanıcı kitabın yasal olarak edindiği yerel kopyasının yolunu `ACUPUNCTURE_PDF` ortam değişkeniyle uygulamaya verir. ChromaDB indeksi de yeniden üretilebilir olduğu için repoda tutulmaz.

### Yerel modeller

- Yanıt ve tool calling: `qwen3:4b-instruct-2507-q4_K_M` (GGUF/Q4_K_M)
- Çok dilli embedding: `bge-m3`
- Vektör veritabanı: ChromaDB
- Arayüz: terminal ve Streamlit

Kitap İngilizce olmasına rağmen kullanıcı Türkçe çalışır. `bge-m3`, Türkçe vaka ile İngilizce kaynak arasında çapraz dil araması yapar; Qwen3 sonucu Türkçe sunar.

### Güvenlik sınırları

- Sistem kesin tanı veya otomatik tedavi emri vermez; seçenekleri hekime sunar.
- Nokta önerileri `nokta_bilgisi_getir` ile kitapta tam kod eşleşmesi üzerinden doğrulanır.
- Doğrulanmayan nokta nihai cevaba alınmaz.
- Kırmızı bayrak ifadeleri modelden önce kodla kontrol edilir; bu durumda nokta önerilmez ve acil modern tıbbi değerlendirme belirtilir.
- Sistem yalnızca yerel kitap indeksini kullanır; kontrolsüz internet kaynağı kullanmaz.

## Kurulum

Ollama'yı kurup modelleri indirin:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull bge-m3
```

Python ortamını hazırlayın:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Kitap yolunu tanımlayın (`.env.example` yalnızca örnektir; ek bağımlılık kullanmamak için değer shell'den okunur):

```bash
export ACUPUNCTURE_PDF="/tam/yol/The Foundations of Chinese Medicine.pdf"
```

İlk kullanımda bir kez indeksleyin, sonra sohbeti açın:

```bash
python index.py
python chat.py
```

Web arayüzü için aynı terminalde:

```bash
streamlit run app.py
```

Tarayıcı adresi: `http://localhost:8501`

İndeksi yeniden üretmek için `python index.py --reset` kullanın. Kaynak sayfaları cevap sırasında `source_pages/` altında PNG olarak oluşturulur.
Alaka eşiği varsayılan olarak `MIN_SIMILARITY=0.45` değeridir; gerçek vaka ölçümleriyle kalibre edilmelidir.

## System prompt özeti

Model yalnızca araç sonuçlarını kullanır, İngilizce arama sorgusu üretir, her nokta adayını ikinci araçla doğrular, eksik bulguda soru sorar ve kitap/PDF sayfasını gösterir. Kırmızı bayrak kontrolü modelden önce deterministik olarak çalışır.

System prompt özellikle küçük ve yerel bir modelde araç döngüsünü sınırlayacak şekilde optimize edilmiştir: kitap araması vaka başına bir kez yapılır, nokta kodları ayrı araçla doğrulanır ve nihai cevap yalnızca doğrulanmış kaynaklardan oluşturulur.

## Örnek konuşmalar

Test ortamı: 8 GB Apple Silicon, Ollama 0.32.9, Qwen3 4B Q4_K_M, `bge-m3` ve kitabın tamamından oluşturulmuş 3.766 indeks parçası. Aşağıdaki kayıtlar yerel çalıştırmalardan alınmıştır; ilk model yüklemesi ve normal vaka birkaç dakika sürebilir.

### 1. Normal vaka

```text
Kullanıcı — Ana şikâyet ve süre: 3 aydır baş ağrısı
Kullanıcı — Dil bulgusu: kenarlar kırmızı
Kullanıcı — Nabız bulgusu: wiry, özellikle solda
Kullanıcı — Diğer bulgular: baş dönmesi, irritabilite ve tinnitus
[tool] kitapta_ara({"sorgu":"wiry pulse with headache and dizziness","sonuc_sayisi":1})
[tool] nokta_bilgisi_getir({"nokta_kodu":"LV-3"})
Asistan — Olası patern: Liver disharmony / Liver-Yang yükselmesi. Wiry nabız, baş ağrısı,
baş dönmesi, irritabilite ve tinnitus bu olasılığı destekler. Doğrulanan nokta adayı:
LV-3 (Taichong). Kaynak: kitap s. 1121, PDF s. 1150,
source_pages/pdf-page-1150.png. Son karar hekimindir.
```

### 2. Eksik bulgu

```text
Kullanıcı — Ana şikâyet ve süre: uzun süredir yorgunluk
Kullanıcı — Dil bulgusu: belirtilmedi
Kullanıcı — Nabız bulgusu: belirtilmedi
[tool] kitapta_ara({"sorgu":"chronic fatigue pattern differentiation tongue pulse"})
Asistan — Ayırıcı değerlendirme için dil ve nabız bulgularını belirtin.
```

### 3. Kırmızı bayrak

```text
Kullanıcı — Ana şikâyet ve süre: ani güç kaybı ve yüzde kayma
Asistan — ACİL/KIRMIZI BAYRAK: Bu bulgular acil modern tıbbi değerlendirme gerektirebilir. Akupunktur noktası önerilmedi; yerel acil yardım sürecini başlatın.
```

## Kontrol

```bash
python tools.py
python -m compileall -q .
```
