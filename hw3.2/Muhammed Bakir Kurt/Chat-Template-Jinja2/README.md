# 🎭 Custom Jinja2 Chat Template - Sistem Mimarisi

Bu depo, **Magibu Uygulamalı Yapay Zekâ Mimarisi Eğitimi** kapsamında, büyük dil modellerinin (LLM) kullanıcı, sistem ve asistan mesajlarını kusursuz bir şekilde ayırt edebilmesi için sıfırdan kurgulanmış özel bir **Jinja2 Chat Template** barındırmaktadır.

---

## 🏗️ Kaputun Altındaki Mantık

Büyük dil modelleri özünde düz metin işleyen tahmin mekanizmalarıdır. Bu Jinja2 şablonu, sohbet geçmişini düz bir metin yığını olmaktan çıkarıp, modelin anlayabileceği bir "tiyatro senaryosuna" dönüştürür. Rol ayrımı şu etiketlerle sağlanır:

* **System (Kamera Arkası Yönetmen):** Modelin karakterini, görevlerini ve güvenlik sınırlarını (Guardrails) belirler. `<|turn>system` etiketiyle sarmalanır.
* **User (Kullanıcı):** İnsandan gelen yönlendirme ve soruları temsil eder. `<|turn>user` etiketiyle sarmalanır.
* **Assistant / Model (Aktör):** Yapay zekânın sistem kurallarına bağlı kalarak ürettiği yanıtlardır. Geçmişi hatırlaması için `<|turn>model` etiketiyle sarmalanır.

---

## 📄 Şablon Yapısı (`chat_template.jinja`)

Şablonumuz temiz, gereksiz karmaşadan uzak ve roller arası kesin sınırlar çizecek şekilde optimize edilmiştir:

```jinja2
{{ bos_token }}
{%- for message in messages -%}
    {%- if message['role'] == 'system' -%}
        {{ '<|turn>system\n' + message['content'] | trim + '\n<turn|>\n' }}
    {%- elif message['role'] == 'user' -%}
        {{ '<|turn>user\n' + message['content'] | trim + '\n<turn|>\n' }}
    {%- elif message['role'] == 'assistant' -%}
        {{ '<|turn>model\n' + message['content'] | trim + '\n<turn|>\n' }}
    {%- endif -%}
{%- endfor -%}
{%- if add_generation_prompt -%}
    {{ '<|turn>model\n' }}
{%- endif -%}
