# Ödev 2 — Karakter Token'larıyla Model Eğitimi (Sonuçlar)

**Görev:** Mineral / değerli taş adı üretme.

> Bu ödev BPE'den **bağımsızdır**. Eğitim, reponun kendi karakter tokenizer'ı ile
> yapılır; `tokenizer.json` (BPE) burada kullanılmaz — bkz. `BPE_SONUCLAR.md`.

## Tokenizasyon — karakter seviyesi

Repodaki `CharTokenizer` (`single_letter_transformers/<model>/tokenizer.py`)
aynen kullanıldı:

- Her token **tek karakter**
- Sözlük doğrudan metinden kurulur: **32** karakter
  (`abcdefghijklmnoprstuvwxyzçöüışš` + `\n`)
- `\n` hem ad ayıracı hem EOS (üretimde durdurma token'ı)
- Metin (1000 ad) → **9208** karakter token, ad başına ortalama **9.21**
- Taban(rastgele) kayıp = ln(32) = **3.47**

## Model eğitimi — repodaki BÜTÜN dil modelleri

4 mimarinin hepsi aynı karakter token'larıyla eğitildi.
Ortak ayar: CPU, 3000 adım, AdamW lr=3e-3, batch=64, block=16.

**Eğitilmeyenler (bilerek):**
- `acestep` — ses/müzik üretimi (DiT+VAE+flow), metin göreviyle alakasız.
- `lora` — bağımsız model değil, fine-tune eklentisi.

## Karşılaştırma tablosu

Aynı metin (1000 ad), aynı karakter tokenizer (vocab=32), aynı ayar.
"İyileşme" = taban ÷ son kayıp. Kayıba göre sıralı (düşük daha iyi).

| Sıra | Model | Parametre | Taban kayıp | Son kayıp | İyileşme | Ayırt edici özellik |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gemma4    | 63,360 | 3.47 | 0.6425 | 5.4× | Sliding-window local/global, sandwich norm, GeGLU |
| 2 | qwen3_5   | 42,056 | 3.47 | 0.6761 | 5.1× | Hibrit: Gated DeltaNet + her 4'te 1 tam attention |
| 3 | deepseek3 | 48,040 | 3.47 | 0.9063 | 3.8× | MLA (latent attn) + MoE (uzman karışımı) |
| 4 | qwen3     | 19,648 | 3.47 | 1.1683 | 3.0× | Yoğun (dense): RMSNorm + RoPE + GQA + SwiGLU |

> Bu tablo `SONUCLAR_LOG.md` ile eşitlenmiştir (`python sonuclar_uret.py`
> checkpoint'lerden otomatik üretir).

**Okuma:**
- **Kapasite sıralaması belirleyici.** En büyük model (`gemma4`, 63K) birinci,
  en küçük (`qwen3`, 20K) sonuncu. Aradaki fark küçük değil: 0.64 vs 1.17.
- `qwen3_5` (42K) parametre başına en verimlisi — `gemma4`'ün üçte iki
  parametresiyle neredeyse aynı kayba ulaşıyor (0.676 vs 0.643).
- `deepseek3` (MoE) parametresine göre öne çıkmıyor: 48K ile 0.91, 42K'lık
  `qwen3_5`'in gerisinde. MoE'nin faydası büyük ölçekte belirir, 1000 adlık
  metinde değil.
- Karakter seviyesinde görev BPE'ye göre daha zor: model her adı harf harf
  kurmak zorunda (ad başına 9.21 karar, BPE'de 4.12 idi).

Aşağıdaki örnekler tek bir örnekleme koşusundan alınmıştır. Üretim rastgeledir:
`sonuclar_uret.py` / `generate_model.py` her çalıştırmada **farklı adlar** verir.
Metrikler (yukarıdaki tablo) ise sabittir — checkpoint'lerin içinde saklıdır.

## Üretilen mineral adları (T=0.8 — güvenli)

```
gemma4:    hausmanit, böhmit, selen, kintonit, morimorit, nevillin, trondit
qwen3_5:   kalkofillit, barrerit, yugavaralit, nikelin, pirotin, tomsonit, fenikokroit
deepseek3: kireçtaşı, götit, karneol, evenkit, ferrit, ferokobaltit, dilonit
qwen3:     inezit, toryit, klinoklor, maghematit, manganortanit, dalit, biyonit
```

## Üretilen mineral adları (T=1.1 — yaratıcı)

```
gemma4:    benjaminit, levinit, hieratit, iserit, langingit, kupvanit, imojolumit
qwen3_5:   ferrierit, illit, siderofillit, biyosparit, plajgadoit, frankiraz
deepseek3: simplezit, olenit, ferroit, hahnit, paratokit, ksebergit, erion
qwen3:     imonit, ponzit, atafit, ferbilit, argentanit, mellür, rokint
```

Modeller hem gerçek mineralleri (`hausmanit, böhmit, nikelin, pirotin, götit,
karneol, inezit, toryit, klinoklor, ferrierit, illit, simplezit, olenit`) hem de
metinde olmayan yeni ama mineral'e benzeyen adlar (`morimorit`, `dilonit`,
`iserit`, `ponzit`) üretiyor — Türkçe mineral morfolojisini (`-it`, `-taşı`,
`klino-`, `ferro-`) harf seviyesinden öğrenerek.

Üretim kalitesi tabloyu doğruluyor: `gemma4` ve `qwen3_5` çoğunlukla gerçek ya da
inandırıcı adlar veriyor; `qwen3` (20K) daha sık bozuk çıktı üretiyor
(`akimbtait`, `olastronskuntit`) — kapasitesi 1000 adın dağılımını taşımıyor.

## Not

Metin 1000 ad ile mutlak anlamda küçük; tablo mimarilerin genel kalite sıralaması
değil, **bu ölçekteki kapasite/öğrenme davranışıdır**.

Tüm kayıplar **eğitim kaybı**; ayrı bir doğrulama kümesi yok. Modellerin ne
kadarının genelleme, ne kadarının ezber olduğu bu kurulumda ölçülmüyor.
