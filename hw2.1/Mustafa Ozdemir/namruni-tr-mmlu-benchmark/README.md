# TR-MMLU Benchmark — MEB Öğretmen LoRA vs Yalın Qwen3-14B

Fine-tune edilmiş bir Türkçe modeli (`namruni/meb-ogretmen-qwen3-14b-lora`), taban modeli
`unsloth/Qwen3-14B` ile **TR-MMLU** benchmark'ı üzerinde kontrollü olarak kıyaslayan bir
değerlendirme çalışması.

## Amaç

"Benchmark nedir, nasıl uygulanır?" sorusunu uçtan uca öğrenmek ve fine-tune edilmiş
modelin genel bilgi başarısını objektif olarak ölçmek.

## Yöntem

- **Benchmark:** [TR-MMLU](https://huggingface.co/datasets/alibayram/turkish_mmlu)
  (`mmlu` split, 6200 çoktan seçmeli soru; Bayram ve diğerleri, arXiv:2501.00593).
- **Kontrollü deney:** Base ve LoRA, birebir aynı 6200 soruda koşuldu. Tek değişen = LoRA.
- **Koşullar:** 4-bit yükleme · düşünme modu kapalı · greedy (deterministik) · tek-harf
  cevap · doğruluk (accuracy). Colab GPU üzerinde `unsloth` ile.

## Sonuçlar

| Model | Doğru | Başarı |
|---|---|---|
| Yalın Qwen3-14B (kontrol) | 3995/6200 | **%64,44** |
| Qwen3-14B + MEB LoRA (deney) | 3879/6200 | **%62,56** |

**Bulgu:** Dar alandaki (öğretmen özlük/mevzuat, 450 örnek) fine-tune, genel bilgi
başarısını **~1,9 puan düşürdü** (hafif "unutma"). Konu-bazı kırılımda tutarlı bir alan
kazancı görülmedi — çünkü fine-tune alanı, TR-MMLU'nun ölçtüğü genel akademik bilgiyle
örtüşmüyor. **Ders:** Bir benchmark yalnızca kendi ölçtüğü şeyi ölçer.

## Dosyalar

- `tr_mmlu_benchmark.ipynb` — değerlendirme notebook'u (Colab'da çalışır, hücre hücre).
- `MODEL_KARTI.md` — modelin HuggingFace model kartı taslağı (benchmark sonuçları dahil).

## Çalıştırma

1. Notebook'u Google Colab'da aç (GPU: L4/A100).
2. TR-MMLU veri seti *gated*: HF sayfasında şartları kabul et.
3. Hücreleri sırayla çalıştır. Pilot (~100 soru) → tam set (6200).

## Sınırlama

Sonuçlar, TR-MMLU liderlik tablosundan (%71,65) düşüktür; çünkü o skor farklı koşulda
(Ollama `Q4_K_M`, düşünme açık) alınmıştır. Yalnızca aynı koşuldakiler kıyaslanmalıdır.
