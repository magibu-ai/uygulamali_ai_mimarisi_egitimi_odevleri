# Pharmacy Prompt Serialization Format (PPSF) — Custom Jinja2 Chat Template

Bu proje, bir dil modelinin (LLM) kullanıcı, sistem, asistan ve araç (tool calling) mesajlarını doğru ayırt edebilmesi ve **Pharmacy Prompt Serialization Format (PPSF v1.0 / v1.1)** spesifikasyonuna uygun şekilde serileştirmesi için geliştirilmiş bir **Custom Jinja2 Chat Template** uygulamasıdır.

Hugging Face `transformers` kütüphanesinin `apply_chat_template()` fonksiyonu ile **%100 tam uyumlu** olarak çalışacak şekilde tasarlanmıştır.

---

## 🎯 Ödev Amacı ve Özellikler

- **Hugging Face Standartlarına Tam Uyumluluk:** Standart `messages` dizisini (`role`, `content`, `tool_calls`) ve `tools` listesini kabul eder.
- **Alan Spesifik Rol Tanımları (Pharmacy Protocol):**
  - `system` $\rightarrow$ `@SYSTEM`
  - `user` $\rightarrow$ `@PATIENT`
  - `assistant` $\rightarrow$ `@PHARMACIST`
  - `tool` $\rightarrow$ `@TOOL_RESPONSE`
- **Tool Calling (Araç Çağrısı) Desteği:**
  - Mevcut araç tanımlarını `@TOOLS` bloğu altında ilan eder.
  - Asistanın araç çağırma isteklerini `@TOOL_CALL` formatında formatlar.
  - Araç yanıtlarını `@TOOL_RESPONSE` olarak bağlama ekler.
- **Geleceğe Uyumlu Metadata Desteği (PPSF v1.1):**
  - Mesaj nesnesinde yer alan `metadata.reference` verilerini `@REFERENCE` bloğuna dönüştürür.
  - Mesaj nesnesinde yer alan `metadata.thought` verilerini (Chain of Thought) `@THOUGHT` bloğuna dönüştürür.

---

## 📁 Proje Dosya Yapısı

```
Chat_Template/
├── chat_template.jinja    # PPSF v1.0 / v1.1 Jinja2 şablon dosyası
├── main.py                # Jinja2 ve Hugging Face AutoTokenizer test scripti
└── README.md              # Proje dokümantasyonu
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Gereksinimler
Projeyi çalıştırmak için Python 3.8+ ve aşağıdaki kütüphanelerin kurulu olması yeterlidir:

```bash
pip install jinja2 transformers
```

### 2. Test Scriptini Çalıştırma
Tüm test senaryolarını (Standart sohbet, Tool Calling ve Metadata kullanımı) çalıştırmak için:

```bash
python main.py
```

---

## 💻 Kullanım Örnekleri

### Hugging Face `transformers` ile Kullanım

```python
from transformers import AutoTokenizer

# Herhangi bir tokenizer yüklendikten sonra özel şablon atanabilir:
tokenizer = AutoTokenizer.from_pretrained("gpt2")

with open("chat_template.jinja", "r", encoding="utf-8") as f:
    tokenizer.chat_template = f.read()

messages = [
    {"role": "system", "content": "Sen uzman bir eczacı yapay zekâsısın."},
    {"role": "user", "content": "Boğazım ağrıyor."}
]

prompt = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=False
)

print(prompt)
```

**Üretilen Çıktı:**
```text
@FORMAT PPSF/1.0

@SYSTEM
Sen uzman bir eczacı yapay zekâsısın.

@PATIENT
Boğazım ağrıyor.

@PHARMACIST
```

---

### Tool Calling Senaryosu Örneği

**Girdi:**
```python
messages = [
    {"role": "system", "content": "Sen uzman bir eczacı yapay zekâsısın."},
    {"role": "user", "content": "Parol ne işe yarar?"},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "function": {
                    "name": "search_drug",
                    "arguments": {"drug": "Parol"}
                }
            }
        ]
    },
    {
        "role": "tool",
        "content": '{"drug": "Parol", "active_ingredient": "Parasetamol", "usage": "Ağrı kesici ve ateş düşürücü"}'
    }
]
```

**Üretilen Çıktı:**
```text
@FORMAT PPSF/1.0

@SYSTEM
Sen uzman bir eczacı yapay zekâsısın.

@PATIENT
Parol ne işe yarar?

@TOOL_CALL
{
  "name": "search_drug",
  "arguments": {"drug": "Parol"}
}

@TOOL_RESPONSE
{"drug": "Parol", "active_ingredient": "Parasetamol", "usage": "Ağrı kesici ve ateş düşürücü"}

@PHARMACIST
```

---

## 🏛️ Mimari Tasarım Notları (PPSF v1.1 Desteği)

Hugging Face standart `messages` yapısında `thought` veya `reference` rolleri bulunmamaktadır. Bu nedenle PPSF formatında CoT (Düşünce Adımları) ve RAG (Referans Dokümanlar) desteği `metadata` nesnesi üzerinden sağlanmıştır:

```python
{
    "role": "user",
    "content": "Grip için hangi ilacı kullanmalıyım?",
    "metadata": {
        "reference": "[Kılavuz Doc #42]: Parasetamol 500mg tercih edilir."
    }
}
```

Jinja2 şablonu bu `metadata` içeriğini otomatik olarak algılar ve `@REFERENCE` ile `@THOUGHT` bloklarını sırasıyla bağlama yerleştirir. Bu yaklaşım, ekosistem uyumluluğunu bozmadan formatı genişletilebilir kılar.
