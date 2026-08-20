# MIHENK — Changelog

Anlamsal sürümleme: **majör** (2.0) şema/yapı değişiklikleri, **minör** (1.1) yeni
soru ekleri, **yama** (1.0.1) düzeltmeler. Her sürümde eklenen/çıkarılan/düzeltilen
sorular kaydedilir.

## [1.0] — 2026-07-28

### Eklendi (Faz 1 — Pilot Set)
- İlk pilot soru bankası: **20 disiplin × 2 dil (tr/en) × 2 format (MC/short_answer) × 10 soru = 800 soru**.
- Zorluk dağılımı disiplin başına yaklaşık L1:2-3, L2:3-4, L3:2-3, L4:1-2.
- JSON şeması (`schema/question_schema.json`) ve doğrulayıcı (`scripts/validate.py`).
- Otomatik puanlama betikleri (`scoring/score.py`, `scoring/normalize.py`).
- `split` alanı: her soru `public` (HF örnek split, ~%10-15) veya `private` (holdout).
- HuggingFace public sample üreticisi (`scripts/build_hf.py`).

### Değişiklikler (1.0 hazırlık)
- `explanation` alanı tüm kayıtlarda **İngilizce** (Türkçe sorular dâhil) — uluslararası
  incelemeciler için dilden bağımsız meta veri; modele hiçbir zaman gösterilmez.
- README ve HF dataset card akademik İngilizceye getirildi.
- Public/private split **zorluk-dengeli** hâle getirildi (`scripts/assign_splits.py`):
  disiplin başına L1–L4 birer public, toplam 80 public (20/tier).
- Model değerlendirme aracı eklendi (`scripts/evaluate.py`): standart 0-shot koşullar,
  disiplin/dil/zorluk/format doğruluğu + dil tutarlılık endeksi.

### Notlar
- Tüm sorular sıfırdan özgün üretilmiştir; `source: "orijinal-AI-üretim"`.
- ÖSYM/telifli sınav bankalarından hiçbir soru kopyalanmamış veya türetilmemiştir;
  yalnızca stil/zorluk referansı alınmıştır.
