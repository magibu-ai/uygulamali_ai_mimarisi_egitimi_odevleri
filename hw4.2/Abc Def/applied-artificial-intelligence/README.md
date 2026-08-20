# Veri Seti Seçimi ve Parçalama (Chunking)
## Veri Kaynağı
Hugging Face üzerindeki `umutertugrul/turkish-hospital-medical-articles` veri seti seçildi.

## Miktar 
İlgili veri setinden ilk 100 makale (doküman) seçildi. 

## Chunking Stratejisi 

Chunking için aşağıdaki stratejiler denendi:

### Chunking Yok

- İlgili kodlar ve scriptler `no-chunking/` dosyası altında bulunmaktadır.

### Sabit Token Sayısı + Overlap

- Seçilen embedding modeli yaklaşık 8000 büyüklüğünde bir windowa sahip olduğu için token sayısı 2000 ve overlap 200 olarak kullanıldı.
- İlgili kodlar ve scriptler `token-chunking/` dosyası altında bulunmaktadır.

### Sentence Chunking

- İlgili kodlar ve scriptler `sentence-chunking/` dosyası altında bulunmaktadır.

### Semantic Chunking

- Threshold percentile yaygın bir değer olan %85 olarak seçildi.
- İlgili kodlar ve scriptler `semantic-chunking/` dosyası altında bulunmaktadır.

Makalelerde paragrafları ayırmak zor olduğu için Paragraf Chunking yapamadım.

# Vektör Veri Tabanı Mimarisi & Şeması

Veri tabanı olarak PgVector eklentili Postgres.app (Postgresql) kullanıldı. Versiyonu 18.4.
Oluşturulan veri tabanı asağıdaki sütunları içermektedir:

- url:	Parçanın ait olduğu orijinal makalenin kaynak bağlantısı
- chunk_text: Parçalanmış metin içeriği
- chunk_vector: `semantic-chunking-half-dim/` için 384 boyutlu, ötekiler için 768 boyutlu embedding vektörü 

İlgili veriler çok büyük olduğu için ekleyemedim ama bu veriler "download-and-save.py" ile oluşturulabilir.

# Test Veri Seti (Benchmarking)

## Pozitif Sorular

### Sorular

1. Açık kalp ameliyatı nedir?
2. Onkolojik cerrahi nedir?
3. Mide bulantısı neden olur?
4. Ağız yarası neden olur?
5. Adet gecikmesi belirtileri nelerdir?
6. Vazopressin hormonunun görevleri nelerdir?
7. Bel fıtığı belirtileri nelerdir?
8. Amputasyonu bana açıkla.
9. Amilaz neden yükselir?
10. Göz kapağı ameliyatsız düzeltilebilir mi?
11. Amiloidozun organlar üzerinde ne tür etkileri vardır?
12. Ani öfke patlamaları neden olur?
13. Anoreksiya nasıl tedavi edilir?
14. Ankilozan spondalit belirtileri nelerdir?
15. Anksiyete türleri nelerdir?
16. Bazofil ne zaman yükselir?
17. Antikor testi nasıl yapılır?
18. Arı sokmasına ne iyi gelir?
19. Kardiyak arrest belirtileri nelerdir?
20. Aort kapak darlığı neden olur?

### İlgili Dokümanlar

1. Açık kalp ameliyatı nedir?
- https://www.acibadem.com.tr/ilgi-alani/acik-kalp-ameliyati/
2. Onkolojik cerrahi nedir?
- https://www.acibadem.com.tr/acibadem-de/onkolojik-cerrahi/
3. Mide bulantısı neden olur?
- https://www.acibadem.com.tr/ilgi-alani/mide-bulantisi-neden-olur-surekli-mide-bulantisi-nedenleri/
4. Ağız yarası neden olur?
- https://www.acibadem.com.tr/ilgi-alani/agiz-yarasi-nedir-belirtileri-ve-nedenleri/
5. Adet gecikmesi belirtileri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/adet-gecikmesi-nedenleri-regl-gecikmesi-neden-olur/
6. Vazopressin hormonunun görevleri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/adh-vazopressin-nedir/
7. Bel fıtığı belirtileri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/bel-fitigi-nedir/
8. Amputasyonu bana açıkla.
- https://www.acibadem.com.tr/ilgi-alani/ampute-ne-demek/
9. Amilaz neden yükselir?
- https://www.acibadem.com.tr/ilgi-alani/amilaz-nedir/
10. Göz kapağı ameliyatsız düzeltilebilir mi?
- https://www.acibadem.com.tr/ilgi-alani/ameliyatsiz-goz-kapagi-estetigi/
11. Amiloidozun organlar üzerinde ne tür etkileri vardır?
- https://www.acibadem.com.tr/ilgi-alani/amiloidoz-nedir-organlarda-protein-birikimi/
12. Ani öfke patlamaları neden olur?
- https://www.acibadem.com.tr/ilgi-alani/amok-hastaligi-nedir-ani-ofke-patlamalari/
13. Anoreksiya nasıl tedavi edilir?
- https://www.acibadem.com.tr/ilgi-alani/anoreksiya-nedir-anoreksiya-nervoza-belirtileri/
14. Ankilozan spondalit belirtileri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/ankilozan-spondilit/
15. Anksiyete türleri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/anksiyete/
16. Bazofil ne zaman yükselir?
- https://www.acibadem.com.tr/ilgi-alani/baso-bazofil-nedir-yuksekligi-dusuklugu/
17. Antikor testi nasıl yapılır?
- https://www.acibadem.com.tr/ilgi-alani/antikor/
18. Arı sokmasına ne iyi gelir?
- https://www.acibadem.com.tr/ilgi-alani/ari-sokmasi/
19. Kardiyak arrest belirtileri nelerdir?
- https://www.acibadem.com.tr/ilgi-alani/arrest-nedir-kardiyak-arrest-nedir/
20. Aort kapak darlığı neden olur?
- https://www.acibadem.com.tr/ilgi-alani/aort-kapak-darligi-nedir/

