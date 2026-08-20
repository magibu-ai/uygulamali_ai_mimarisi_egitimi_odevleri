# MIHENK — Model Test Yol Haritası (Türkçe)

Bu doküman, benchmark sorularını **API üzerinden 10+ farklı modelde** sırayla test edip leaderboard'a eklemek için adım adım rehberdir.

---

## 0. Strateji: neden OpenRouter?

10 ayrı modeli test etmek için normalde 6-7 ayrı hesap + 6-7 ayrı API anahtarı gerekir. Bunun yerine **[OpenRouter](https://openrouter.ai)** kullanacağız: **tek hesap, tek API anahtarı** ile OpenAI, Anthropic (Claude), Google (Gemini), xAI (Grok), Meta (Llama), DeepSeek, Qwen, Mistral… yüzlerce modele erişilir. Hepsi **OpenAI-uyumlu** tek bir arayüzle çalışır, yani tek script her modeli test eder.

> İstersen tek tek sağlayıcı anahtarı da kullanabilirsin (Bölüm 5). Ama en hızlı yol OpenRouter'dır.

---

## 1. OpenRouter hesabı ve API anahtarı (adım adım)

1. https://openrouter.ai adresine git → sağ üstten **Sign In** (Google veya GitHub ile giriş yapabilirsin).
2. Sağ üstte profil → **Credits** (Krediler) → **Add Credits**. Kredi kartıyla küçük bir tutar yükle (örn. 5-10 USD; 10 model × 40-80 soru toplam birkaç dolar tutar, ucuz modellerde sente iner).
3. Sağ üstte profil → **Keys** (veya https://openrouter.ai/keys) → **Create Key** → bir isim ver → **Create**.
4. Çıkan anahtarı kopyala (`sk-or-v1-...` ile başlar). **Yalnızca bir kez gösterilir**, güvenli bir yere kaydet.

### Anahtarı Windows'a yazma

```powershell
# Kalıcı (yeni terminal açınca geçerli olur):
setx OPENROUTER_API_KEY "sk-or-v1-xxxxx"

# Ya da sadece bu oturum için (PowerShell):
$env:OPENROUTER_API_KEY = "sk-or-v1-xxxxx"
```

---

## 2. Test aracını hazırla (tek seferlik)

```powershell
pip install openai        # OpenAI-uyumlu istemci (OpenRouter bununla çalışır)
```

`scripts/evaluate.py` artık `--backend openai` seçeneğiyle her OpenAI-uyumlu sağlayıcıyı destekliyor.

**Önce API'siz deneme (boru hattı çalışıyor mu?):**

```powershell
python scripts/evaluate.py --split public --backend dryrun
```

---

## 3. İlk modeli test et

**İlk test için ucuz ve hızlı bir model seç** (boru hattını doğrulamak, para harcamamak için). Örnek: Google Gemini Flash.

```powershell
python scripts/evaluate.py `
  --split public `
  --backend openai `
  --base-url https://openrouter.ai/api/v1 `
  --api-key-env OPENROUTER_API_KEY `
  --model "google/gemini-2.5-flash-lite" `
  --output results/gemini-flash.json
```

> ⚠️ Model kimliği (`--model`) OpenRouter'da güncel olmalı. **Kesin kimlikleri https://openrouter.ai/models sayfasından kopyala** (arama kutusuna model adını yaz, kartın üstündeki `saglayici/model-adi` metnini al). Aşağıdaki liste yön göstericidir; sürüm numaraları zamanla değişebilir.

Çıktı JSON olarak gelir: genel doğruluk + disiplin/dil/zorluk/format kırılımı + dil tutarlılık endeksi.

---

## 4. Test edilecek modeller — sıralı liste (en az 12)

Aşağıdaki sırayla ilerle. **Ucuzdan pahalıya / bazlından frontier'a** doğru dizildi; ilk üçü boru hattını ucuza doğrular, sonrakiler ciddi karşılaştırma içindir.

| Sıra | Sağlayıcı | Model (OpenRouter kimliği — sitede doğrula) | Rol                    |
| ----- | ------------ | ---------------------------------------------- | ---------------------- |
| 1     | Google       | `google/gemini-2.5-flash-lite`                    | ucuz baz / doğrulama  |
| 2     | Anthropic    | `anthropic/claude-haiku-4-5`                 | ucuz baz               |
| 3     | OpenAI       | `openai/gpt-5-mini` (veya güncel mini)      | ucuz baz               |
| 4     | DeepSeek     | `deepseek/deepseek-chat`                     | orta                   |
| 5     | Meta         | `meta-llama/llama-4-maverick`                | açık kaynak frontier |
| 6     | Alibaba      | `qwen/qwen-max` (veya güncel)               | açık kaynak frontier |
| 7     | Mistral      | `mistralai/mistral-large`                    | frontier               |
| 8     | xAI          | `x-ai/grok-4` (veya güncel)                 | frontier               |
| 9     | DeepSeek     | `deepseek/deepseek-r1` (reasoner)            | muhakeme frontier      |
| 10    | Google       | `google/gemini-3.1-pro-preview` (veya Gemini 3 Pro)  | frontier               |
| 11    | OpenAI       | `openai/gpt-5.5` (veya güncel)              | frontier               |
| 12    | Anthropic    | `anthropic/claude-opus-4-8`                  | frontier               |

> Zaten **Gemini Pro 3.1, Gemini Flash 3.6 ve GPT-5.5** için elle sonuç aldık (bkz. `leaderboard.md`). API'yle bunları da tekrar teyit edebilir, üstüne yenilerini ekleyebilirsin.

### Hepsini sırayla çalıştırmak (PowerShell döngüsü)

```powershell
$models = @(
  "google/gemini-2.5-flash-lite",
  "anthropic/claude-haiku-4-5",
  "openai/gpt-5-mini",
  "deepseek/deepseek-chat",
  "meta-llama/llama-4-maverick",
  "qwen/qwen-max",
  "mistralai/mistral-large",
  "x-ai/grok-4",
  "deepseek/deepseek-r1",
  "google/gemini-3.1-pro-preview",
  "openai/gpt-5.5",
  "anthropic/claude-opus-4-8"
)
foreach ($m in $models) {
  $safe = $m -replace "[/:]","_"
  Write-Host ">>> $m"
  python scripts/evaluate.py --split public --backend openai `
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY `
    --model $m --output "results/$safe.json"
}
```

> **İpucu — daha zorlu test:** `--split public` yerine `--split all` verirsen 800 sorunun tamamı (L1–L4) test edilir. Frontier modelleri ayırt etmek için bunu kullan. (Public sample tasarım gereği TR=L1–L2, EN=L3–L4 kapsar; tam zorluk yelpazesi için `all`.)

---

## 5. Alternatif: doğrudan sağlayıcı anahtarları

OpenRouter kullanmak istemezsen, `--base-url` ve `--api-key-env` değiştirerek doğrudan bağlanabilirsin:

| Sağlayıcı            | Anahtar nereden                            | `--base-url`                                               | Örnek`--model`        |
| ----------------------- | ------------------------------------------ | ------------------------------------------------------------ | ------------------------ |
| **OpenAI**        | https://platform.openai.com → API keys    | (boş bırak, varsayılan)                                   | `gpt-5.5`              |
| **DeepSeek**      | https://platform.deepseek.com → API Keys  | `https://api.deepseek.com`                                 | `deepseek-chat`        |
| **Mistral**       | https://console.mistral.ai → API Keys     | `https://api.mistral.ai/v1`                                | `mistral-large-latest` |
| **xAI (Grok)**    | https://console.x.ai → API Keys           | `https://api.x.ai/v1`                                      | `grok-4`               |
| **Google Gemini** | https://aistudio.google.com → Get API key | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash`     |
| **Anthropic**     | https://console.anthropic.com → API Keys  | `evaluate.py --backend anthropic` (SDK'sı gömülü)      | `claude-opus-4-8`      |

Her biri için:

```powershell
setx OPENAI_API_KEY "..."     # ilgili anahtarı ilgili değişkene yaz
python scripts/evaluate.py --split public --backend openai --base-url <URL> --api-key-env OPENAI_API_KEY --model <model>
```

Anthropic için ise `--backend anthropic --model claude-opus-4-8` yeter (ayrı SDK gömülü, `ANTHROPIC_API_KEY` okur).

---

## 5.5. Yerel modeller — Ollama (bedava, anahtarsız)

Ollama yerel modelleri **OpenAI-uyumlu** `http://localhost:11434/v1` adresinden sunar; API anahtarı ve para gerekmez. Küçük modeller genelde daha düşük skor alır — zorlayıcı ayrım için harika.

```powershell
# 1) Model indir (biri yeter, birden çok deneyebilirsin):
ollama pull llama3.1          # 8B
ollama pull qwen2.5:7b
ollama pull gemma2:9b
ollama pull phi4              # Microsoft
ollama pull deepseek-r1:7b    # muhakeme
ollama pull mistral

# 2) Test et (anahtar GEREKMEZ):
python scripts/evaluate.py --split public --backend openai `
  --base-url http://localhost:11434/v1 --model llama3.1 `
  --output results/ollama-llama3.1.json
```

`ollama list` ile indirdiğin modellerin kimliklerini görebilirsin; `--model` oraya birebir yazılır. Ollama'nın çalışır olması yeter (`ollama serve` arka planda otomatik açılır).

---

## 6. Sonuçları leaderboard'a ekleme

Her koşumun `results/<model>.json` çıktısında `overall_accuracy`, `by_language`, `by_difficulty` vardır. Bunları `leaderboard.md` tablosuna işle. İstersen bana "results klasörünü güncelledim" dersin, hepsini okuyup tabloyu yeniden üretir ve commit ederim.

---

## 7. Notlar

- **HuggingFace'de 80 satır görünmesi normaldir:** HF'e yalnızca **public sample** (dev split, ~%10) yüklenir; kalan 720 soru **private holdout** olarak kirlenmeye karşı saklanır. Sorunun tamamı GitHub'daki `data/` klasöründedir.
- **Maliyet:** ucuz modeller (Flash/Haiku/mini) 80 soruyu birkaç sent'e, frontier modeller birkaç on sent'e çözer. `--split all` (800 soru) maliyeti ~10 katına çıkarır; önce public ile dene.
- **Determinizm:** openai backend `temperature=0` gönderir. Anthropic Opus 4.x'te sampling parametreleri API tarafından kaldırıldığı için gönderilmez.


---

## 8. Doğrulanmış güncel model kimlikleri (OpenRouter, 2026-07)

`google/gemini-flash-1.5` gibi eski kimlikler kaldırıldı. **Kesin kimliği bulmak için:**
```powershell
python scripts/list_openrouter_models.py gemini    # anahtar/ücret göstermeden filtreler
python scripts/list_openrouter_models.py ":free"   # ÜCRETSİZ uçlar
```

Şu an çalışan, iyi bir karşılaştırma listesi ($ = giriş/çıkış 1M token):

| Model kimliği (`--model`) | $ | Rol |
|---|---|---|
| `openai/gpt-oss-20b:free` | 0 / 0 | **ücretsiz** baz |
| `google/gemma-4-31b-it:free` | 0 / 0 | **ücretsiz** baz |
| `nvidia/nemotron-3-super-120b-a12b:free` | 0 / 0 | **ücretsiz** güçlü |
| `google/gemini-2.5-flash-lite` | 0.10 / 0.40 | çok ucuz |
| `openai/gpt-5-nano` | 0.05 / 0.40 | çok ucuz |
| `meta-llama/llama-4-scout` | 0.10 / 0.30 | ucuz açık kaynak |
| `deepseek/deepseek-chat-v3.1` | 0.25 / 0.95 | orta |
| `deepseek/deepseek-r1` | 0.70 / 2.50 | muhakeme |
| `mistralai/mistral-large-2512` | 0.50 / 1.50 | Mistral Large 3 |
| `qwen/qwen3-max` | 0.78 / 3.90 | frontier |
| `x-ai/grok-4.5` | 2.00 / 6.00 | frontier |
| `google/gemini-3.1-pro-preview` | 2.00 / 12.00 | frontier |
| `openai/gpt-5` | 1.25 / 10.00 | frontier |
| `anthropic/claude-opus-4.7` | 5.00 / 25.00 | frontier |

> OpenRouter kimlikleri **nokta** kullanır (`claude-opus-4.7`), Anthropic'in kendi API'si **tire** (`claude-opus-4-8`). Anthropic'i doğrudan test etmek için `--backend anthropic --model claude-opus-4-8` daha günceldir.
