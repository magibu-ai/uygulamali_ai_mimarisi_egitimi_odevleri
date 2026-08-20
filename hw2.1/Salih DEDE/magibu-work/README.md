# MMLU Benchmark Sonuçları

Türkçe MMLU veri seti ([`alibayram/yapay_zeka_turkce_mmlu_model_cevaplari`](https://huggingface.co/datasets/alibayram/yapay_zeka_turkce_mmlu_model_cevaplari)) üzerinde, **62 kategori** ve toplam **6.200 soru** kullanılarak iki model karşılaştırıldı. Test kodu: [`MMLUBenchmark.ipynb`](MMLUBenchmark.ipynb), ham sonuçlar: [`BenchmarkResults/`](BenchmarkResults/).

| | Fine-tuned model | Referans model |
|---|---|---|
| **Model** | `trendyol-marangoz-finetuned-gemma-4-E4B-it` | `google/gemma-4-31b-it:nitro` |
| **Kaynak** | HuggingFace (LoRA adaptörü + `google/gemma-4-E4B-it` taban) | OpenRouter API |
| **Parametre sayısı** | 7.96B | Bilinmiyor (API üzerinden) |

## Genel Sonuç

| Metrik | Fine-tuned model | Referans model | Fark |
|---|---:|---:|---:|
| **Başarı** | %71.73 | %84.89 | **-13.16 puan** |
| Doğru cevap | 4.447 / 6.200 | 5.263 / 6.200 | -816 |
| Toplam süre | 2.273 sn (~38 dk) | 5.416 sn (~90 dk) | - |

**Öne çıkan sonuç:** Referans model (OpenRouter, `gemma-4-31b-it`), test edilen **62 kategorinin tamamında** fine-tuned modelden daha yüksek başarı gösterdi. Ortalama fark kategori başına ~13 puan.

## Farkın En Az Olduğu 10 Kategori

Fine-tuned modelin referans modele en çok yaklaştığı alanlar:

| Kategori | Fine-tuned | Referans | Fark |
|---|---:|---:|---:|
| Tıbbi Dökümantasyon ve Sekreterlik | 79 | 82 | +3 |
| Turizm ve Seyahat Hizmetleri | 69 | 73 | +4 |
| Yönetim Bilişim Sistemleri | 76 | 80 | +4 |
| Sosyal Hizmet | 80 | 85 | +5 |
| Ehliyet Sınavı | 89 | 95 | +6 |
| Okul Öncesi Öğretmenliği | 82 | 88 | +6 |
| Parakende Satış ve Mağaza Yöneticiliği | 72 | 78 | +6 |
| Çocuk Gelişimi | 79 | 85 | +6 |
| Sağlık Yönetimi | 78 | 85 | +7 |
| Tarım | 68 | 75 | +7 |

## Farkın En Fazla Olduğu 10 Kategori

Fine-tuned modelin en çok geride kaldığı alanlar:

| Kategori | Fine-tuned | Referans | Fark |
|---|---:|---:|---:|
| Kim 500 Milyar İster | 56 | 88 | +32 |
| DHBT | 61 | 84 | +23 |
| Çağrı Merkezi Hizmetleri | 63 | 85 | +22 |
| Futbol | 57 | 79 | +22 |
| Emlak ve Emlak Yönetimi | 65 | 87 | +22 |
| TUS | 67 | 88 | +21 |
| Medya ve İletişim | 69 | 90 | +21 |
| Tarih | 64 | 84 | +20 |
| KPSS Denemeleri | 61 | 80 | +19 |
| Aşçılık | 68 | 87 | +19 |

*(Her kategoride tam 100 soru bulunduğundan yukarıdaki sayılar doğrudan yüzde başarı oranıdır.)*

## Değerlendirme

- Fine-tuned model, referans modelin ~%85'lik seviyesinin gerisinde kalarak genel doğrulukta **%71.7** ile sınırlı kaldı; hiçbir kategoride referans modeli geçemedi.
- En düşük performans, genel kültür/güncel bilgi ağırlıklı kategorilerde (**Kim 500 Milyar İster, Futbol, Tarih, Medya ve İletişim**) görülüyor — bu, fine-tuning verisinin (Trendyol ürün/mağaza odaklı) bu alanları kapsamadığını düşündürüyor.
- En yakın sonuçlar, göreve özel/prosedürel bilgi gerektiren kategorilerde (**Ehliyet Sınavı, Sosyal Hizmet, Tıbbi Dökümantasyon**) alındı; bu alanlarda taban modelin genel yeteneği zaten güçlü olduğundan fark daralıyor.
- Süre açısından fine-tuned model (lokal, MPS/CUDA) referans modele (bulut API) göre ~2.4x daha hızlı tamamlandı; ancak bu karşılaştırma donanım ve API gecikmesine bağlı olduğundan model kalitesiyle doğrudan ilişkili değildir.
