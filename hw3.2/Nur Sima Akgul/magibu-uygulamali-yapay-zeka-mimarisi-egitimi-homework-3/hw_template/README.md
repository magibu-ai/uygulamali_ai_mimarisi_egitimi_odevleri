# Türkçe BPE Tokenizer — Chat Template (Jinja2)

Bu depo, sıfırdan eğittiğim Türkçe BPE tokenizer için hazırlanmış bir **chat template**
(`chat_template.jinja`) içerir. Chat template, bir sohbetteki mesajları (system, user,
assistant ve tool rolleri) modelin eğitim sırasında gördüğü tek bir metin dizisine çeviren
bir Jinja2 şablonudur.

## Amaç

Bir dil modelinin; kullanıcı, sistem ve asistan mesajlarını doğru ayırt edebilmesi ve
çıktıyı beklenen formatta üretebilmesi için mesajların tutarlı bir yapıda sarmalanması
gerekir. Bu şablon, o sarmalama kurallarını tanımlar ve ayrıca **tool calling
(fonksiyon çağırma)** parametrelerini de doğru biçimde işler.

## Desteklenen roller

| Rol | Nasıl sarmalanır |
|-----|------------------|
| `system` | `<\|im_start\|>system ... <\|im_end\|>` — sohbetin en başında |
| `user` | `<\|im_start\|>user ... <\|im_end\|>` |
| `assistant` | `<\|im_start\|>assistant ... <\|im_end\|>` (metin ve/veya tool çağrısı) |
| `tool` | `<\|im_start\|>tool <tool_response> ... </tool_response> <\|im_end\|>` |

Şablon, belirli bir model ailesine ait özel token'lara bağımlı değildir; rol sınırları
evrensel ve okunabilir `<|im_start|>` / `<|im_end|>` etiketleriyle belirtilir. Bu, şablonu
bağımsız bir tokenizer için uygun kılar.

## Tool calling desteği

- Kullanılabilecek araçlar (tools) verildiğinde, JSON şemaları sistem bağlamına eklenir;
  böylece model hangi fonksiyonları çağırabileceğini bilir.
- Asistanın yaptığı fonksiyon çağrıları `<tool_call>{"name": ..., "arguments": ...}</tool_call>`
  biçiminde sarmalanır.
- Araçtan dönen sonuçlar `<tool_response> ... </tool_response>` biçiminde modele geri verilir.

## Örnek çıktı

Aşağıdaki mesaj listesi:

```python
messages = [
    {"role": "system", "content": "Sen yardımcı bir asistansın."},
    {"role": "user", "content": "Hava nasıl?"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "hava", "arguments": {"sehir": "Sivas"}}}
    ]},
    {"role": "tool", "content": '{"derece": 12}'},
    {"role": "assistant", "content": "Sivas'ta hava 12 derece."},
]
```

şu metne dönüştürülür:

```
<|im_start|>system
Sen yardımcı bir asistansın.<|im_end|>
<|im_start|>user
Hava nasıl?<|im_end|>
<|im_start|>assistant
<tool_call>
{"name": "hava", "arguments": {"sehir": "Sivas"}}
</tool_call><|im_end|>
<|im_start|>tool
<tool_response>
{"derece": 12}
</tool_response><|im_end|>
<|im_start|>assistant
Sivas'ta hava 12 derece.<|im_end|>
```

## Kullanım

Şablonu tokenizer'a bağlayıp `apply_chat_template` ile kullanabilirsiniz:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("nursimakgul/turkce-bpe-tokenizer")

# chat_template.jinja dosyasının içeriğini tokenizer'a ata
with open("chat_template.jinja", encoding="utf-8") as f:
    tokenizer.chat_template = f.read()

messages = [
    {"role": "system", "content": "Sen yardımcı bir asistansın."},
    {"role": "user", "content": "Merhaba!"},
]
metin = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
print(metin)
```

`add_generation_prompt=True` verildiğinde, çıktının sonuna `<|im_start|>assistant\n`
eklenir; böylece model yanıt üretmeye hazır hale gelir.

## Tasarım notları

- **Whitespace kontrolü:** Şablon boyunca `{%- ... -%}` kullanılarak istenmeyen boşluk ve
  satır sonları engellenmiştir; çıktı temiz ve tutarlıdır.
- **Sistem mesajı isteğe bağlıdır:** Verilmezse şablon doğrudan kullanıcı mesajıyla başlar.
- **JSON şemaları `tojson` filtresiyle** güvenli biçimde serileştirilir.
