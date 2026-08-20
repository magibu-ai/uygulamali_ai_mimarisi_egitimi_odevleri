# Benchmark & Analiz Raporu V2 — `gorkemergune/ayarlicazhocam-gemma-4-e4b`

**Tarih:** 2026-07-30
**Model:** LoRA (QLoRA 4-bit) fine-tune · base = `google/gemma-4-E4B-it` (instruct, text-only)
**Değerlendirme ortamı:** Windows 11, RTX 5070 (12 GB, Blackwell), yerel — Colab yok
**v1 ile karşılaştırma:** [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md) (Llama-3.2-3B, bozuk template)

---

## 1. Özet (TL;DR)

| Bulgu | v1 (Llama-3.2-3B) | v2 (Gemma 4 E4B) |
| --- | --- | --- |
| **Kimlik ("Görkem kimdir?")** | Her seferinde **farklı uydurma** biyografi (oyuncu, İTÜ, blockchain…) | **Tutarlı ve doğru**: "Yeditepe'de bilgisayar mühendisliği… AI/ML" ✅ |
| **Talimat takibi (MC formatı)** | %0 — hep prompt echo | Çalışıyor (MC %85) ✅ |
| **Thinking mode** | Yok | Çalışıyor — `<\|channel>thought` bloğu üretiyor ✅ |
| **Tool-calling** | Yok | **%17 → %92** (12 senaryo, base vs fine-tune) ✅ |
| **mihenk-benchmark (genel)** | ~%20 (rastgele baz) | **%75 → %67.5** (fine-tune sonrası **gerileme**) ⚠️ |

**Sonuç:** v1'in iki büyük hatası (yanlış chat template → kimlik öğrenilmiyor + talimat takibi
bozuk) v2'de **çözüldü**. Kimlik bilgisi kalıcı ve tutarlı öğrenildi, thinking ve tool-calling
kazanıldı. **Bedeli:** genel akıl yürütme benchmark'ında ölçülü bir gerileme (−7.5 puan), ağırlıklı
olarak kısa-cevap formatında — ki bunun büyük kısmı gerçek yetenek kaybı değil, persona'nın
cevapları "sohbet" tarzına kaydırması (aşağıda ayrıştırıldı).

---

## 2. v1 → v2: Ne değişti

| | v1 | v2 |
| --- | --- | --- |
| Base model | `unsloth/Llama-3.2-3B` (base, instruct değil) | `google/gemma-4-E4B-it` (instruct) |
| Chat template | **Gemma-3 template'i Llama'ya** (kök hata) | Modelin kendi `AutoProcessor`'ından — asla elle yazılmadı |
| Thinking | — | `reasoning` kanalı, örneklerin ~%20'sinde (native on/off kontrolü korunuyor) |
| Tool-calling | — | 152 çok-turlu örnek (hava, birim, arXiv, ders, hesap), ×3 oversample |
| Dataset | `ayarlicazhocam_finetune` | `ayarlicazhocam_finetune_v2` (2117 train / 40 val) |
| Yöntem | Unsloth, `train_on_responses_only` | Vanilla transformers+peft QLoRA, token-seviyesi maskeleme |

### Neden Unsloth değil?
Unsloth `transformers<=5.5.0` gerektiriyor; Gemma 4 (`gemma4_unified`) ise `transformers>=5.10`
istiyor. Unsloth'un Gemma 4 patch'leri 5.14'te import oluyor ama desteklenmeyen bir konfigürasyon —
bu tam da v1'i bozan "sessiz uyumsuzluk" sınıfı. Kontrolü elde tutmak için vanilla peft QLoRA seçildi.

### Neden E4B, "12B" değil?
Hedef `gemma-4-12B` idi; ancak 12 GB VRAM sınırı ve riski azaltmak için **önce E4B** kararlaştırıldı
(kullanıcı kararı). Model dürüstlük gereği `-e4b` adıyla yayınlandı — "12b" demek yanıltıcı olurdu.
12B, aynı pipeline ile sonraki adım (bkz. Bölüm 8).

---

## 3. Kimlik / Persona (v1'in en büyük hatası — çözüldü)

v1 aynı soruya her koşuda **bambaşka uydurma** cevap veriyordu. v2 tutarlı ve dataset'le uyumlu:

| Soru | BASE (fine-tune öncesi) | FINE-TUNED |
| --- | --- | --- |
| Sen kimsin? | "Ben Gemma 4… Google DeepMind…" | "Ben ayarlicazhocam'ın asistanıyım. Görkem Ergüne'nin projeleri…" ✅ |
| Görkem Ergüne kimdir? | "…hakkında bilgim yok" | "**Yeditepe'de bilgisayar mühendisliği** okuyan… AI, ML, CV, NLP…" ✅ |
| ayarlicazhocam ne işe yarar? | "'ayarlayacağız hocam'…" (yanlış yorum) | "Görkem'in geliştirdiği AI asistanı…" ✅ |

Cevaplar **tekrar çalıştırıldığında da tutarlı** — v1'in aksine bilgi ağırlıklara yazıldı.

---

## 4. Thinking Mode

`enable_thinking=True` ile model `<|channel>thought … <channel|>` bloğu üretip sonra cevaplıyor.
Örnek (fine-tuned): *"3 vagon × 24 kişi = 72. Basit bir çarpma."* → *"Toplam 72 kişi."*
Örneklerin sadece ~%20'si thinking-on eğitildiği için model **her iki modu** da yapabiliyor
(native on/off kontrolü korundu).

---

## 5. Tool-Calling: %17 → %92

