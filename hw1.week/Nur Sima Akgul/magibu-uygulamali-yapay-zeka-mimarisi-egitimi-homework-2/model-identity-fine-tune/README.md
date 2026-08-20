# Kimlik (Identity) Fine-Tune — Ada

Bu repo, bir dil modeline kendi kimliğini öğretme çalışmamı içerir. `unsloth/gemma-3-1b-it`
modelini, hazırladığım bir kimlik veri setiyle fine-tune ederek modele kendi adını
(**Ada**) ve yaratıcısını (**Nur Şima Akgül**) öğrettim. Çıkan LoRA adaptörünü Hugging
Face'te yayınladım.

🤗 **Model (LoRA adaptörü):** [nursimakgul/gemma-3-1b-ada-identity-lora](https://huggingface.co/nursimakgul/gemma-3-1b-ada-identity-lora)

## İçerik

- `gemma3_1b_identity_finetune.ipynb` — modeli eğiten, kimliğini test eden ve LoRA
  adaptörünü Hugging Face'e yükleyen Colab notebook'u

## Amaç

Modelin kendini tutarlı bir kimlikle tanıtmasını istedim. "Sen kimsin?" ya da "Seni kim
geliştirdi?" gibi sorulara, adının **Ada**, yaratıcısının **Nur Şima Akgül** olduğunu
söyleyerek yanıt vermesini hedefledim.

## Kullandığım veri seti ve neden

Kimlik veri setini, referans alınan bir kimlik veri setinin yapısını temel alarak
oluşturdum. Referans veri; bir yapay zekânın kendini, doğasını, yeteneklerini ve
sınırlarını nasıl tanımladığına dair soru-cevap örneklerinden oluşuyor. Bu yapıyı
kullanmamın nedeni, kimlik öğretiminde iyi kurgulanmış, çeşitli ve tutarlı bir örnek
kümesi sağlaması.

Veriyi kendi kimliğime uyarlamak için, referanstaki model adı ve yaratıcı bilgilerini
(orijinaldeki isimleri) kendi bilgilerimle değiştirdim:

- Model adı → **Ada**
- Yaratıcı → **Nur Şima Akgül**

Değiştirme sonrası bozulan Türkçe ekleri (örneğin isim değişince oluşan yazım
düzensizliklerini) de düzelterek dili tutarlı hâle getirdim. Veri hem **Türkçe** hem
**İngilizce** olmak üzere iki dilde; toplam yaklaşık 1600 örnek.

## Model eğitim tekniği

- **Temel model:** `unsloth/gemma-3-1b-it`
- **Kütüphane:** [Unsloth](https://github.com/unslothai/unsloth) — hızlı ve bellek dostu
  fine-tune sağladığı için tercih ettim.
- **Yöntem:** LoRA (Low-Rank Adaptation) ile parametre-verimli fine-tune; 4-bit (QLoRA)
  nicemleme ile düşük bellek kullanımı.
- **LoRA ayarları:** r=16, alpha=16, hedef modüller q/k/v/o_proj ve gate/up/down_proj.
- **Eğitim:** 3 epoch. Kimlik veri seti görece küçük olduğu için, modelin kimliği iyi
  benimsemesi adına epoch sayısını biraz yüksek tuttum. Sadece asistan cevabı üzerinden
  eğitim yaptım (`train_on_responses_only`).

## Sonuç

Eğitim sonunda model, kimlik sorularına Ada / Nur Şima Akgül olarak tutarlı biçimde yanıt
vermeye başladı. Kimlik veri setinde bu bilgiler yoğun ve tekrarlı geçtiği için, model
kimliğini net şekilde öğrendi. Kimlik dışındaki genel yeteneklerde temel modelin sınırları
geçerli.

## Kullanım

```python
from unsloth import FastModel

model, tokenizer = FastModel.from_pretrained(
    "nursimakgul/gemma-3-1b-ada-identity-lora", load_in_4bit=True
)

messages = [{"role": "user", "content": "Sen kimsin?"}]
inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(model.device)
out = model.generate(input_ids=inputs, max_new_tokens=256, temperature=0.7, do_sample=True)
print(tokenizer.decode(out[0][inputs.shape[1]:], skip_special_tokens=True))
```

## Not

Bu çalışma eğitim/ödev amaçlıdır. Kimlik bilgisi dışındaki cevaplarda temel modelin
doğruluk ve kapsam sınırları geçerlidir.
