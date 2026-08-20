# Eşik Analizi (Threshold Analysis)

- Embedding modeli: `magibu/embeddingmagibu-200m` (768 boyut, kosinüs)
- Değerlendirme kümesi: 20 pozitif + 10 negatif soru
- Seçilen eşik: **0.53**

## Ayrışma (separation)

| Grup | En yüksek benzerlik (ort.) | Min | Maks |
|---|---:|---:|---:|
| Pozitif (20) | 0.7376 | 0.5819 | 0.8784 |
| Negatif (10) | 0.2749 | 0.1615 | 0.4777 |

Ayrışma boşluğu: en düşük pozitif **0.5819** ile en yüksek negatif **0.4777** arasında **0.1042** fark var.

## Eşik taraması

| Eşik | Yanıtlanan poz. | Doğru kaynakla | Kaçırılan poz. | Negatife yanlış yanıt | F1 | Doğruluk |
|---:|---:|---:|---:|---:|---:|---:|
| 0.20 | 20/20 | 20/20 | 0 | 8/10 | 0.833 | 0.733 |
| 0.25 | 20/20 | 20/20 | 0 | 5/10 | 0.889 | 0.833 |
| 0.30 | 20/20 | 20/20 | 0 | 2/10 | 0.952 | 0.933 |
| 0.35 | 20/20 | 20/20 | 0 | 2/10 | 0.952 | 0.933 |
| 0.40 | 20/20 | 20/20 | 0 | 1/10 | 0.976 | 0.967 |
| 0.45 | 20/20 | 20/20 | 0 | 1/10 | 0.976 | 0.967 |
| 0.50 | 20/20 | 20/20 | 0 | 0/10 | 1.000 | 1.000 |
| 0.53 **←** | 20/20 | 20/20 | 0 | 0/10 | 1.000 | 1.000 |
| 0.55 | 20/20 | 20/20 | 0 | 0/10 | 1.000 | 1.000 |
| 0.60 | 18/20 | 18/20 | 2 | 0/10 | 0.947 | 0.933 |
| 0.65 | 17/20 | 17/20 | 3 | 0/10 | 0.919 | 0.900 |
| 0.70 | 13/20 | 13/20 | 7 | 0/10 | 0.788 | 0.767 |
| 0.75 | 12/20 | 11/20 | 8 | 0/10 | 0.710 | 0.733 |
| 0.80 | 5/20 | 4/20 | 15 | 0/10 | 0.333 | 0.500 |
| 0.85 | 1/20 | 0/20 | 19 | 0/10 | 0.000 | 0.367 |
| 0.90 | 0/20 | 0/20 | 20 | 0/10 | 0.000 | 0.333 |

## Kaynak makale geri çağırma (retrieval)

- Beklenen kaynak ilk sırada: **15/20**
- Beklenen kaynak ilk 5'te: **20/20**
- Beklenen kaynak ilk 10'da bulunamadı: **0**

## Soru bazında en yüksek benzerlik

| ID | Tür | Soru | En yüksek benzerlik | Beklenen kaynak sırası |
|---|---|---|---:|---:|
| P01 | poz | Osteoporozda kemik yıkımı hangi yaşlardan itibaren başlar? | 0.7565 | 1 |
| P02 | poz | Demir eksikliği anemisinin belirtileri nelerdir? | 0.8307 | 1 |
| P03 | poz | Alerjik rinit hangi belirtilerle ortaya çıkar? | 0.7961 | 5 |
| P04 | poz | Alerjik astıma neden olan başlıca alerjenler nelerdir? | 0.7703 | 2 |
| P05 | poz | Anksiyete bozuklukları kadınlarda mı erkeklerde mi daha sık… | 0.6377 | 1 |
| P06 | poz | Derin ven trombozunda pıhtılaşmaya yol açan nedenler nelerdir? | 0.7318 | 1 |
| P07 | poz | Lupus hastalığının oluşumunu tetikleyen çevresel etkenler n… | 0.7852 | 1 |
| P08 | poz | Hodgkin lenfomayı diğer lenfoma türlerinden ayıran hücre ti… | 0.7789 | 1 |
| P09 | poz | Prostat bezinin ana görevi nedir? | 0.6550 | 1 |
| P10 | poz | Ayak mantarına en sık hangi mantar cinsleri neden olur? | 0.8063 | 3 |
| P11 | poz | Ürodinami testi hangi organların bozukluklarını araştırmak … | 0.8087 | 1 |
| P12 | poz | Histeroskopi işleminde hangi cihaz kullanılır? | 0.7546 | 1 |
| P13 | poz | Eritrositler nerede üretilir ve ömrünü tamamlayınca nerede … | 0.5834 | 1 |
| P14 | poz | Menisküslerin diz eklemindeki görevi nedir? | 0.6591 | 1 |
| P15 | poz | Yutak (farenks) kanserlerinde ön plandaki risk faktörleri n… | 0.5819 | 1 |
| P16 | poz | Anal fissür belirtileri nelerdir? | 0.8784 | 3 |
| P17 | poz | Obezite vücut yağ oranı bakımından nasıl tanımlanır? | 0.6869 | 2 |
| P18 | poz | Diş ağrısının olası sebepleri nelerdir? | 0.8044 | 1 |
| P19 | poz | Tırnak mantarı hangi ortamlarda bulaşır? | 0.7639 | 1 |
| P20 | poz | Kemik iliğinde bulunan kök hücreler ne için çalışır? | 0.6831 | 1 |
| N01 | neg | Java programlama dilinde bir HashMap nasıl oluşturulur? | 0.1939 | — |
| N02 | neg | 2022 FIFA Dünya Kupası'nı hangi ülke kazandı? | 0.2478 | — |
| N03 | neg | İstanbul'dan Ankara'ya yüksek hızlı tren bileti kaç TL? | 0.2933 | — |
| N04 | neg | Bitcoin'in bugünkü dolar cinsinden fiyatı nedir? | 0.4777 | — |
| N05 | neg | Mars'a insanlı ilk görevin hangi yıl yapılması planlanıyor? | 0.1615 | — |
| N06 | neg | Bir otomobilin motor yağı kaç kilometrede bir değiştirilmel… | 0.2707 | — |
| N07 | neg | Osmanlı Devleti hangi padişah döneminde İstanbul'u fethetti? | 0.2061 | — |
| N08 | neg | Kedilerde kalp kurdu hastalığı nasıl tedavi edilir? | 0.3944 | — |
| N09 | neg | Python'da pandas kütüphanesiyle CSV dosyası nasıl okunur? | 0.2489 | — |
| N10 | neg | Bir evin elektrik tesisatında sigorta nasıl değiştirilir? | 0.2547 | — |
