---
license: mit
language:
- tr
tags:
- medical
- turkish
- vector-search
- embeddings
- retrieval
- rag
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: train
    path: data/chunks.parquet
---

# 🩺 Türkçe Tıbbi Vektör Arama Projesi

Bu projede Türkçe tıbbi makaleler üzerinde çalışan basit bir semantik arama sistemi geliştirdim. Temel amaç, kullanıcı bir soru sorduğunda bu soruyla en alakalı makale parçalarını bulabilmek.

Burada özellikle dikkat ettiğim noktalardan biri, sistemin elinde yeterli bilgi yokken cevap üretmeye çalışmamasıydı. Bu nedenle benzerlik skoru belirli bir seviyenin altında kaldığında sistem cevap vermek yerine:

> Bu sorunun cevabı dokümanlarımda yer almamaktadır.

şeklinde geri dönüş yapıyor.

Projede genel olarak şu yapı kullanıldı:

| Özellik | Değer |
|---|---|
| Kaynak veri | `umutertugrul/turkish-hospital-medical-articles` veri setinin Acıbadem bölümü |
| Kullanılan makale | 250 |
| Toplam chunk | 1.556 |
| Ortalama chunk uzunluğu | Yaklaşık 339 token |
| Embedding modeli | `magibu/embeddingmagibu-200m` |
| Vektör boyutu | 768 |
| Vektör veritabanı | ChromaDB |
| Benzerlik metriği | Cosine Similarity |
| Belirlenen eşik | 0.49 |
| Genel doğruluk | %93,3 |

## 1. Veri Seti ve Chunking

### Veri seti seçimi

Veri kaynağı olarak Hugging Face üzerindeki `umutertugrul/turkish-hospital-medical-articles` veri setini kullandım.

Bu veri setinde makaleler hastanelere göre ayrıldığı için çalışmayı biraz daha kontrollü tutmak adına yalnızca **Acıbadem** kaynaklı makaleleri seçtim.

Acıbadem tarafında toplam 6.339 makale bulunuyordu. Öncelikle 500 karakterden kısa olan içerikleri çıkardım. Bu işlemden sonra 4.508 makale kaldı.

Daha sonra bu makaleler arasından `random_state=42` kullanarak rastgele 250 makale seçtim.

Burada sabit bir seed kullanmamın temel sebebi, çalışma tekrar çalıştırıldığında aynı makalelerin seçilebilmesini sağlamaktı.

Parçalama işlemi makalelerin `text` alanı üzerinden gerçekleştirildi.

### Chunking yöntemim

Metinleri doğrudan sabit uzunluklarda bölmek mümkün. Ancak bu yöntem bazı cümlelerin ortadan kesilmesine ve anlam bütünlüğünün bozulmasına neden olabiliyor.

Sadece paragraf bazlı parçalama yapıldığında ise başka bir problem ortaya çıkıyor. Bazı paragraflar birkaç kelimeden oluşurken bazıları yüzlerce kelime olabiliyor.

Bu nedenle iki yaklaşımı birleştiren daha dengeli bir yöntem kullandım.

`src/chunking.py` içerisinde işlem genel olarak şu şekilde ilerliyor:

1. Öncelikle metin boş satırlara göre paragraflara ayrılıyor.
2. Daha sonra paragraflar cümlelere bölünüyor.
3. Cümleler embedding modelinin tokenizer'ı kullanılarak ölçülüyor.
4. Bir chunk içerisinde maksimum 384 token bulunmasına izin veriliyor.
5. Ardışık chunk'lar arasında yaklaşık 64 token overlap bırakılıyor.
6. Tek başına 384 token sınırını geçen çok uzun cümleler kelime sınırlarından parçalanıyor.
7. Çok kısa kalan son parçalar mümkün olduğunca bir önceki chunk ile birleştiriliyor.

Bu yöntemi tercih etmemin en önemli sebebi parçaların hem anlamlı kalması hem de embedding işlemi için fazla uzun olmamasıydı.

Sonuçta 250 makaleden toplam **1.556 chunk** oluşturuldu. Ortalama chunk uzunluğu ise yaklaşık **339 token** oldu.

Overlap kullanılması da özellikle iki chunk sınırında kalan bilgilerin kaybolmasını önlüyor.

