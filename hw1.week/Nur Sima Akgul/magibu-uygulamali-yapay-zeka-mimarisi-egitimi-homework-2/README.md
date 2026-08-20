# Magibu Uygulamalı Yapay Zeka Mimarisi Eğitimi — Ödevler

Bu repo, Magibu Uygulamalı Yapay Zeka Mimarisi Eğitimi kapsamındaki dört ödevden oluşan
bir çalışmayı içerir: bir alan verisi hazırlama, sıfırdan BPE tokenizer eğitme, seçilen
bir modeli fine-tune etme ve bir modele kimlik öğretme. Tüm çıktılar Hugging Face
profilimde yayınlanmıştır.

---

## Ödev Gereksinimleri

### 1. Ödev: Veri Seti (Dataset) Hazırlama
**Hedef:** Belirli bir alanda (domain) veri seti oluşturmak.

**Format:** `alibayram/identity_finetune_magibu_q3` veri setindeki formata gibi olmalı
(standardı bu).

**Yöntem:** Verileri web scraping ile toplamak artı puan kazandırır. Sentetik veri
kullanılacaksa, en az 10-20 örnek elle yazılıp model ile çoğaltılmalı; mevcut veri
setleri kullanılacaksa çok küçük kelime değişiklikleri yeterlidir.

### 2. Ödev: BPE Tokenizer Oluşturma
**Hedef:** Eğitilecek model için özel bir BPE Tokenizer oluşturmak.

**Süreç:** Tokenizer eğitilecek ve Hugging Face profilinde yayınlanacaktır.

### 3. Ödev: Model Fine-Tune Etme
**Hedef:** unsloth.ai üzerinden seçilen bir modeli eğitmek.

**Süreç:** Model; 1. ödevde hazırlanan veri seti kullanılarak eğitilecek, çıkan LoRA
adaptörü Hugging Face profilinde yayınlanacaktır.

### ➕ Ek Ödev: Yapay Zeka Kimlik Eğitimi (Identity Fine-Tuning)
**Not:** 1, 2 ve 3. ödevden bağımsız, ayrı bir süreçtir.

**Hedef:** Yapay zekaya kendi yaratıcısını, ismini ve görevlerini öğretmek.

**Süreç:** Hocanın Hugging Face deposundaki veri yapısı referans alınarak, AI'ın kendini
tanımlamasını sağlayacak bir veri seti oluşturulacak ve model bununla eğitilecektir.

**Ödevler tamamlandığında HF profilinde olması gerekenler:**
1 adet Veri Seti (Dataset), 1 adet BPE Tokenizer, 1 adet Model Fine-Tune LoRA Adaptörü.

---

## Hugging Face Bağlantıları

| Ödev | İçerik | Bağlantı |
|------|--------|----------|
| 1. Ödev | Veri Seti | https://huggingface.co/datasets/nursimakgul/meb-soru-uretme |
| 2. Ödev | BPE Tokenizer | https://huggingface.co/nursimakgul/turkce-bpe-tokenizer |
| 3. Ödev | Fine-Tune LoRA Adaptörü | https://huggingface.co/nursimakgul/gemma-3-1b-meb-soru-lora |
| Ek Ödev | Kimlik (Identity) LoRA Adaptörü | https://huggingface.co/nursimakgul/gemma-3-1b-ada-identity-lora |

---

## Ödev Açıklamaları

### 1. Ödev — Veri Seti

MEB müfredatına uygun Türkçe sorulardan oluşan bir veri seti hazırladım. Türkçe dil
verisi konusunda MEB müfredatı ve sorularının iyi, güvenilir ve geniş bir kaynak
olabileceğini düşündüm; bu yüzden bu verileri toparlayıp bir dil modelini fine-tune
etmeye uygun, standart bir sohbet (chat) formatına dönüştürdüm.

Veriyi hazırlarken referans formata (`alibayram/identity_finetune_magibu_q3`) birebir
uydum: her örnek, `user` (soru isteği) ve `assistant` (üretilen soru) mesajlarından
oluşan bir mesaj listesi. İstemleri sorunun gerçek konusunu (kazanımını) yansıtacak
şekilde kurarak istem-içerik tutarlılığını sağladım; boş/tekrar seçenek içeren veya
bozuk kayıtları temizledim; matematik sorularını bu sürümde kapsam dışı bıraktım. Sonuçta
yaklaşık 20.000 temiz örnek elde ettim.

### 2. Ödev — BPE Tokenizer

Sıfırdan (from-scratch) bir byte-level BPE tokenizer eğittim. Karpathy'nin
[minbpe](https://github.com/karpathy/minbpe) yaklaşımını ve HuggingFace LLM Course'un
BPE bölümündeki eğitim algoritmasını temel aldım. Byte-level yaklaşım sayesinde Türkçe
karakterler dâhil hiçbir karakter `[UNK]` olmuyor. Tokenizer'ı İstanbul'un tarihi
üzerine yazdığım özgün bir Türkçe metin üzerinde eğitip Hugging Face'e yükledim.

### 3. Ödev — Model Fine-Tune

1. ödevde hazırladığım veri setini kullanarak `unsloth/gemma-3-1b-it` modelini fine-tune
ettim. Eğitim için [Unsloth](https://github.com/unslothai/unsloth) kütüphanesini tercih
ettim; hızlı ve bellek dostu olduğu için Colab üzerinde rahatça çalışıyor. Yöntem olarak
LoRA (parametre-verimli fine-tune) ve 4-bit (QLoRA) nicemleme kullandım; sadece asistan
cevabı üzerinden eğitim yaptım (`train_on_responses_only`). Eğitim sonunda model, istenen
ders/konuya uygun ve doğru formatta (JSON) sorular üretmeye başladı. Çıkan LoRA adaptörünü
Hugging Face'e yükledim.

### Ek Ödev — Kimlik Eğitimi

Bir modele kendi kimliğini öğrettim: adı **Ada**, yaratıcısı **Nur Şima Akgül**. Referans
alınan kimlik veri setinin yapısını temel alıp, içindeki model adı ve yaratıcı bilgilerini
kendi kimliğimle değiştirdim; değişim sonrası bozulan Türkçe ekleri de düzelttim. Veri
Türkçe ve İngilizce olmak üzere iki dilde (~1600 örnek). Aynı fine-tune tekniğiyle
(Unsloth + LoRA + QLoRA) `unsloth/gemma-3-1b-it` modelini bu veriyle eğittim. Eğitim
sonunda model, "Sen kimsin?" / "Seni kim geliştirdi?" gibi sorulara Ada / Nur Şima Akgül
olarak tutarlı biçimde yanıt vermeye başladı.

---

## Repo İçeriği

- 1. Ödev — veri seti hazırlama dosyaları
- 2. Ödev — BPE tokenizer notebook'u (`bpe_tokenizer_sifirdan.ipynb`)
- 3. Ödev — fine-tune notebook'u (`gemma3_1b_finetune.ipynb`)
- Ek Ödev — kimlik fine-tune notebook'u (`gemma3_1b_identity_finetune.ipynb`)

## Not

Tüm çalışmalar eğitim/ödev amaçlıdır. Üretilen içeriklerin doğruluğu her zaman garanti
değildir; kullanılan temel modelin (Gemma 3 1B) boyut ve kapsam sınırları geçerlidir.
