# Benchmark & Analiz Raporu — `gorkemergune/ayarlicazhocam-llama-3.2-3b`

**Tarih:** 2026-07-23
**Model:** LoRA fine-tune, base = `unsloth/Llama-3.2-3B` (base, instruct değil)
**Değerlendirme ortamı:** macOS (16 GB, Apple Silicon) · ollama · q8_0 GGUF · merge edilmiş adaptör

---

## 1. Özet (TL;DR)

| Bulgu                                            | Sonuç                                                                                 |
| ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Türkçe MMLU başarısı                        | **%20.65** — 5 şıklı soruda rastgele baz (%20) ile **aynı**           |
| Liderlik tablosundaki yer                        | **61 / 67** (en altta)                                                           |
| Aynı boyuttaki stok model (`llama3.2:latest`) | %44.95 —**iki katından fazla**                                                 |
| Çoktan seçmeli formatı takip etme             | **%0** (model hep prompt'u echo'luyor / serbest metin)                           |
| "Görkem kimdir?"                                | **Her seferinde farklı, dataset'te olmayan uydurma biyografi**                  |
| Kök neden                                       | (1) Yanlış chat template (gemma-3, Llama'ya) + (2) dar veri / base modelden başlama |

**Sonuç:** Fine-tune, modelin genel yeteneğini yükseltmedi — düşürdü. Persona bilgisi (Görkem) da kalıcı olarak öğrenilmedi; model base-model davranışına geri dönüp halüsinasyon görüyor.

---

## 2. MMLU Benchmark Sonuçları

Profesörün `mmlu_script.py`'sinin lokal, güvenli sürümü ile ölçüldü (aynı `cevap_dogru_mu`
puanlama mantığı korundu; `push_to_hub` çağrıları — üçüncü kişinin herkese açık repolarına
yazıyordu — devre dışı bırakıldı).

- **Dataset:** `alibayram/yapay_zeka_turkce_mmlu_model_cevaplari` — 6200 soru, 62 bölüm × 100, hepsi 5 şıklı.
- **Örneklem:** Her bölümden 5 soru (stratified, 310 soru). Bölüm dağılımı tam setle orantısal olarak birebir aynı → temsili.
- **Neden tam 6200 değil:** Bu Mac'te ~11 saat sürüyordu; 30 ve 310 soruluk iki bağımsız koşu da aynı (rastgele) sonucu verdi.

| Koşu                      | Soru          | Doğru       | Başarı         |
| -------------------------- | ------------- | ------------ | ---------------- |
| Ön test                   | 30            | 8            | %26.67           |
| **Stratified (ana)** | **310** | **64** | **%20.65** |

### Liderlik tablosundaki yer

```
  1. gpt-4o ......................... 84.84%
  2. claude-3-5-sonnet .............. 84.40%
  3. llama3.3:latest (70B) .......... 79.42%
 ...
 44. llama3.2:latest (3.2B) ........ 44.95%   ← AYNI BOYUT, stok instruct
 45. gemma3:1b (1B!) ............... 42.74%   ← 1B model bile 2x daha iyi
 ...
 59. qwen3:0.6b (0.6B) ............. 21.65%
 60. qwen2.5:0.5b (0.5B) ........... 21.23%
 61. >>> SİZİN MODEL (3.2B) ........ 20.65%   ← BURADA
 62. Turkcell-LLM-7b ............... 19.50%
 63. tinyllama (1B) ................ 19.44%
 64. Doktor-Llama-3-8b ............. 19.23%
```

3.2B'lik modeliniz, **0.5B'lik bir modelle aynı** ve **stok `llama3.2:latest`'in yarısı**
seviyesinde skor aldı. Komşuları bozuk/dar fine-tune'lar (Turkcell, tinyllama, Doktor-Llama).

---

## 3. Neden bu kadar düşük? — Çoktan seçmeli formatını hiç takip etmiyor

- **Temiz tek-harf (A/B/C…) cevap oranı: %0.0.** Model tek bir soruda bile "B" gibi net cevap vermedi.
- Tipik çıktılar (cevap üretmek yerine):| Model çıktısı                                              | Sorun                               |
  | -------------------------------------------------------------- | ----------------------------------- |
  | `user: Sana soru ve seçenekleri veriyorum. sadece hangi...` | Prompt'u**echo**'luyor        |
  | `Soru ve seçenekleri: Buzullaşma dönemlerinde...`         | Soruyu tekrar yazıyor, cevap yok   |
  | `A ve B doğru. C yanlış çünkü...`                      | Serbest sohbet, tek şıkka inmiyor |