Örneğin bir tedavi yöntemiyle ilgili kritik bir cümle chunk'ın sonuna denk geldiğinde, aynı bilgi sonraki chunk içerisinde de kısmen yer alabiliyor.

## 2. Vektör Veritabanı ve Veri Şeması

Chunk'lar oluşturulduktan sonra hem Parquet formatında saklandı hem de ChromaDB içerisine eklendi.

Oluşturulan `data/chunks.parquet` dosyasında şu alanlar bulunuyor:

| Sütun | Tip | Açıklama |
|---|---|---|
| `url` | string | Makalenin orijinal bağlantısı |
| `chunk_text` | string | Parçalanmış metin |
| `chunk_vector` | list<float> | Chunk'ın embedding vektörü |
| `chunk_id` | string | Chunk'ın benzersiz kimliği |
| `parent_id` | string | Chunk'ın hangi makaleye ait olduğunu gösterir |
| `title` | string | Makalenin başlığı |
| `__source` | string | Makalenin kaynak hastanesi |
| `chunk_index` | int | Chunk'ın makale içerisindeki sırası |
| `n_tokens` | int | Chunk'ın token sayısı |

Ödev kapsamında özellikle istenen üç temel alan olan `url`, `chunk_text` ve `chunk_vector` bu yapı içerisinde bulunuyor.

Embedding vektörleri ChromaDB içerisinde **cosine similarity** kullanılacak şekilde saklanıyor.

Index'i yeniden oluşturmak için:

```bash
python src/build_index.py
```

komutunu çalıştırmak yeterli.

### Neden ChromaDB?

Bu projede yaklaşık 1.500 civarında vektör bulunduğu için çok büyük veya dağıtık bir veritabanı altyapısına ihtiyaç yoktu.

PGVector da kullanılabilirdi ancak bunun için ayrıca PostgreSQL kurulumu ve yönetimi gerekiyordu.

ChromaDB ise dosya tabanlı çalıştığı ve kurulumu oldukça kolay olduğu için bu ölçekteki proje için daha pratik bir seçenek oldu.

Projeyi başka bir bilgisayarda çalıştırmak isteyen biri de ek bir veritabanı sunucusu kurmadan sistemi ayağa kaldırabiliyor.

## 3. Embedding Modeli

Embedding modeli olarak:

`magibu/embeddingmagibu-200m`

modelini kullandım.

Model 768 boyutlu embedding üretiyor ve 8192 token'a kadar bağlam destekliyor.

Bu modeli seçmemin temel nedenlerinden biri Türkçe metinler için geliştirilmiş olmasıydı.

Özellikle tıbbi içeriklerin Türkçe olması nedeniyle, genel amaçlı bir embedding modeli yerine Türkçe konusunda güçlü bir model kullanmanın retrieval kalitesini artıracağını düşündüm.

Modelin başka önemli bir özelliği ise sorgu ve doküman tarafında farklı prompt yapıları kullanması.

Dokümanlar şu formatta modele veriliyor:

```text
title: none | text: ...
```

Kullanıcı sorguları ise:

```text
task: search result | query: ...
```

formatında embedding'e çevriliyor.

Bu ayrımı `src/embedder.py` içerisinde uyguladım.

Yaptığım küçük testlerde bunun etkisi oldukça net görüldü.

Birbiriyle ilişkili soru ve dokümanların benzerlik skorları yaklaşık **0.62 – 0.80** arasında çıkarken, ilgisiz tıbbi içerikler yaklaşık **0.04** seviyesinde kaldı.

Tamamen alan dışı olan örneğin Bitcoin ile ilgili bir sorguda ise skor yaklaşık **0.05** seviyesindeydi.

Bu fark daha sonra kullanacağım similarity threshold değerini belirlemeyi de kolaylaştırdı.

768 boyutlu embedding bu proje için yeterli oldu. Daha yüksek boyutlu modeller kullanılabilirdi ancak mevcut sonuçlarda buna ihtiyaç duymadım.

## 4. Arama Sistemi ve Eşik Belirleme

### Test soruları

Sistemi değerlendirmek için toplam 30 sorudan oluşan küçük bir test seti hazırladım.

Test setinin yapısı şu şekilde:

- 20 adet pozitif soru
- 10 adet negatif soru

Pozitif soruların cevapları veri setinde gerçekten bulunuyor.

