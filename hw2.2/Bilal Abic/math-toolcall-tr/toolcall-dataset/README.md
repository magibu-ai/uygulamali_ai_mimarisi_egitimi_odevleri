# Matematik Tool-Call Veri Seti Ureteci

Alan: **Tool Call** — modelin verilen fonksiyonu dogru sekilde cagirmasi ve sonucu
kullaniciya uygun bicimde sunmasi. Icerik tamamen **matematik** uzerine.

Uretim OpenAI ile yapilir (Gemini destegi kodda hazir, kapali). Her kaydin hangi model
tarafindan uretildigi ve hangi konuya ait oldugu veri setinde tutulur.

Hangi saglayicinin kullanilacagi `.env` icindeki `DEFAULT_PROVIDER` ile belirlenir:
`openai` (varsayilan) | `gemini` | `both`. Tek seferlik degistirmek icin komuta
`--provider both` eklemek yeterli. Cikti formatlari bundan bagimsizdir — saglayici
`openai` olsa bile hem `train_openai.jsonl` hem `train_gemini.jsonl` uretilir.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env      # sonra anahtarlari doldur
```

## Akis

```bash
python cli.py topics             # taksonomiyi gor
python cli.py run --n 200        # uretim: soru -> hemen cevap, 5'lik turlarla
python cli.py export             # jsonl formatlari
python cli.py stats              # dagilim raporu
```

`run` tek akista calisir: her turda 5 soru uretir, **hemen ardindan** o 5 soruyu
cevaplar (thinking + arac cagrilari + cevap), sonucu diske yazar ve bir sonraki tura
gecer. Yani 5 tam kayitta bir dosyalar guncellenir — surec yarida kesilse bile
o ana kadar uretilen her sey duruyor olur.

Tur boyutunu `.env` icindeki `QUESTION_BATCH_SIZE` belirler (varsayilan 5).

Birikimlidir: tekrar calistirdiginda uzerine ekler, ayni soruyu ikinci kez yazmaz.

Faydali bayraklar:

```bash
python cli.py run --n 200 --fresh            # once hic islenmemis konular (kapsama icin)
python cli.py run --n 20 --domain analiz     # tek alt alan
python cli.py run --n 50 --provider both     # gecici olarak Gemini'yi de kat
python cli.py export --inline-thinking       # <think>...</think> cevaba gomulur
```

Iki asamayi ayirmak istersen (once tum sorular, sonra cevaplar) eski komutlar duruyor:

```bash
python cli.py questions --n 200
python cli.py answers --limit 20
```

## Ciktilar (`data/`)

| Dosya | Ne ise yarar |
|---|---|
| `dataset_chat.json` | **Sohbet formati** — asagidaki mesaj yapisi, egitim icin hazir |
| `dataset.json` | Ayni kayitlar + tum metadata (konu, senaryo, hangi model uretti) |
| `questions.json` | Ham soru havuzu (arac semalari + etiketler) |
| `train_openai.jsonl` | OpenAI `messages` + `tools` formati |
| `train_gemini.jsonl` | Gemini `contents` + `functionDeclarations` formati |

`dataset_chat.json` ve `dataset.json` ayni sirada, ayni kayitlari tutar; biri sade
egitim formati, digeri o kaydin nereden geldigini anlatan tam kayit.

### `dataset_chat.json` — sohbet formati

Konusma listesi; her konusma iki mesajdan olusur. Arac cagrilari ve donen sonuclar
asistan mesajinin `tool_calls` alaninda birlikte durur, arac cagrilmadiysa `null` olur.

```json
[
  [
    {
      "content": "(3x^2+1)*sin(x) turevi nedir?",
      "images": null,
      "role": "user",
      "thinking": null,
      "tool_calls": null
    },
    {
      "content": "f'(x) = 6x·sin(x) + (3x²+1)·cos(x)",
      "images": null,
      "role": "assistant",
      "thinking": "Carpim kurali gerekiyor...",
      "tool_calls": [
        {
          "name": "compute_derivative",
          "arguments": { "expression": "(3*x^2+1)*sin(x)" },
          "result": { "derivative": "6*x*sin(x)+(3*x^2+1)*cos(x)" }
        }
      ]
    }
  ]
]
```

### `dataset.json` kayit ornegi

```json
{
  "id": "q_3f9a2c1b04",
  "domain": "analiz",
  "topic": "turev alma kurallari (carpim, bolum, zincir)",
  "scenario": "tek_cagri",
  "difficulty": "orta",
  "tools": [{ "type": "function", "function": { "name": "compute_derivative", "...": "..." } }],
  "question": "f(x) = (3x^2+1)*sin(x) fonksiyonunun turevini alir misin?",
  "thinking": "Kullanici bir carpim halindeki fonksiyonun turevini istiyor...",
  "tool_calls": [{ "name": "compute_derivative", "arguments": { "expression": "(3*x^2+1)*sin(x)", "variable": "x" } }],
  "tool_results": [{ "name": "compute_derivative", "result": { "derivative": "6*x*sin(x) + (3*x^2+1)*cos(x)" } }],
  "answer": "Turev su sekilde: f'(x) = 6x·sin(x) + (3x²+1)·cos(x). ...",
  "question_provider": "gemini",
  "question_model": "gemini-2.5-pro",
  "answer_provider": "openai",
  "answer_model": "gpt-5"
}
```

`question_*` ve `answer_*` alanlari "hangisi hangi yapay zeka ile uretildi" sorusunu
karsilar; `domain` / `topic` / `scenario` / `difficulty` ise konu bilgisini tasir.
Ayni alanlar jsonl ciktilarinda `metadata` altinda tekrarlanir.

> OpenAI'a fine-tune icin yuklerken `metadata` anahtarini atmak gerekebilir —
> ayni bilgi `dataset.json` icinde `id` ile eslesir.

## Dosyalar

| Dosya | Sorumluluk |
|---|---|
| `prompts.py` | **Tek master prompt** + iki asama eki. Kalite ayari burada yapilir. |
| `topics.py` | Matematik alt alanlari, konular, senaryolar. Genisletmesi kolay. |
| `providers.py` | OpenAI + Gemini icin tek istemci (Gemini OpenAI-uyumlu endpoint ile). |
| `exporters.py` | OpenAI / Gemini egitim formatlarina cevirim. |
| `config.py` | `.env` okuma. |
| `cli.py` | Komutlar. |

Senaryolar (`topics.py`): `tek_cagri`, `zincirli_cagri`, `paralel_cagri`,
`eksik_parametre`, `arac_gereksiz`, `yanlis_arac_tuzagi`, `hata_yonetimi`,
`cok_adimli_gorev` — yani veri seti sadece "dogru cagri" degil, **cagri yapmamayi**
ve hatayi aciklamayi da ogretir.

## Model secimi

Varsayilan: **`gpt-5.4-mini`** + `gemini-2.5-pro`.

Matematiksel dogruluk bu veri setinin can damari oldugu icin reasoning yapabilen bir
model gerekir; `gpt-4.1-mini` / `gpt-4o-mini` hesabi sessizce yanlis yapip emin gorunur.
Butce sikisirsa sirayla `gpt-5-mini` -> `o4-mini` denenebilir. `nano` ve `codex`
modelleri bu is icin onerilmez.

`gpt-5*` ve `o*` ailesinde istemci ayrica `REASONING_EFFORT` gonderir (varsayilan
`medium`). Uretilen ornekler yuzeysel kalirsa `high` yap; hiz istiyorsan `low`.

## Notlar

- `MAX_TOKENS` / `TEMPERATURE` / `REASONING_EFFORT` gibi parametreleri desteklemeyen
  modellerde istemci o parametreyi dusurup otomatik tekrar dener.
- Rate limit yersen `.env` icinde `WORKERS` degerini dusur.
- Ayni soru metni iki kez uretilirse ikincisi otomatik elenir.
