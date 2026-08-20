---
base_model: unsloth/Qwen3-14B
library_name: peft
license: apache-2.0
language:
- tr
tags:
- unsloth
- qwen3
- lora
- qlora
- meb
- egitim
- turkish
- mevzuat
datasets:
- namruni/meb-ogretmen-soru-cevap
pipeline_tag: text-generation
model-index:
- name: meb-ogretmen-qwen3-14b-lora
  results:
  - task:
      type: multiple-choice
      name: Çoktan Seçmeli Soru-Cevap (Türkçe genel bilgi)
    dataset:
      name: TR-MMLU (mmlu split, 6200 soru)
      type: alibayram/turkish_mmlu
    metrics:
    - type: accuracy
      value: 62.56
      name: Doğruluk (accuracy)
---

# MEB Öğretmen Qwen3-14B LoRA

`unsloth/Qwen3-14B` tabanlı, **Millî Eğitim Bakanlığı öğretmenlerinin özlük ve mevzuat
sorularına** yanıt vermek üzere ince ayar (fine-tune) yapılmış bir **LoRA adaptörü**.

> ⚠️ Bu model uzmanlaşmış bir asistandır, genel bilgi modeli değildir. Aşağıdaki
> **Değerlendirme** ve **Sınırlamalar** bölümlerini mutlaka okuyun.

## Model Tanımı

| | |
|---|---|
| **Taban model** | `unsloth/Qwen3-14B` (14 milyar parametre) |
| **Tip** | LoRA adaptörü (birleştirilmiş/merged değil) |
| **Yöntem** | 4-bit QLoRA (unsloth) |
| **LoRA rank (r)** | 16 |
| **LoRA alpha** | 16 |
| **Max sequence length** | 2048 |
| **Eğitilebilir parametre** | 64,2M (%0,43) |
| **Eğitim verisi** | `namruni/meb-ogretmen-soru-cevap` — 450 örnek (405 eğitim / 45 doğrulama) |
| **Epoch** | 2 (overfitting nedeniyle 3'ten geri çekildi) |
| **Donanım** | L4 GPU, ~18 dakika |
| **Lisans** | Apache 2.0 |

## Kullanım Amacı

- **Hedef:** MEB öğretmenlerinin özlük hakları ve mevzuat (izin, atama, haklar vb.)
  konularında Türkçe soru-cevap.
- **Uygun kullanım:** İlgili mevzuat konularında ilk yönlendirme / taslak yanıt.
- **Uygun OLMAYAN kullanım:** Genel bilgi/akademik soru-cevap (bkz. Değerlendirme),
  bağlayıcı hukuki tavsiye, kaynak/madde numarası doğrulaması.

## Değerlendirme (TR-MMLU)

Model, **TR-MMLU** (`alibayram/turkish_mmlu`, `mmlu` split, 6200 soru; Bayram ve diğerleri)
üzerinde, **yalın taban modelle kontrollü bir kıyas** ile değerlendirilmiştir.

**Yöntem:** 4-bit yükleme · düşünme modu kapalı (`enable_thinking=False`) · greedy
(deterministik) · tek-harf cevap · doğruluk (accuracy). Base ve LoRA **birebir aynı 6200
soruda** koşuldu (adil/kontrollü deney; tek değişen = LoRA).

| Model | Doğru | Başarı |
|---|---|---|
| Yalın Qwen3-14B (kontrol) | 3995/6200 | **%64,44** |
| Qwen3-14B + bu LoRA (deney) | 3879/6200 | **%62,56** |

**Bulgu:** Fine-tune, genel bilgi başarısını **~1,9 puan düşürmüştür** (hafif "unutma" /
catastrophic forgetting). Konu-bazı kırılımda **tutarlı bir alan kazancı gözlenmemiştir**
(bölüm başına 100 soru olduğu için tekil farklar gürültü düzeyindedir).

### Konu-bazı kırılım (en çok değişen bölümler)

62 bölüm × 100 soru = 6200. ⚠️ 100 soruda belirsizlik payı **±~9 puan** olduğundan tekil
satırlar istatistiksel olarak anlamlı değildir; aşağıdaki liste yalnızca "en çok oynayan"
bölümleri gösterir.

| Bölüm | Base % | LoRA % | Fark |
|---|---|---|---|
| Adalet | 70,0 | 72,0 | +2,0 |
| Lojistik | 67,0 | 69,0 | +2,0 |
| Türk Dili ve Edebiyatı | 48,0 | 50,0 | +2,0 |
| Yaşlı Bakımı | 69,0 | 71,0 | +2,0 |
| Turizm ve Seyahat Hizmetleri | 61,0 | 63,0 | +2,0 |
| … | … | … | … |
| Spor Yönetimi | 65,0 | 59,0 | −6,0 |
| Özel Koruma ve Güvenlik | 68,0 | 62,0 | −6,0 |
| Aşçılık | 70,0 | 63,0 | −7,0 |
| Uluslararası Ticaret ve Lojistik Yönetimi | 69,0 | 62,0 | −7,0 |
| Yerel Yönetimler | 65,0 | 57,0 | −8,0 |

**Kırılım yorumu:** "İyileşen" bölümlerdeki +2'ler gürültü düzeyindedir (gerçek kazanç
değil). Düşüşler idari/mesleki alanlarda daha belirgin görünse de tek tek kesin değildir.
Kritik nokta: modelin fine-tune alanına (öğretmen özlük/mevzuat) en yakın görünen
bölümlerde bile **tutarlı bir kazanç yoktur** — ör. "Adalet" +2 (gürültü), "Yerel
Yönetimler" −8. Çünkü TR-MMLU'daki bu konular *genel sınav sorularıdır*, modelin öğrendiği
dar mevzuat soru-cevabı değildir.

**Yorum:** Bu beklenen bir sonuçtur. Modelin uzmanlaştığı alan (öğretmen özlük/mevzuat,
450 örnek), TR-MMLU'nun ölçtüğü **genel akademik bilgiyle örtüşmez**; dolayısıyla benchmark
bu uzmanlaşmayı ölçemez ve yalnızca genel yetenekteki küçük aşınmayı gösterir. Modelin asıl
değeri, **kendi alanındaki** bir değerlendirme ile ölçülmelidir (bkz. gelecek çalışma).

> Not: Sonuçlar, TR-MMLU liderlik tablosundaki `qwen3:14b` skorundan (%71,65) düşüktür;
> çünkü o skor farklı koşulda (Ollama `Q4_K_M`, düşünme modu açık) alınmıştır. Yalnızca
> aynı koşuldakiler kıyaslanmalıdır (like-with-like). Tam yöntem ve kod için repodaki
> `tr_mmlu_benchmark.ipynb` dosyasına bakınız.

## Sınırlamalar ve Riskler

- **Genel bilgi:** Taban modele göre ~1,9 puan daha düşüktür (yukarıya bakınız).
- **Kaynak atıfları güvenilmez:** Uydurma belge adı / madde numarası üretebilir.
- **Olgusal doğruluk garantili değildir**; kritik kullanımda RAG ile desteklenmelidir.
- **Yasal tavsiye değildir**; 2025–2026 dönemi verisine dayanır.

## Atıf

Değerlendirmede kullanılan TR-MMLU veri seti için Zenodo DOI ile atıf yapınız
(Bayram, M. Ali ve diğerleri — TR-MMLU, `alibayram/turkish_mmlu`).
