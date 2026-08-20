# Custom Chat Template (Jinja2) — Gemma 4 uyumlu, tool-calling odaklı

Bir dil modelinin `system`, `user`, `assistant` ve `tool` mesajlarını doğru ayırt edebilmesi
ve tool-calling parametrelerini beklenen biçimde üretebilmesi için yazılmış özel bir Jinja2
sohbet şablonu.

Şablonu gerçek bir modelde (Gemma 4, Ollama üzerinden) çalıştırılarak doğruladım.

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `chat_template.jinja` | Şablonun kendisi |
| `test_render.py` | Şablonu 4 farklı sohbet üzerinde render eder (model gerekmez) |
| `test_ollama.py` | Şablonun ürettiği metni gerçek modele gönderip davranışı ölçer |

Karşılaştırma için kullanılan resmi Gemma 4 şablonu repoya dahil edilmemiştir; kendi lisansı
altında [unsloth/gemma-4-E4B-it](https://huggingface.co/unsloth/gemma-4-E4B-it/blob/main/chat_template.jinja)
adresinden alınabilir.

## Desteklenen girdiler

```python
messages               # OpenAI biçiminde mesaj listesi (system / user / assistant / tool)
tools                  # OpenAI biçiminde araç şeması listesi (opsiyonel)
add_generation_prompt  # True ise sonda boş model turu açılır
bos_token              # opsiyonel
varsayilan_talimat     # system mesajı yokken kullanılacak talimat
```

## Ürettiği biçim

```
<bos><|turn>system
Sen bir biyoloji çalışma koçusun. Yanıtlarını YALNIZCA araçlardan dönen veriye dayandır.
<|tool>declaration:terim_ara{description:<|"|>...<|"|>,parameters:{properties:{terim:{
description:<|"|>Aranacak biyoloji terimi<|"|>,type:<|"|>STRING<|"|>}},
required:[<|"|>terim<|"|>],type:<|"|>OBJECT<|"|>}}<tool|><turn|>
<|turn>user
Mayoz nedir?<turn|>
<|turn>model
<|tool_call>call:terim_ara{terim:<|"|>mayoz<|"|>}<tool_call|>
<|tool_response>response:terim_ara{bulundu:true,kitap_sayfasi:87,tanim:<|"|>...<|"|>}<tool_response|>
Mayoz, ... (Kaynak: ders kitabı s.87)<turn|>
<|turn>model
```

## Tasarım kararları

**Token seti neden özgün değil, Gemma 4'ün token'ları?**
Özel token'lar tokenizer'da tek parçadır ve model onları eğitim boyunca sınır işareti olarak
öğrenir. Uydurma bir token (`<|msg|>` gibi) tokenizer'da tanımsız olduğu için `<`, `|`, `msg`,
`|`, `>` şeklinde parçalanır ve model bunu sıradan metin sanar. Sonuç hata değil, **sessiz kalite
kaybıdır**: model rolleri karıştırır, tool çağrısı üretmez. Bu yüzden alfabe modelden alındı,
şablonun yapısı ve mantığı bu projede kuruldu.

**Rol sırası kontrolü (alternation) neden yok?**
Yaygın şablonlarda `user/assistant/user/assistant` sırası zorlanır ve bozulursa
`raise_exception` fırlatılır. Tool calling bu kuralı kırar, çünkü gerçek akış
`user → assistant(tool çağırır) → tool(sonuç) → assistant(cevaplar)` şeklindedir. Bu şablonda
böyle bir kontrol bilinçli olarak yoktur.

**Gemma'ya özgü iki davranış korundu:**
1. `assistant` rolü metinde `model` adıyla yazılır.
2. `tool` sonuçları kendi turunu açmaz; açık model turunun içine girer. Böylece
   `model → tool → model` zinciri tek bir tur içinde kalır.

**Resmi şablona göre çıkarılanlar.** Resmi Gemma 4 şablonu 385 satırdır; düşünme kanalları
(`<|think|>`, `<|channel>`), multimodal içerik (görüntü/ses/video), legacy Google + OpenAI çift
tool formatı ve derin şema özyinelemesi taşır. Bu şablon yalnızca metin + tool-calling akışına
odaklanır. Kullanılmayan özelliği taşımamak hata yüzeyini küçültür.

**`<|"|>` escape token'ı.** Gemma argümanları JSON yerine kendi kompakt biçiminde yazar ve
string sınırlarını `<|"|>` özel token'ıyla işaretler. Bu token kullanıcı metninden üretilemediği
için kaçış (escape) sorunu tokenizer seviyesinde çözülür — JSON'daki `"` karakterinin aksine
kırılgan değildir.

## Doğrulama

### Render testi (model gerekmez)

```bash
pip install jinja2
python test_render.py
```

Dört senaryo: tam tool-calling zinciri, system mesajı olmadan yalnızca araçlar, düz sohbet,
argümanların JSON string olarak geldiği durum. Testler `StrictUndefined` ile çalışır; şablondaki
opsiyonel alan erişimleri bu sayede sessizce boş geçmek yerine hata verir.

### Gerçek model testi

```bash
ollama pull gemma4
python test_ollama.py
```

Şablonun ürettiği metin Ollama'ya `raw=True` ile gönderilir. Bu, Ollama'nın kendi şablonunu devre
dışı bırakır; modele giden her karakteri bu şablon belirler.

| Test | Beklenen | Sonuç |
|---|---|---|
| A | Modelin aracı çağırması | `<\|tool_call>call:terim_ara{terim:<\|"\|>Mayoz<\|"\|>}<tool_call\|>` |
| B | Araç sonucundan cevap üretmesi | Tanımı verdi, "Kaynak: Sayfa 87" atfıyla |
| C | Araç boş dönünce uydurmaması | "…kullandığım biyoloji sözlüğünde bulunmamaktadır." |

C testi şablonun tool-response bloğunun işe yaradığını gösterir: model konu hakkında bilgi
sahibi olmasına rağmen, araçtan `bulundu:false` gelince tanım uydurmayı reddetti.

## Kullanım

```python
from jinja2 import Environment
from pathlib import Path

sablon = Environment().from_string(Path("chat_template.jinja").read_text())
prompt = sablon.render(
    messages=[{"role": "user", "content": "Mayoz nedir?"}],
    tools=TOOLS,
    add_generation_prompt=True,
    bos_token="<bos>",
)
```

Elde edilen `prompt` doğrudan Ollama'ya `raw=True` ile veya bir tokenizer'a verilebilir.

## Not

Bu şablon, tool-calling destekli bir biyoloji çalışma koçu projesinde kullanılmak üzere
yazılmıştır; araç örnekleri (`terim_ara`, `quiz_getir`) o projeden gelir. Şablonun kendisi
senaryodan bağımsızdır ve herhangi bir OpenAI biçimli araç şemasıyla çalışır.
