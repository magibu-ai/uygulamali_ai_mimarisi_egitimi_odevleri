# Custom Chat Template (Jinja2)

`chat_template.jinja`, bir dil modelinin `system` / `user` / `assistant` / `tool` rollerini
ve tool-calling parametrelerini doğru sarmalayan özel bir ChatML-benzeri şablondur.

## Format

- Her mesaj `<|im_start|>{role}\n ... <|im_end|>\n` bloğuna sarılır.
- `system` mesajı varsa (veya `tools` parametresi geçilmişse) en başta tek bir `system`
  bloğu oluşur; `tools` listesi JSON olarak `<tools>...</tools>` içinde gömülür.
- Modelin fonksiyon çağırması gerektiğinde beklenen çıktı formatı:
  ```
  <tool_call>
  {"name": "get_weather", "arguments": {"city": "İstanbul"}}
  </tool_call>
  ```
- Fonksiyon sonucu, ardışık `tool` mesajları tek bir `<|im_start|>tool ... <|im_end|>` bloğunda
  birleştirilir, her sonuç kendi `<tool_response>...</tool_response>` etiketinde durur.
- `add_generation_prompt=True` verilirse şablon `<|im_start|>assistant\n` ile biter, model
  buradan devam üretir.

## Test etme

```bash
pip install jinja2
python test_render.py
```

`test_render.py`, bir `get_weather` tool tanımı + tool-call + tool-response içeren örnek bir
konuşmayı şablondan geçirip render edilmiş metni terminale basar (kanıt için).

## Hugging Face üzerinde kullanım

Bir modelin repo'suna `chat_template.jinja` dosyasını eklediğinizde (veya
`tokenizer.chat_template` alanına içeriğini atadığınızda), `tokenizer.apply_chat_template(...)`
bu şablonu kullanarak mesaj listesini modele uygun metne çevirir.

## Dosyalar

- `chat_template.jinja` — şablonun kendisi
- `test_render.py` — örnek konuşma ile render testi
- `README.md` — bu dosya
