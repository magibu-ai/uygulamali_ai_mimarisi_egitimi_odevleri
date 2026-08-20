# Türkçe Custom Chat Template

Bu proje, `system`, `user` ve `assistant` rollerini Türkçe Byte-Level BPE
tokenizer ile kullanılabilecek tek bir model girdisine dönüştüren Jinja2 chat
template örneğidir.

Kullanılan tokenizer:
[`samliumay/turkish_bpe_based_on_cyber_security_texts`](https://huggingface.co/samliumay/turkish_bpe_based_on_cyber_security_texts)

## Sohbet formatı

Şablon aşağıdaki kontrol tokenlerini kullanır:

```text
<|system|>
<|user|>
<|assistant|>
```

Tokenizer'da önceden bulunan `<bos>` konuşmanın başında, `<eos>` ise her
mesajın sonunda kullanılır. Örnek bir model girdisi şöyledir:

```text
<bos><|system|>
Her zaman Türkçe cevap ver.
<eos>
<|user|>
Zero Trust nedir?
<eos>
<|assistant|>
```

`<|assistant|>` etiketinin sonda açık bırakılması
`add_generation_prompt=True` davranışıdır ve modele sıradaki cevabı asistanın
üretmesi gerektiğini bildirir.

## Şablonun özellikleri

- Yalnızca `system`, `user` ve `assistant` rollerini kabul eder.
- System mesajına yalnızca konuşmanın ilk sırasında izin verir.
- User ve assistant mesaj sırasını doğrular.
- Yalnızca metin içeriklerini kabul eder.
- Mesajların başındaki ve sonundaki gereksiz boşlukları temizler.
- `add_generation_prompt` ile yeni assistant turu başlatabilir.
- Tokenizer'ın mevcut `bos_token` ve `eos_token` değerlerini kullanır.

## Proje yapısı

```text
.
├── chat_template.jinja
├── scripts/
│   └── prepare_tokenizer.py
├── tests/
│   └── test_chat_template.py
└── requirements.txt
```

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Tokenizer'ı hazırlama

Aşağıdaki komut tokenizer'ı Hugging Face'den indirir, rol etiketlerini özel
token olarak ekler, `chat_template.jinja` dosyasını tokenizer'a bağlar ve
sonucu `output/chat_tokenizer` dizinine kaydeder:

```bash
python3 scripts/prepare_tokenizer.py
```

Farklı bir yerel tokenizer veya çıktı dizini de seçilebilir:

```bash
python3 scripts/prepare_tokenizer.py \
  --tokenizer /yerel/tokenizer/dizini \
  --output-dir output/chat_tokenizer
```

Script her rol etiketinin tek token ID'ye dönüştüğünü doğrular. Ardından örnek
bir sohbeti hem metin hem token ID dizisi olarak üretir.

Hazırlanan tokenizer daha sonra şöyle yüklenebilir:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("output/chat_tokenizer")

messages = [
    {"role": "system", "content": "Her zaman Türkçe cevap ver."},
    {"role": "user", "content": "Zero Trust nedir?"},
]

prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

print(prompt)
```

Doğrudan modele verilecek token ID'leri için `tokenize=True` kullanılabilir:

```python
input_ids = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=False,
)
```

## Testler

Testler ek bir test kütüphanesi gerektirmeyen Python `unittest` altyapısını
kullanır:

```bash
python3 -m unittest discover -s tests -v
```

Test paketi doğru render çıktısını, generation prompt davranışını, boşlukların
temizlenmesini ve geçersiz rol/sıra/içerik durumlarının reddedilmesini kontrol
eder.

## Model uyumluluğu

Bu depo bir tokenizer ve chat template içerir; tek başına metin üreten bir dil
modeli değildir. Hazır bir Gemma, Llama veya Qwen modelinin tokenizer'ı bununla
doğrudan değiştirilmemelidir. Modelin embedding tablosu kendi tokenizer
sözlüğüne göre öğrenilmiştir.

Bu tokenizer ile sıfırdan model eğitilecekse rol tokenleri eğitim verilerinde
kullanılmalıdır. Mevcut bir modele yeni tokenler eklenirse embedding tablosu
yeniden boyutlandırılmalı ve model bu sohbet formatıyla fine-tune edilmelidir:

```python
model.resize_token_embeddings(len(tokenizer))
```

Tokenizer'ın 1.000 tokenlık küçük ve siber güvenlik odaklı bir sözlüğü vardır.
Bu nedenle eğitim ve alan odaklı prototipler için uygundur; genel Türkçe
metinlerde daha uzun token dizileri üretebilir.

## Hugging Face'e yükleme

Sonuçlar kontrol edildikten sonra kullanıcı tarafından şu şekilde ayrı bir
depoya yüklenebilir:

```python
tokenizer.push_to_hub("KULLANICI_ADI/TOKENIZER_DEPO_ADI")
```

Bu işlem tokenizer dosyalarıyla birlikte `chat_template.jinja` dosyasını da
kaydeder. Yükleme işlemi kimlik doğrulaması ve uzak depoda değişiklik yaptığı
için otomatik olarak çalıştırılmaz.
