# Gemma 3 1B Fine-Tune — MEB Soru Üretici

Bu repo, MEB müfredatına uygun Türkçe eğitim soruları üreten bir dil modeli fine-tune
etme çalışmamı içerir. Temel model olarak `unsloth/gemma-3-1b-it` kullandım; LoRA
yöntemiyle eğitip çıkan adaptörü Hugging Face'te yayınladım.

🤗 **Model (LoRA adaptörü):** [nursimakgul/gemma-3-1b-meb-soru-lora](https://huggingface.co/nursimakgul/gemma-3-1b-meb-soru-lora)
🤗 **Veri seti:** [nursimakgul/meb-soru-uretme](https://huggingface.co/datasets/nursimakgul/meb-soru-uretme)

## İçerik

- `gemma3_1b_finetune.ipynb` — modeli eğiten, test eden ve LoRA adaptörünü Hugging
  Face'e yükleyen Colab notebook'u

## Amaç

Kullanıcı bir sınıf, ders ve konu belirttiğinde (örneğin "8. sınıf Türkçe - Fiilimsiler
konusunda orta seviyede çoktan seçmeli soru üret"), modelin o konuya uygun bir soru
üretmesini istedim. Çıktı, çoktan seçmeli sorularda yapılandırılmış (JSON) bir biçimde
gelir: soru metni, seçenekler, doğru cevap ve cevap açıklaması.

## Kullandığım veri seti ve neden

Veri setini MEB kaynaklarından üretilen sorulardan derledim. Türkçe dil verisi konusunda
MEB müfredatı ve sorularının iyi, güvenilir ve geniş bir kaynak olabileceğini düşündüm;
bu yüzden bu verileri toparlayıp bir dil modelini fine-tune etmeye uygun, standart bir
sohbet (chat) formatına dönüştürdüm.

Veri hazırlarken şunlara dikkat ettim:

- **Format:** Her örnek, `user` (soru isteği) ve `assistant` (üretilen soru) mesajlarından
  oluşan bir mesaj listesi. Bu yapı, referans alınan sohbet veri seti formatıyla uyumlu.
- **İstem–içerik tutarlılığı:** İstemleri, sorunun gerçek konusunu (kazanımını) yansıtacak
  şekilde kurdum; böylece "X konusu iste, Y konusunda soru gel" gibi tutarsızlıkları
  temizledim.
- **Temizlik:** Boş/tekrar eden seçenek içeren ya da çok kısa/bozuk kayıtları ayıkladım.
- **Kapsam:** Fen Bilimleri, Türkçe, Sosyal Bilgiler, İngilizce, Din Kültürü ve İnkılap
  Tarihi derslerini dâhil ettim; matematik sorularını bu sürümde kapsam dışı bıraktım.

Sonuç olarak yaklaşık 20.000 temiz örnekten oluşan bir veri seti elde ettim.

## Model eğitim tekniği

- **Temel model:** `unsloth/gemma-3-1b-it`
- **Kütüphane:** [Unsloth](https://github.com/unslothai/unsloth) — Colab üzerinde hızlı
  ve bellek dostu fine-tune sağladığı için tercih ettim.
- **Yöntem:** LoRA (Low-Rank Adaptation) ile parametre-verimli fine-tune. Modelin tüm
  ağırlıklarını değil, eklenen küçük LoRA katmanlarını eğittim; bu sayede eğitim hem hızlı
  hem de düşük bellekle mümkün oldu.
- **Nicemleme (quantization):** 4-bit (QLoRA) — modeli 4-bit yükleyerek bellek kullanımını
  düşürdüm.
- **LoRA ayarları:** r=16, alpha=16, hedef modüller q/k/v/o_proj ve gate/up/down_proj.
- **Eğitim:** 2 epoch. Sadece asistan cevabı üzerinden eğitim yaptım
  (`train_on_responses_only`); böylece model soruyu değil, üretmesi gereken cevabı öğrendi.

## Sonuç ve gözlem

Eğitim sonunda model, istenen ders/konuya uygun ve doğru formatta (JSON) sorular
üretmeye başladı — eğitim öncesi çıktılarla karşılaştırıldığında format ve konu
tutarlılığının net şekilde öğrenildiği görülüyor. 1B'lik görece küçük bir model
kullandığım için üretilen soruların içeriği her zaman kusursuz olmayabiliyor; bu, model
boyutunun doğal bir sınırı. Amaç, veri setinin ve fine-tune sürecinin çalıştığını
göstermekti ve bu anlamda sonuç başarılı.

## Kullanım

Eğitilen LoRA adaptörünü temel modelle birlikte yükleyerek kullanabilirsiniz:

```python
from unsloth import FastModel

model, tokenizer = FastModel.from_pretrained(
    "nursimakgul/gemma-3-1b-meb-soru-lora", load_in_4bit=True
)

messages = [{"role": "user", "content": "5. sınıf Fen Bilimleri - Güneş, Dünya ve Ay konusunda orta seviyede çoktan seçmeli soru üret."}]
inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(model.device)
out = model.generate(input_ids=inputs, max_new_tokens=256, temperature=0.8, do_sample=True)
print(tokenizer.decode(out[0][inputs.shape[1]:], skip_special_tokens=True))
```

## Not

Üretilen sorular eğitim/araştırma amaçlıdır; doğrudan sınavda kullanım için ek kontrol
gerekebilir.