## Negatif Sorular

1. Kedilerde böbrek hastalığı belirtileri nelerdir?
2. Köpeklerde kusmaya ne sebep olur?
3. AES algoritması nedir?
4. Türkiye’nin en büyük hastanesi neresidir?
5. Kuantum bilgisayarları ne amaçla kullanılır?
6. CSS nedir?
7. Yapay zeka uygulama alanları nerelerdir?
8. Pil nedir?
9. Zika virüsü nedir?
10. Yumurtalık kistlerini bana açıkla.

# Vektör Arama & Eşik (Threshold) Yönetimi

- Embedding üretimi için Hugging Face'de bulunan "alibayram/embeddingmagibu-200m" kullanıldı.
- Karşılaştırma için kosinüs benzerliği kullanıldı.
- İki çeşit threshold'u test ettim, 70% ve 50%. 70%'i yaygın kullanıldığı için tercih ettim, 50%'de ise ne olacağını merak ettim.
- Vector dimensionlar'ı için `embeddingmagibu-200m`nun kendi kullandığı 785 ve bunun yarısı olan 384'ü test ettim.

# Sonuçlar

- Model beklenenden fazla belge getirdiği zaman, bunu False Positive olarak işaretledim.
- Buraya sonuçların özet versiyonları konuldu. Ayrıntılara `RAG_Results.numbers` veya `RAG_Results.xlsx` dosyalarından bakılabilir.

## Farklı Chunking Stratejileri İçin
### Chunking Yok

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
|:-------------|:-------------|:----------|:------------|:------------|
| **50**       | 84.21        | 94.12     | 88.89       | 95.00          |
| **70**       | 100.00       | 30.00     | 46.15       | 30.00          |

### Sabit Token Sayısı + Overlap

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
|:-------------|:-------------|:----------|:------------|:------------|
| **50**       | 70.00        | 93.33     | 80.00       | 95.00       |
| **70**       | 100.00       | 30.00     | 46.15       | 30          |

### Sentence Chunking

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
| :---         | :---         | :---      | :---        | :---        |
| **50**       | 12.50        | 60.00     | 20.69       | 100.00      |
| **70**       | 76.19        | 84.21     | 80.00       | 95.00       |

### Semantic Chunking

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
| :---         | :---         | :---      | :---        | :---        |
| **50**       | 40.00        | 88.89     | 55.17       | 95.00       |
| **70**       | 100.00       | 80.00     | 88.89       | 80.00       |

En iyi sonuçlar Semantic Chunking + 70% threshold ve Chunking olmadan %50 threshold ile gerçekleşti. Chunking olmadan başarı olmasının sebebi kullanılan embedding'in window size'ının çok büyük olması olabilir.
Burada hangisinin seçileceği amaca bağlı, ilgili Excel dosyasında ayrıntılara bakıldığında No Chunking stratejisi az sayıda da olsa False Positive sonuç getirmiş. Medical alanda bu durum sıkıntı olabileceğinden Semantic Chunking stratejisinin daha tercih edilebilir olduğunu düşünüyorum.

## Farklı Dimension'lar İçin

Chunking stratejisi olarak Semantic Chunking'i kullandım.

### 785

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
| :---         | :---         | :---      | :---        | :---        |
| **50**       | 40.00        | 88.89     | 55.17       | 95.00       |
| **70**       | 100.00       | 80.00     | 88.89       | 80.00       |

### 384

| Threshold(%) | Precision(%) | Recall(%) | F1 Score(%) | Hit Rate(%) |
| :---         | :---         | :---      | :---        | :---        |
| **50**       | 40.00        | 88.89     | 55.17       | 95.00       |
| **70**       | 100.00       | 70.00     | 82.35       | 70.00       |


Dimension sayısını yarıya düşürünce başarı da kötüleşti. 785 dimension kullanılması çok daha iyi.