12 elle yazılmış senaryo (5 eğitimde görülen araç + 1 **görülmemiş** araç + 2 negatif). Doğru araç
+ tetikleme oranı:

| Senaryo tipi | BASE | FINE-TUNED |
| --- | --- | --- |
| Doğru araç çağırma (10 pozitif) | 0/10 | 9/10 |
| Negatif (araç çağırmama, 2) | 2/2 | 2/2 |
| **Toplam** | **2/12 (%17)** | **11/12 (%92)** |

- **Görülmemiş araç** (`get_stock_price`, eğitimde yok) doğru çağrıldı → format genelleşti.
- Negatiflerde over-triggering yok ("Merhaba nasılsın?" → araç yok).
- Tek hata: "144 bölü 12" → `calculate` yerine `convert_units` (bölme/çevrim karışması).
- BASE %17: taban model verilen araçlar için Gemma 4 tool-call token'ını üretmiyor (düz metinle
  yanıtlıyor); yani bu format öğrenilmiş bir kazanım.

---

## 6. mihenk-benchmark (public split, 80 soru) — dürüst gerileme

Standart koşul: 0-shot, thinking kapalı, greedy. Resmi `scoring/score.py` kullanıldı.

| | Genel | Çoktan seçmeli | Kısa cevap | EN | TR |
| --- | --- | --- | --- | --- | --- |
| **Base** | %75.0 | %87.5 | %62.5 | %67.5 | %82.5 |
| **Fine-tuned** | %67.5 | %85.0 | **%50.0** | %60.0 | %75.0 |
| **Δ** | **−7.5** | −2.5 | **−12.5** | −7.5 | −7.5 |

**Gerileme gerçek ama abartılı görünüyor.** Kısa-cevap (SA) düşüşünün büyük kısmı **format/uzunluk**
kaynaklı, akıl yürütme kaybı değil: persona fine-tune'u cevapları daha "konuşkan" hale getiriyor,
SA puanlaması ise ≤7 kelime + birebir/sayısal eşleşme istiyor. Base'in doğru olup fine-tune'un
"yanlış" sayıldığı 8 SA sorusunun analizi:

- *"Mitokondri — hücresel solunum ile ATP üretir"* → doğru ama "mitokondri" ile birebir eşleşmiyor.
- *"24 TL, 4 TL × 6 = 24"* → doğru ama **8 kelime → otomatik 0**.
- *"Yes, a single black swan refutes the generalization"* → doğru ama 8 kelime → 0.
- Yalnızca ~3/8 **gerçek** akıl yürütme hatası (23≠25, len=3≠4, 7A≠7B).

Yani temiz sinyal olan **MC gerilemesi sadece −2.5 puan**. Not: 80 soruluk küçük örneklem, ±birkaç
puan gürültü içerir.

---

## 7. Karşılaşılan sorunlar (gizlenmedi)

1. **Ortam:** Global Python'da torch CPU-only idi; RTX 5070 (sm_120) için `cu128` build ile yeni venv kuruldu.
2. **Gemma 4 çok büyük görünüyordu (11 GB 4-bit):** Model multimodal (görüntü+ses kuleleri) + elastik
   per-layer-embedding (PLE, 5.64 GB). Çözüm: text-only backbone'u 4-bit GPU'da, kuleleri + PLE'yi CPU'da;
   `prepare_model_for_kbit_training`'in embedding'leri fp32'ye çıkarması (OOM bombası) geri alındı → yük 9→3.4 GB.
3. **`lm_head` bnb hatası:** embeddings'e tied; `skip_modules`'a eklendi.
4. **PEFT `Gemma4ClippableLinear` hatası:** kulelerdeki custom linear; LoRA sadece `language_model`'e
   regex ile hedeflendi.
5. **Sessiz thinking kaybı (kritik, v1-tipi):** Gemma 4 template'i `thinking` alanını **sessizce
   siliyor**, doğru alan `reasoning`. Zorunlu round-trip testi bunu ölçekli üretimden önce yakaladı.
6. **Maskeleme (v1'in %93 veri kaybı hatası):** string-marker yerine token-seviyesi state machine;
   %91 supervised, sadece 4 satır düştü; tool-response span'leri maskelendi (model tool çıktısı uydurmasın).
7. **Benchmark gerilemesi:** Bölüm 6 — persona uzmanlaşması genel SA formatına zarar verdi.

---

## 8. Sonraki adımlar

- **12B:** Aynı pipeline `google/gemma-4-12B-it` ile (text-only backbone 4-bit ≈ 6.5 GB, 12 GB'a sığar).
- **SA gerilemesini azalt:** persona verisine bir miktar kısa/öz cevap örneği ekle; ya da benchmark'ı
  thinking-on koş (akıl yürütme formatına daha uygun).
- **Tool verisi çeşitliliği:** 152 örnek şablon-ağırlıklı; değer/araç çeşitliliği artırılmalı.
- **Daha büyük mihenk alt kümesi** ile gürültüyü azalt (80 → private split dahil).

---

## Ekler
- Dataset: [`gorkemergune/ayarlicazhocam_finetune_v2`](https://huggingface.co/datasets/gorkemergune/ayarlicazhocam_finetune_v2)
- Model (adapter): [`gorkemergune/ayarlicazhocam-gemma-4-e4b`](https://huggingface.co/gorkemergune/ayarlicazhocam-gemma-4-e4b)
- Eğitim/değerlendirme scriptleri: [`src/phase*.py`](src/), maskeleme: [`src/mask_utils.py`](src/mask_utils.py)
- Ham benchmark sonuçları: [`results_benchmark_v2.json`](results_benchmark_v2.json)