Bu soruları hazırlarken hangi makaleden geldiklerini bildiğim için beklenen makale URL'sini de test verisine ekledim.

Negatif sorular ise iki gruptan oluşturuldu.

Birinci grupta:

- Bitcoin
- Fenerbahçe
- Python
- Uzay

gibi tıbbi veri setiyle tamamen ilgisiz sorular bulunuyor.

İkinci grupta ise:

- Kuduz
- Vitiligo
- Skolyoz

gibi tıbbi konular yer alıyor.

Bu hastalık isimlerinin kullandığım 250 makalelik korpusta bulunmadığını ayrıca kontrol ettim.

### Negatif veri hazırlarken yaşadığım sorun

İlk test setini hazırlarken Parkinson, çölyak ve sedef hastalığını negatif örnek olarak eklemiştim.

Ancak test sırasında sistem bu sorulara yüksek benzerlik değerleri vermeye başladı.

Başta bunun retrieval tarafında bir problem olduğunu düşündüm fakat veri setini kontrol ettiğimde bu hastalıkların aslında makalelerde geçtiğini fark ettim.

Örneğin Parkinson kelimesi korpus içerisinde 35 kez geçiyordu ve hatta doğrudan Parkinson ile ilgili bir makale bulunuyordu.

Bu yüzden bu soruları negatif setten çıkardım ve gerçekten korpusta bulunmayan hastalıklarla değiştirdim.

Bu süreç bana özellikle negatif test verisi oluştururken yalnızca tahmin ederek hareket etmenin doğru olmadığını gösterdi.

Negatif kabul edilen konunun veri setinde gerçekten bulunmadığını kontrol etmek gerekiyor.

## Arama nasıl çalışıyor?

Kullanıcının sorusu öncelikle embedding modelinin query formatıyla vektöre çevriliyor.

Daha sonra ChromaDB içerisinde en yakın 5 chunk aranıyor.

En yüksek cosine similarity skoru belirlenen threshold değerinin altında kalırsa sistem herhangi bir içerik üretmiyor.

Bunun yerine doğrudan:

```text
Bu sorunun cevabı dokümanlarımda yer almamaktadır.
```

mesajını döndürüyor.

Bu yapı `src/search.py` içerisinde bulunuyor.

## Benzerlik skorlarının dağılımı

30 test sorusunun sonuçlarına baktığımda pozitif ve negatif örneklerin büyük ölçüde birbirinden ayrıldığı görüldü.

| Grup | Minimum | Ortalama | Maksimum |
|---|---:|---:|---:|
| Pozitif sorular | 0.361 | 0.678 | 0.861 |
| Negatif sorular | 0.144 | 0.269 | 0.454 |

Burada tamamen kusursuz bir ayrım oluşmadı.

En yüksek negatif skor **0.454**, en düşük pozitif skor ise **0.361** oldu.

Bunun normal olduğunu düşünüyorum.

Çünkü bazı tıbbi sorular korpusta doğrudan bulunmasa bile veri setindeki başka tıbbi içeriklerle semantik olarak benzer olabilir.

Aynı şekilde bazı pozitif sorular çok genel veya dolaylı şekilde sorulduğunda beklenenden daha düşük similarity değeri alabilir.

## Threshold değerini nasıl belirledim?

Threshold değerini doğrudan tahmini olarak seçmek yerine 0.20 ile 0.70 arasındaki değerleri test ettim.

Her eşik değeri için:

- True Positive
- False Negative
- False Positive
- True Negative
- Precision
- Recall
- F1
- Accuracy

değerlerini hesapladım.

Tüm sonuçlar:

`outputs/threshold_analysis.csv`

dosyasına kaydedildi.

Öne çıkan bazı değerler şöyle:

| Eşik | TP | FN | FP | TN | Precision | Recall | F1 | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 20 | 0 | 4 | 6 | 0.83 | 1.00 | 0.91 | 0.87 |
| 0.40 | 19 | 1 | 1 | 9 | 0.95 | 0.95 | 0.95 | 0.93 |
| **0.49** | **18** | **2** | **0** | **10** | **1.00** | **0.90** | **0.947** | **0.933** |
| 0.55 | 17 | 3 | 0 | 10 | 1.00 | 0.85 | 0.92 | 0.90 |
| 0.65 | 14 | 6 | 0 | 10 | 1.00 | 0.70 | 0.82 | 0.80 |

