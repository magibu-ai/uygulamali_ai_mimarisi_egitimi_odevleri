# Özel ChatML Chat Template

Bir dil modelinin `system`, `user`, `assistant` ve `tool` mesajlarını doğru
ayırt edebilmesi ve çıktıyı beklenen formatta üretebilmesi için hazırlanmış
özel bir **Jinja2 chat template**'i.

## Ne yapar

`messages` listesini (rol + içerik) modelin beklediği **tek bir düz metne**
çevirir. Roller **ChatML** biçiminde sarmalanır:

```
<|im_start|>system
...<|im_end|>
<|im_start|>user
...<|im_end|>
<|im_start|>assistant
...<|im_end|>
```

## Özellikler

- **Roller:** `system`, `user`, `assistant`, `tool`
- **Tool-calling:** assistant mesajındaki `tool_calls` alanı
  `<tool_call>...</tool_call>` bloğu olarak; aracın döndürdüğü sonuç ise ayrı
  bir `tool` turn'ü olarak sarmalanır.
- **`add_generation_prompt`:** `True` iken sona `<|im_start|>assistant\n`
  eklenir; böylece üretim için sıra modele açık bırakılır.
- ChatML özel token'ları (`<|im_start|>`, `<|im_end|>`) tek token olan bir
  tokenizer ile uyumlu tasarlandı: [`namruni/meb-ogretmen-tokenizer`](https://huggingface.co/namruni/meb-ogretmen-tokenizer).

## Kullanım

```python
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("namruni/meb-ogretmen-tokenizer")
tok.chat_template = open("chat_template.jinja").read()

messages = [
    {"role": "system", "content": "Sen yardımcı bir asistansın."},
    {"role": "user", "content": "Merhaba"},
]
metin = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(metin)
```

## Tool-calling örneği

```python
messages = [
    {"role": "user", "content": "İstanbul'da hava nasıl?"},
    {"role": "assistant", "tool_calls": [
        {"type": "function",
         "function": {"name": "hava_durumu", "arguments": {"sehir": "İstanbul"}}}]},
    {"role": "tool", "content": '{"sicaklik": 22, "durum": "güneşli"}'},
    {"role": "assistant", "content": "İstanbul'da hava 22°C ve güneşli."},
]
```

Bu sohbet şu çıktıya dönüşür:

```
<|im_start|>user
İstanbul'da hava nasıl?<|im_end|>
<|im_start|>assistant
<tool_call>
{"name": "hava_durumu", "arguments": {"sehir": "İstanbul"}}
</tool_call><|im_end|>
<|im_start|>tool
{"sicaklik": 22, "durum": "güneşli"}<|im_end|>
<|im_start|>assistant
İstanbul'da hava 22°C ve güneşli.<|im_end|>
```

## Not

- Tool etiketleri (`<tool_call>`) düz metindir; ilgili tokenizer'da özel token
  olarak tanımlı değildir. Eğitim/çıkarımda temiz tek-token sınır isteniyorsa
  bu etiketler tokenizer'a özel token olarak eklenebilir.
