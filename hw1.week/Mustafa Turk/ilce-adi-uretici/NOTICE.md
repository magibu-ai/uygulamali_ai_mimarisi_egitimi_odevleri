# Kaynaklar ve Katkılar

Bu proje bir ders ödevidir. Aşağıda hangi dosyanın kime ait olduğu listelenmiştir.

## Model mimarisi

`qwen3/` klasöründeki model kodu
[malibayram/single_letter_transformers](https://github.com/malibayram/single_letter_transformers)
reposundan alınmıştır. Bu ödevin verildiği ders kapsamında kullanılmıştır.

| Dosya | Durum |
|-------|-------|
| `qwen3/model.py` | upstream, değiştirilmedi |
| `qwen3/attention.py` | upstream, değiştirilmedi |
| `qwen3/block.py` | upstream, değiştirilmedi |
| `qwen3/config.py` | upstream, değiştirilmedi |
| `qwen3/mlp.py` | upstream, değiştirilmedi |
| `qwen3/rms_norm.py` | upstream, değiştirilmedi |
| `qwen3/rotary.py` | upstream, değiştirilmedi |
| `qwen3/tokenizer.py` | upstream, değiştirilmedi (karşılaştırma için tutuldu) |
| `qwen3/train_tiny3.py` | upstream, değiştirilmedi (bu ödevde kullanılmadı) |
| `data/temizle_isimler.py` | upstream, değiştirilmedi |
| `qwen3/train.py` | upstream **+ 4 satır değişiklik** (tokenizer bağlantısı) |
| `qwen3/generate.py` | upstream **+ 2 satır değişiklik** (tokenizer bağlantısı) |

Upstream repoda bu yazının yazıldığı tarihte bir lisans dosyası bulunmamaktadır.
Kod, ödev kapsamında ve kaynak belirtilerek kullanılmıştır.

## Bana ait dosyalar

| Dosya | Ne yapar |
|-------|----------|
| `qwen3/bpe_tokenizer.py` | BPE algoritmasının sıfırdan implementasyonu (**Ödev 1**) |
| `qwen3/egit_tokenizer.py` | Tokenizer'ı eğitir, `tokenizer.json` üretir, ne öğrendiğini raporlar |
| `qwen3/karsilastir.py` | Char vs BPE karşılaştırması, bits-per-character hesabı |
| `data/hazirla.py` | Veri setini indirir, ilçe/köy adlarını ayıklar ve temizler |
| `README.md` | Proje dokümantasyonu ve sonuçlar |

## Veri

[nejdetkadir/il-ilce-semt-mahalleler](https://github.com/nejdetkadir/il-ilce-semt-mahalleler)
— Türkiye il/ilçe/semt/mahalle listesi. `data/hazirla.py` bu veriyi indirip işler.

## Algoritma referansı

BPE implementasyonu
[Hugging Face LLM Course, Chapter 6.5](https://huggingface.co/learn/llm-course/en/chapter6/5)
temel alınarak yazılmıştır. Hazır tokenizer kütüphanesi (`tokenizers`, `transformers`)
kullanılmamıştır.

Orijinal makale: Sennrich, R., Haddow, B., & Birch, A. (2016).
*Neural Machine Translation of Rare Words with Subword Units.* ACL.

## Yardım beyanı

_(Aldığın yardımı buraya yaz. Örnek:)_

BPE implementasyonu ve analiz scriptleri, Hugging Face LLM Course Chapter 6.5
temel alınarak Claude (Anthropic) ile birlikte geliştirilmiştir. Algoritmanın
çalışma mantığı, tasarım kararları (vocab boyutu seçimi, arayüz uyumluluğu) ve
sonuçların yorumlanması tarafımdan anlaşılmış ve doğrulanmıştır.
