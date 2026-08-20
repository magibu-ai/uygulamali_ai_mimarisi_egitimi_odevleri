# Türkçe İlçe/Köy Adı Üretici

**BPE tokenizer (sıfırdan) + minyatür Transformer**

> Ders ödevi. İki teslim:
> 1. **Tokenizer** — Byte-Pair Encoding algoritmasının sıfırdan implementasyonu
> 2. **Model** — bu tokenizer ile eğitilmiş minyatür bir dil modeli
>
> Model mimarisi [malibayram/single_letter_transformers](https://github.com/malibayram/single_letter_transformers)
> reposundan alınmıştır. Hangi dosyanın kime ait olduğu: [NOTICE.md](NOTICE.md)

**Ad Soyad:** _(doldur)_
**Öğrenci No:** _(doldur)_
**Tarih:** _(doldur)_

---

## Özet

22.682 Türkçe yerleşim adı üzerinde sıfırdan bir BPE tokenizer eğittim ve bunu
TinyQwen mimarisine bağlayarak gerçekte var olmayan ama inandırıcı ilçe/köy adları
üreten bir model eğittim.

BPE, hiçbir dilbilgisi kuralı verilmeden yalnızca frekans sayarak Türkçe yer adı
morfolojisini keşfetti: `yukarı`, `aşağı`, `pınar`, `büyük`, `küçük`, `demir`,
`kızıl`, `çayır`, `köy` gibi parçalar tek token hâline geldi.

**Örnek üretimler:** `yukarıhamzayolu` · `küçükkaravaca` · `büyükdocahan` ·
`karlıpınar` · `sıraoba` · `tekçukur`

---

## Hızlı başlangıç

```bash
pip install -r requirements.txt

cd data
python hazirla.py              # veriyi indirir  -> isimler.txt      (23.769)
python temizle_isimler.py      # normalize eder  -> temiz_isimler.txt (22.682)

cd ../qwen3
python egit_tokenizer.py       # Ödev 1 -> tokenizer.json
python train.py                # Ödev 2 -> tiny_qwen.pt   (~2 dk, CPU)
python generate.py 30 0.8      # 30 isim üret
python karsilastir.py          # Char vs BPE (~5 dk, iki modeli de eğitir)
```

---

# Ödev 1 — BPE Tokenizer

**Kod:** [`qwen3/bpe_tokenizer.py`](qwen3/bpe_tokenizer.py)
**Artefakt:** `qwen3/tokenizer.json` (vocab + merge kuralları)
**Çalıştır:** `cd qwen3 && python egit_tokenizer.py`

Hazır tokenizer kütüphanesi (`tokenizers`, `transformers`) **kullanılmadı**.
Algoritma [HF LLM Course, Ch. 6.5](https://huggingface.co/learn/llm-course/en/chapter6/5)
temel alınarak elle yazıldı.

## Nasıl çalışıyor

1. **Ön-tokenizasyon** — her satır bir isim = bir "kelime". `\n` sınırdır; BPE asla
   iki ismi birbirine bağlayamaz.
2. **Temel sözlük** — 29 Türkçe harf + `\n` (id 0, aynı zamanda EOS).
3. **Eğitim döngüsü** — en sık geçen ardışık ikiliyi bul → birleştir → sözlüğe ekle
   → `vocab_size`'a ulaşana kadar tekrarla.
4. **Encode** — kelimeyi harflere böl, öğrenilen kuralları öncelik sırasıyla yeniden
   oynat.

### `yeşil` tokenının doğuşu

5 isimlik minik bir korpusta (`yeşilköy, kızılköy, yeşiltepe, kızıltepe, yeşilova`):

| Adım | Kazanan ikili | `yeşilköy` o an |
|:----:|---------------|-----------------|
| —    | —             | `y+e+ş+i+l+k+ö+y` |
| 1    | `ş`+`i`       | `y+e+şi+l+k+ö+y` |
| 2    | `şi`+`l`      | `y+e+şil+k+ö+y` |
| 3    | `y`+`e`       | `ye+şil+k+ö+y` |
| 4    | `ye`+`şil`    | **`yeşil`**`+k+ö+y` |

Adım 4'te iki çok-karakterli token birleşti (`ye`+`şil`). BPE böyle büyür: önce
heceler, sonra heceler birleşip kelimeler.

Kodda "yeşil bir Türkçe kelimedir" bilgisi yok. Sadece sayıldı.

### Beraberlik kuralı

Adım 1'de `eş`, `il`, `ye`, `şi` ikililerinin dördü de 3 kez geçiyordu. HF kursu bu
noktada *"kütüphane farklı seçtiği için sonuçlar birebir aynı olmaz"* diye uyarıyor.
Bu implementasyonda beraberlik **alfabetik** çözülüyor:

```python
best = max(pair_freqs, key=lambda p: (pair_freqs[p], p))
```

Sonuç: aynı veriyle her eğitim birebir aynı tokenizer'ı üretir (reproducibility).

## Ne öğrendi

Gerçek veri, `vocab_size=300` → 30 temel + **270 merge kuralı**.

**İlk 10 merge kuralı:** `ar` `an` `al` `er` `ak` `en` `ay` `ağ` `li` `aş`
→ Türkçe'nin en sık hece yapıları.

**Öğrenilen en uzun tokenlar:** `yukarı` `pınar` `aşağı` `büyük` `küçük` `demir`
`kızıl` `çayır` `çukur` `güney` `doğan` `uşağı`
→ Türkçe yer adı bileşenleri, denetimsiz keşfedildi.

## Vocab boyutu seçimi

| vocab | toplam token | sıkıştırma | `kızılyeşilköy` |
|------:|-------------:|-----------:|-----------------|
| 30    | 209.801 | 1.00x | `k+ı+z+ı+l+y+e+ş+i+l+k+ö+y` |
| 100   | 145.657 | 1.44x | `kı+z+ı+l+y+e+ş+il+köy` |
| 200   | 123.804 | 1.69x | `kız+ıl+y+eş+il+köy` |
| **300** | **113.331** | **1.85x** | **`kızıl+yeşil+köy`** ← seçilen |
| 500   | 101.448 | 2.07x | `kızıl+yeşil+köy` |
| 1000  | 88.399  | 2.37x | `kızıl+yeşil+köy` |

**Neden 300?** Kelimeler tam anlamlı parçalarına ayrılmaya bu noktada başlıyor.
Daha büyük vocab'da ek sıkıştırma kazancı azalırken embedding tablosu şişiyor ve
her token daha az örnek görüyor.

## Görülmemiş kelimeler

```
zonguldak        ->  z+on+g+ul+d+ak       (eğitimde yok, [UNK] yok)
vaşington        ->  v+aş+in+g+to+n       (yabancı kökenli, daha çok parçalandı)
kızılyeşilpınar  ->  kızıl+yeşil+pınar    (hiç görülmedi, mükemmel bölündü)
```

Temel sözlük eğitim verisinin **tüm** karakterlerini içerdiği için `[UNK]` imkânsız —
en kötü ihtimalle kelime harf harf bölünür. HF kursunun anlattığı byte-level BPE'ye
bu görevde ihtiyaç yok. (Byte-level, GPT-2 gibi açık uçlu metinlerde gerekir; bizim
alfabemiz kapalı.)

## Arayüz uyumluluğu

`BPETokenizer`, `CharTokenizer` ile aynı sözleşmeyi sunar:
`from_file` · `encode` · `decode` · `vocab_size` · `newline_id` · `eos_id` · `chars`

`chars` bir `@property`:

```python
@property
def chars(self) -> dict:
    return {"vocab": self.vocab, "merges": [list(m) for m in self.merges]}
```

`train.py` checkpoint'e `tokenizer.chars` kaydeder, `generate.py` de
`Tokenizer(ckpt["chars"])` ile geri yükler. İsmi koruduğum için **model kodunun tek
satırı değişmedi** — tokenizer tamamen değişti, dışarısı fark etmedi.

*(İsim artık teknik olarak yanlış: dönen şey karakter listesi değil. Upstream
sözleşmesine sadık kalmanın bedeli.)*

---

# Ödev 2 — Model Eğitimi

**Kod:** [`qwen3/train.py`](qwen3/train.py) · [`qwen3/generate.py`](qwen3/generate.py)
**Çalıştır:** `cd qwen3 && python train.py && python generate.py 30 0.8`

## Değişen satırlar

`train.py` (4 satır):
```python
from bpe_tokenizer import BPETokenizer      # önce: from tokenizer import CharTokenizer
VOCAB_SIZE = 300
tokenizer = BPETokenizer.from_file(DATA_FILE, vocab_size=VOCAB_SIZE)
```

`generate.py` (2 satır):
```python
from bpe_tokenizer import BPETokenizer
tokenizer = BPETokenizer(ckpt["chars"])
```

`model.py`, `attention.py`, `config.py` ve diğerlerine dokunulmadı.

## Yapılandırma

| | |
|---|---|
| Mimari | TinyQwen — RMSNorm, QK-Norm, GQA, RoPE, SwiGLU, pre-norm |
| Boyut | hidden 32 · 2 katman · 4 head (2 kv) |
| Parametre | 28.224 |
| Eğitim | 3000 adım · AdamW · lr 3e-3 · batch 64 · block 16 |
| Donanım | CPU, ~2 dakika |

## Sonuçlar: Char vs BPE

`python karsilastir.py` çıktısı (loss = son 200 adımın ortalaması):

| | Char | BPE |
|---|---:|---:|
| vocab_size | 30 | 300 |
| parametre | 19.584 | 28.224 |
| toplam token | 209.801 | 113.331 |
| isim başına token | 8.2 | 4.0 |
| loss (nats/token) | 1.796 | 2.670 |
| baseline (ln vocab) | 3.401 | 5.704 |

### ⚠️ Loss'lar doğrudan karşılaştırılamaz

Loss **token başına** ölçülür ve iki modelin token'ı aynı şey değil. BPE modeli her
adımda 300 seçenek arasından seçiyor, char modeli 30 arasından. Rastgele tahminde
bile BPE'nin loss'u daha yüksek olurdu: `ln(300)=5.70` vs `ln(30)=3.40`.

BPE'nin loss'u **daha yüksek görünüyor** ama işi daha zor.

### Adil metrik: bits per character

Loss'u, her token'ın taşıdığı karakter sayısına bölersek karşılaştırılabilir hale gelir:

```
BPC = loss_per_token × (token_sayısı / karakter_sayısı) / ln(2)
```

| | Char | BPE |
|---|---:|---:|
| baseline BPC | 4.907 | 4.445 |
| **model BPC** | **2.591** | **2.081** |

**BPE karakter başına %19.7 daha iyi.** Aynı metni ~%20 daha az bilgiyle anlatıyor.

Bu metrik dil modeli literatüründe farklı tokenizer'ları kıyaslamanın standart yolu.

### Takas

Parametre 19.584 → 28.224 (**+%44**). Sebep: embedding tablosu `vocab × hidden` =
`300×32 = 9.600` (eskiden `30×32 = 960`), çıkış katmanı da aynı oranda büyüdü.

BPE'nin faydası çift yönlü: daha kısa diziler **ve** aynı pencerede daha çok bağlam.
`BLOCK_SIZE=16` char'da ~2 isim görürken BPE'de ~4 isim görüyor.

## Ezber mi, genelleme mi?

Her sıcaklıkta 500 isim üretip eğitim verisiyle karşılaştırdım:

| T | benzersiz | ezberlenmiş | **yeni** | örnekler |
|:---:|---:|---:|---:|---|
| 0.5 | 442 | 62 (%14) | **380 (%86)** | `yukarıhamzayolu`, `küçükkaravaca`, `büyükdocahan` |
| 0.8 | 497 | 45 (%9) | **452 (%91)** | `demiratarıkboğaz`, `yukarıbüyükfalar` |
| 1.0 | 499 | 24 (%5) | **475 (%95)** | `yukarıbüyükkızılcaklıçat` |
| 1.2 | 499 | 20 (%4) | **479 (%96)** | `çiftetekbiayapapınar` |

Model ezberlemiyor — 28k parametreyle 22.682 ismi ezberlemek zaten imkânsız. Onun
yerine kuralı öğrenmiş: *yer adları `yukarı/aşağı/büyük/küçük` + kök +
`köy/pınar/oba/çat` parçalarından kurulur.*

Düşük sıcaklıkta ezber artıyor (%14) — model en olası, yani eğitimde en çok gördüğü
yola giriyor.

## Sıcaklık etkisi

```
T=0.3   kesi, kepenli, benli, tümlü, süse, süğü, kanan, kanan        ← güvenli, tekrarlı
T=0.6   kazara, kepenli, danardak, eğre, süsedibi, sinli, yaran
T=1.0   yeniyerdu, kepahi, danaroca, eğrecik, çayıra, alansaraybatı
T=1.4   karlıpınar, danarluün, eğirköse, adüftükdibi, çayırinli      ← yaratıcı, savruk
```

Sıcaklık, seçim öncesi olasılık dağılımını ölçekler. Düşük T dağılımı sivriltir
(monoton), yüksek T düzleştirir (tutarsız). **Tatlı nokta: T ≈ 0.5–0.8.**

---

## Veri

| | |
|---|---|
| Kaynak | [nejdetkadir/il-ilce-semt-mahalleler](https://github.com/nejdetkadir/il-ilce-semt-mahalleler) — resmî kayıtlardan derlenmiş |
| Ham | 81 il · 973 ilçe · 51.071 mahalle → 56.130 isim |
| Temiz | **22.682 benzersiz kelime** · 29 Türkçe harf |

**Boru hattı:**

```
data.json  →  hazirla.py  →  isimler.txt  →  temizle_isimler.py  →  temiz_isimler.txt
 (kaynak)    (indir+ayıkla)    (23.769)        (normalize+böl)          (22.682)
```

**`hazirla.py`** (benim): mahalle/semt/ilçe adlarını toplar · `Mah.`/`Köyü` eklerini
atar (yoksa model her isme "mah" yapıştırmayı öğrenir) · rakam/parantez içerenleri
eler · tekrarları siler (`Yeşilköy` 40 ilde var, model takıntı yapardı) · sıralar
(tekrarlanabilirlik).

**`temizle_isimler.py`** (upstream, değiştirilmedi): Türkçe-doğru küçültme · çok
kelimeli isimleri böler (`Aşağı Hacıbey` → `aşağı`, `hacıbey`) · tekrarları siler.

**Türkçe küçültme tuzağı:** Python'un `.lower()`'ı `"İzmir"` → `"i̇zmir"` üretir —
noktalı i'nin üstüne bir de ayrı *combining dot* karakteri biner. Gözle görünmez ama
tokenizer'da hayalet karakter olarak durur. Upstream script `I→ı`, `İ→i` eşlemesini
`.lower()`'dan **önce** uygulayarak bunu engelliyor.

---

## Dosya haritası

⭐ = ödev teslimi · 🆕 = benim · ✏️ = upstream + değişiklik · ⬜ = upstream, dokunulmadı

| Dosya | |
|---|---|
| `qwen3/bpe_tokenizer.py` | ⭐🆕 BPE implementasyonu (**Ödev 1**) |
| `qwen3/tokenizer.json` | ⭐ tokenizer artefaktı (`egit_tokenizer.py` üretir) |
| `qwen3/train.py` | ⭐✏️ 4 satır (**Ödev 2**) |
| `qwen3/egit_tokenizer.py` | 🆕 tokenizer'ı eğitir, `tokenizer.json` yazar, raporlar |
| `qwen3/karsilastir.py` | 🆕 Char vs BPE, BPC hesabı |
| `qwen3/generate.py` | ✏️ 2 satır |
| `data/hazirla.py` | 🆕 veri indirme/ayıklama |
| `data/isimler.txt` | 🆕 ham veri (`hazirla.py` üretir) |
| `data/temizle_isimler.py` | ⬜ upstream |
| `qwen3/tokenizer.py` | ⬜ upstream — `CharTokenizer`, karşılaştırma için tutuldu |
| `qwen3/model.py` · `attention.py` · `block.py` · `config.py` · `mlp.py` · `rms_norm.py` · `rotary.py` | ⬜ upstream |

**Repoda olmayan** (`.gitignore`, scriptlerle üretilir):
`data/data.json` · `data/temiz_isimler.txt` · `qwen3/tiny_qwen.pt`

---

## Kaynaklar

- **Model mimarisi:** [malibayram/single_letter_transformers](https://github.com/malibayram/single_letter_transformers) — detaylı atıf: [NOTICE.md](NOTICE.md)
- **BPE algoritması:** [HF LLM Course, Ch. 6.5](https://huggingface.co/learn/llm-course/en/chapter6/5)
- **Veri:** [nejdetkadir/il-ilce-semt-mahalleler](https://github.com/nejdetkadir/il-ilce-semt-mahalleler)
- **Orijinal makale:** Sennrich, R., Haddow, B., & Birch, A. (2016). *Neural Machine Translation of Rare Words with Subword Units.* ACL.
