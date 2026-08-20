# Ödev 1 — BPE Tokenizer (Sonuçlar)

**Görev:** Seçilen metin üzerinden BPE algoritmasıyla bir tokenizasyon kurmak.

> Bu ödev, model eğitimi ödevinden **bağımsızdır**. Buradaki `tokenizer.json`
> model eğitiminde kullanılmaz; eğitim karakter token'larıyla yapılır
> (bkz. `SONUCLAR.md`). İki ödevin tek ortak noktası aynı metni kullanmaları.

## Kurulum

BPE, HuggingFace `tokenizers` kütüphanesiyle (hazır kütüphane) eğitildi ve
standart **`tokenizer.json`** çıktısı üretildi — `hf_bpe.py`.

- Metin: **1000** mineral/taş adı (`data/mineraller.txt`), her satırda bir ad
- Sözlük boyutu: **500** token
- Pre-tokenizer: `Whitespace` — her satır tek "kelime" olduğundan birleştirmeler
  ad sınırını aşmaz, yani EOS (`\n`) asla harflere yapışmaz
- Özel token: `\n` (ad ayıracı / EOS), sabit id

## Doğrulama

- **Roundtrip kayıpsız:** 1000/1000 adda `decode(encode(x)) == x` ✓
- Ad başına ortalama **4.12** token (toplam 4118 token)
- Adların yalnızca **%1.8'i** tek token'a çöküyor — sözlük adları ezberlemiyor,
  ek/kök yapısını öğreniyor

## Öğrenilen alt-parçalar

BPE'nin mineral morfolojisini yakaladığı görülüyor: `pirit`, `matit`, `kolumbit`,
`kalko`, `mangan`, `-it`, `-şist`. Mineral adları bu ekleri/önekleri sık tekrarlar,
BPE de tam bunları tek token yapıyor.

Örnek tokenizasyon:
```
'hematit'         -> ['he', 'matit', '\n']
'kalkopirit'      -> ['kalko', 'pirit', '\n']
'rodokrozit'      -> ['rod', 'ok', 'ro', 'zit', '\n']
'manganokolumbit' -> ['mangan', 'o', 'kolumbit', '\n']
```

## Sözlük boyutu seçimi

`vocab_size` BPE'nin zorunlu parametresidir (birleştirmenin nerede duracağını
söyler). 200 ve 500 denendi; tokenizer seviyesindeki ölçümler:

| | vocab 200 | vocab 500 |
| --- | --- | --- |
| toplam token | 5019 | 4118 |
| ad başına token | 5.02 | 4.12 |
| token başına ortalama görülme | 25.1 | 8.2 |
| korpusta 5 kereden az geçen sözlük girdisi | 4 (%2) | 306 (%61) |

500 daha kısa diziler ve daha anlamlı tam ekler (`pirit`, `kolumbit`) veriyor;
buna karşılık sözlüğün %61'i korpusta 5 kereden az geçiyor. 200 ise istatistiksel
olarak daha sağlam ama parçaları daha kırık (`he`, `ma`, `tit`).

Bu ödevde 500 tercih edildi (daha anlamlı alt-parçalar). 1000 adlık bir metin için
sözlüğün üst sınıra yakın olduğu, yukarıdaki tablodan görülüyor.

## Çalıştırma

```
python hf_bpe.py      # -> tokenizer.json + örnek tokenizasyon çıktısı
```
