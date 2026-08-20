---
pretty_name: Turkish Dermatology RAG Chunks
language:
- tr
license: cc-by-4.0
task_categories:
- feature-extraction
- sentence-similarity
size_categories:
- 1K<n<10K
tags:
- medical
- turkish
- dermatology
- rag
- embeddings
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train.parquet
---

# Turkish Dermatology RAG Chunks

Bu veri kümesi, `umutertugrul/turkish-medical-articles` koleksiyonundaki
Dermatoloji branşından deterministik olarak seçilen 500 Türkçe makalenin
arama odaklı chunk ve embedding temsillerini içerir.

## Teslim bağlantıları

- Kaynak kod: [GitHub — turkish-medical-vector-search](https://github.com/berkbirkan/turkish-medical-vector-search)
- Hugging Face veri kümesi: [berkbirkan/turkish-dermatology-rag-dataset](https://huggingface.co/datasets/berkbirkan/turkish-dermatology-rag-dataset)
- Notebook: [`notebooks/turkish_medical_vector_search.ipynb`](notebooks/turkish_medical_vector_search.ipynb)
- 30 soruluk test seti: [`data/benchmark/test.jsonl`](data/benchmark/test.jsonl)
- Threshold raporu: [`reports/metrics/threshold_evaluation.json`](reports/metrics/threshold_evaluation.json)

> Eğitim ve bilgi erişim araştırması içindir. Klinik karar desteği, tanı veya
> tedavi amacıyla kullanılmamalıdır.

## Kaynak ve atıf

- Kaynak: [umutertugrul/turkish-medical-articles](https://huggingface.co/datasets/umutertugrul/turkish-medical-articles)
- Orijinal yayın sitesi: Doktorsitesi.com
- Kaynak lisansı: CC BY 4.0
- Kaynak veri seti gated'dır ve dosyalara erişim için koşulların kabulü gerekir.
- Her satır, atıf ve kaynağa geri dönüş için orijinal `url` alanını korur.

Bu türetilmiş veri kümesi kaynak metinleri dönüştürdüğü için CC BY 4.0
altında yayımlanır. Kullanıcılar orijinal kaynağı belirtmeli ve kaynak veri
kümesinin güncel erişim koşullarını ayrıca incelemelidir.

## Oluşturma süreci

1. `branch == Dermatoloji` filtresi uygulandı.
2. Zorunlu alanı eksik, 200 karakterden kısa ve yinelenen kayıtlar elendi.
3. URL'ye göre sabit sıralama sonrası `seed=42` ile 500 makale seçildi.
4. Paragraf → cümle → token öncelikli mixed chunking uygulandı.
5. Hedef 512 token, overlap 64 token ve minimum 80 token kullanıldı.
6. `magibu/embeddingmagibu-200m` ile 768 boyutlu L2-normalized vektörler üretildi.

Toplam 500 parent makaleden 1.019 chunk oluşturuldu. Başlık her chunk'a dahil
edilir ve token bütçesinin parçasıdır.

### Chunking stratejisi ve seçim gerekçesi

Salt sabit karakter bölme, tıbbi cümleleri ve paragraf bağlamını rastgele
kesebildiği için tercih edilmedi. Tam semantik chunking ise ek bir model,
değişken karar sınırları ve daha yüksek yeniden üretim maliyeti doğurur. Bu
nedenle deterministik **mixed chunking** kullanıldı:

1. Önce kaynak paragraf ve satır sınırları korunur.
2. Token bütçesini aşan paragraflar cümle sınırlarından bölünür.
3. Tek başına uzun cümleler model tokenizerı ile token düzeyinde bölünür.
4. Küçük birimler 512 token bütçesine kadar birleştirilir.
5. Komşu chunk'lar arasında 64 token overlap bırakılır.
6. Makale başlığı her chunk'a eklenir ve 512 token sınırına dahil edilir.

Bu yaklaşım hem okunabilir tıbbi bağlamı korur hem de aynı kaynak ve
konfigürasyonla tekrarlandığında aynı chunk'ları üretir. Sonuçta 1.019 chunk'ın
hiçbiri 512 token sınırını aşmamış ve 500 makalenin tamamı temsil edilmiştir.

### Embedding modeli ve seçim gerekçesi

[`magibu/embeddingmagibu-200m`](https://huggingface.co/magibu/embeddingmagibu-200m)
ödevde önerilen, Türkçe odaklı bir Sentence Transformers modelidir. Yaklaşık
200 milyon parametreyle yerel/Colab kullanımına görece uygun olması, 8.192 token
context window sunması ve query/document ayrımlı semantik arama kodlama yolları
sağlaması nedeniyle seçildi. Model her chunk için 768 boyutlu, `float32` ve
L2-normalized vektör üretir. Aynı modelin query-specific kodlama yolu soruların
vektörleştirilmesinde kullanılır.

## Şema

| Alan | Tip | Açıklama |
|---|---|---|
| `url` | string | Orijinal makale bağlantısı |
| `chunk_text` | string | Başlık dahil arama parçası |
| `chunk_vector` | float32[768] | L2-normalized Magibu embedding |
| `chunk_id` | string | Deterministik benzersiz chunk kimliği |
| `parent_id` | string | Kaynak makale kimliği |
| `title` | string | Makale başlığı |
| `branch` | string | Uzmanlık dalı; bu sürümde Dermatoloji |
| `chunk_index` | int64 | Parent içindeki sıra |
| `token_count` | int64 | Embedding tokenizerına göre token sayısı |
| `embedding_model` | string | Embedding model kimliği |

## Kullanım

```python
from datasets import load_dataset

dataset = load_dataset("berkbirkan/turkish-dermatology-rag-dataset")
print(dataset["train"].features)
print(len(dataset["train"]))  # 1019
```

`chunk_vector` alanı doğrudan cosine arama indeksine aktarılabilir. Sorgular
aynı embedding modeliyle ve query-specific encoding yoluyla vektörleştirilmelidir.

## Benchmark ve threshold

Eşik yalnızca ayrı bir 10 pozitif + 10 negatif kalibrasyon setinde belirlendi:
`0.4240`. Eşik sabit tutularak 20 pozitif + 10 negatif bağımsız testte precision
`1,00`, recall `0,95` ve F1 `0,9744` elde edildi. Bu kontrollü ve küçük benchmark
sonucu genel klinik performans iddiası değildir.

Yanlış bir tıbbi soruyu cevaplanabilir kabul etmek, cevaplanabilir bir soruyu
reddetmekten daha riskli görüldüğü için threshold taramasında yanlış kabul
maliyeti `2`, yanlış ret maliyeti `1` olarak kullanıldı. Yalnızca kalibrasyon
setinde en yüksek negatif skor `0.41676`, en düşük pozitif skor `0.43128` oldu.
Sınıflar ayrıldığı için uygulama eşiği bu iki sınırın orta noktası olan
`0.42402` değerinden dört ondalığa yuvarlanarak **`0.4240`** seçildi. Test seti
eşik seçiminde kullanılmadı.

ChromaDB cosine distance döndürür; karşılaştırılan skor
`cosine_similarity = 1 - cosine_distance` olarak hesaplanır. En iyi skor eşik
altındaysa sistem LLM çağırmadan doğrudan şu çıktıyı verir:

> Bu sorunun cevabı dokümanlarımda yer almamaktadır.

Bağımsız testte 19/20 pozitif soru kabul edilmiş, 10/10 negatif soru reddedilmiş
ve parent-document Recall@5 `0.85` bulunmuştur. Negatif sorulardaki ayırt edici
yokluk terimlerinin 1.019 chunk'ın tamamında sıfır kez geçtiği ayrıca
doğrulanmıştır.

## Teslim paketindeki kod ve raporlar

Bu Hugging Face reposu yalnızca Parquet dosyasını değil, ödevi yeniden üretmek
için gereken teslim materyallerini de içerir:

| Yol | İçerik |
|---|---|
| `src/` | Chunking, embedding, retrieval, ChromaDB ve opsiyonel üretim kodu |
| `scripts/` | İndirme, seçim, chunking, embedding, benchmark ve dışa aktarma adımları |
| `configs/default.yaml` | Sabit deney parametreleri |
| `notebooks/` | Açıklamalı Colab/Jupyter notebook'u |
| `data/benchmark/` | Kalibrasyon ve 20 pozitif + 10 negatif bağımsız test soruları |
| `reports/metrics/` | Şema, embedding, threshold ve test sonuçları |
| `reports/figures/` | Chunk ve threshold analiz grafikleri |
| `tests/` | Veri sözleşmesi ve retrieval birim testleri |

## Sınırlılıklar ve sorumlu kullanım

- Metinler halka açık sağlık makaleleridir; klinik kılavuz değildir.
- 500 makale dermatolojinin tamamını temsil etmez.
- Kaynak içerikte tarihsel, yanlı veya eksik bilgi bulunabilir.
- Veri ya da embedding modeli değiştirilirse threshold yeniden kalibre edilmelidir.
- Kullanıcıya gösterilen cevaplarda `url` ve kanıt chunk'ları korunmalıdır.
- Kişisel tıbbi kararlar için nitelikli sağlık profesyoneline başvurulmalıdır.

## Yeniden üretilebilirlik

Seçim, chunking, embedding, Chroma ve benchmark kodları companion source-code
reposunda bulunur. Kritik parametreler YAML yapılandırmasında sabitlenmiştir;
teslim Parquet dosyası ayrıca satır sayısı, şema, sonlu vektör, L2 normu ve
SHA-256 kontrollerinden geçirilir.