Sonuçlara göre threshold değerini **0.49** olarak belirledim.

Burada özellikle precision değerini yüksek tutmak istedim.

Bunun nedeni projenin tıbbi içeriklerle çalışması.

Sistemin aslında bilmediği bir konuda cevap üretmesi, cevaplanabilecek bir soruyu yanlışlıkla reddetmesinden daha büyük bir problem.

0.49 threshold değerinde negatif olarak hazırlanan 10 sorunun tamamı doğru şekilde reddedildi ve false positive oluşmadı.

Bunun karşılığında 20 pozitif sorunun 2 tanesi threshold altında kaldı.

Bu nedenle sistem biraz daha temkinli davranıyor ancak bilmediği bir soruya cevap verme ihtimali azalıyor.

## Sonuçlar

Threshold değeri 0.49 olarak kullanıldığında elde edilen sonuçlar:

- Doğru makale ilk sırada: **%90**
- Doğru makale ilk 5 sonuç içerisinde: **%100**
- Negatif soruların doğru reddedilmesi: **10/10**
- Precision: **1.00**
- Recall: **0.90**
- F1: **0.947**
- Genel doğruluk: **0.933**

Bu sonuçlara göre sistemin küçük ölçekli veri setinde semantik olarak ilgili içerikleri başarılı şekilde bulabildiğini söyleyebiliriz.

Özellikle doğru makalenin ilk 5 sonuç içerisinde tüm pozitif sorularda bulunması retrieval tarafında oldukça iyi bir sonuç verdi.

Bunun yanında threshold kullanılması sayesinde sistem, veri setinde bulunmayan sorulara cevap üretmek yerine bunları reddedebiliyor.

## 🚀 Kurulum

Projeyi çalıştırmak için öncelikle sanal ortam oluşturulabilir:

```bash
python -m venv .venv
source .venv/bin/activate
```

Ardından gerekli paketler yüklenir:

```bash
pip install -r requirements.txt
```

Kullanılan Hugging Face veri seti erişim onayı gerektiriyor.

Bu nedenle veri seti sayfasından erişim izni verildikten sonra Hugging Face hesabıyla giriş yapılması gerekiyor.

Daha sonra index oluşturmak için:

```bash
python src/build_index.py
```

Testleri çalıştırmak için:

```bash
python src/evaluate.py
```

Arama yapmak için ise:

```bash
python src/search.py "Vebaya neden olan bakteri nedir?"
```

kullanılabilir.

Veri setinde bulunmayan bir soru sorulduğunda ise örneğin:

```bash
python src/search.py "Kuduz hastalığı nasıl tedavi edilir?"
```

sistem soruyu reddedecektir.

## 📁 Proje Yapısı

```text
├── data/
│   ├── chunks.parquet
│   └── test_questions.json
│
├── src/
│   ├── config.py
│   ├── chunking.py
│   ├── embedder.py
│   ├── build_index.py
│   ├── search.py
│   └── evaluate.py
│
├── outputs/
│   ├── benchmark_results.json
│   └── threshold_analysis.csv
│
├── requirements.txt
└── README.md
```

Dosyaların görevleri kısaca şöyle:

- `chunks.parquet`: Oluşturulan chunk'ları, URL'leri ve embedding vektörlerini içerir.
- `test_questions.json`: 20 pozitif ve 10 negatif test sorusunu içerir.
- `config.py`: Model, chunk boyutu ve threshold gibi genel ayarlar bulunur.
- `chunking.py`: Metinlerin chunk'lara ayrıldığı bölüm.
- `embedder.py`: Embedding modelinin kullanıldığı bölüm.
- `build_index.py`: Veriyi indirir, chunk oluşturur, embedding üretir ve ChromaDB index'ini oluşturur.
- `search.py`: Kullanıcı sorgularını arar ve threshold kontrolünü gerçekleştirir.
- `evaluate.py`: Test sorularını çalıştırır ve threshold analizini oluşturur.
- `benchmark_results.json`: Test sorularına ait ayrıntılı sonuçları içerir.
- `threshold_analysis.csv`: Farklı threshold değerlerinin karşılaştırmasını içerir.

Proje Python 3.14 ortamında geliştirildi.

Kullanılan temel kütüphaneler:

- `sentence-transformers 5.7`
- `chromadb 1.5`
- `torch 2.13`