%20.65'lik skorun neredeyse tamamı benchmark'ın **anlamsal benzerlik "kurtarma"sından** gelir
(bkz. Bölüm 6) — modelin gerçek katkısı ≈ sıfır.

---

## 4. Halüsinasyon Analizi — "Görkem kimdir?" (dataset'te olmayan cevaplar)

### Dataset'teki GERÇEK bilgi (eğitim verisi, 720/2009 kayıt Görkem içeriyor)

> **Görkem Ergüne** — Yeditepe Üniversitesi **Bilgisayar Mühendisliği öğrencisi**, aynı zamanda
> **AI Product Developer**. İstanbul. Yapay zeka, makine öğrenimi ile ilgileniyor.

Dataset'te "Görkem Ergüne kimdir?" sorusuna net, tutarlı kimlik cevapları **var** (TR + EN).

### Modelin ÜRETTİĞİ cevaplar (her koşuda farklı, hepsi UYDURMA)

| Soru                    | Model çıktısı                                                                                | Gerçek mi?                      |
| ----------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------- |
| Görkem kimdir?         | "…yazılım geliştiricisi ve**GitHub Premium üyesi**…"                                 | ❌ Uydurma                       |
| Görkem Ergüne kimdir? | "**25 yaşında**… **İTÜ**'de… **New York Üniversitesi**'nde veri bilimi" | ❌ Yanlış üniversite/yaş     |
| Görkem Ergüne kimdir? | "…**blockchain ve metaverse** dünyasının en aktif isimlerinden, 2015'ten beri…"       | ❌ Uydurma                       |
| Who is Gorkem Ergune?   | "…Turkish**actor and model**… **Vogue Turkey** kapağı… TV dizileri…"           | ❌ Tamamen uydurma               |
| Who is Gorkem Ergune?   | "…**Koç University**… **Google, Facebook**'ta çalıştı…"                      | ❌ Yanlış üniversite/işveren |

**Kritik gözlem:** Aynı soruya her çalıştırmada **bambaşka bir biyografi** üretiyor. Dataset'te
net cevap olmasına rağmen model onu vermiyor.

### Neden halüsinasyon görüyor? (Sebep)

1. **Bilgi ağırlıklara yazılmadı.** Template kusuru (Bölüm 5) yüzünden LoRA, "Görkem = Yeditepe /
   AI Product Developer" gerçeğini kalıcı olarak öğrenemedi. Fine-tune, ağırlıkların
   **dağılımını kaydırır** (retrieval yapmaz); sinyal zayıf olduğunda gerçek "tutmaz".
2. **Base model önceliği (prior) baskın.** "Görkem Ergüne" girdisi, base modelin öğrendiği
   "Türkçe isim → biyografi" dağılımını tetikliyor; model gerçeği hatırlamak yerine
   **istatistiksel olarak olası** ama yanlış metin üretiyor (oyuncu, blockchain, İTÜ, Google…).
3. **Tutarsızlık = öğrenmedi kanıtı.** Bir gerçeği *bilen* model her seferinde aynı cevabı verir.
   Bu modelin her koşuda farklı uydurması, bilgiyi **öğrenmediğinin** en net göstergesi
   (sampling sıcaklığı her seferinde farklı bir "yalanı" örnekliyor).
4. **Dar overfit + catastrophic forgetting.** Persona verisi dar (Görkem/teknik Q&A); base
   modelden (instruct değil) başlanmış. Model biraz Görkem-teması kaptı ama genel bilgi ve
   talimat-takibi yeteneğini kaybetti.

---

## 5. Kök Neden: Yanlış Chat Template (Gemma-3 → Llama)

HF'deki adaptörün `chat_template.jinja` dosyası çekildi: **hâlâ Gemma-3 template'i**
(`<start_of_turn>` / `<end_of_turn>` / `role="model"`).

- Bu token'lar **Llama sözlüğünde özel token değil** → düz metin olarak parçalanır → turn yapısı
  zayıf öğrenilir → talimat takibi bozulur.
- Orijinal eğitimde `train_on_responses_only`, response marker'ı bulamadığı için **2009 örneğin
  1872'sini attı** (sadece 137 örnek eğitildi). Epoch artırılsa bile template bozuk olduğu için
  gerçekler ağırlıklara güçlü yazılamadı.
- İlk konuşmada notebook `llama-3.1` template'iyle düzeltildi; **ancak HF'ye yüklenen model hâlâ
  eski (bozuk) sürüm.**
