# Sonuç Logu (checkpoint'lerden otomatik üretildi)

`python sonuclar_uret.py` ile üretilir. Metrikler eğitilmiş modellerin
gerçek değerleridir; örnekler her çalıştırmada canlı üretilir.

## Metrikler (son kayıba göre sıralı)

| Sıra | Model | Sınıf | Parametre | Taban kayıp | Son kayıp | İyileşme |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gemma4 | TinyGemma | 63,360 | 3.47 | 0.6425 | 5.4× |
| 2 | qwen3_5 | TinyQwen35 | 42,056 | 3.47 | 0.6761 | 5.1× |
| 3 | deepseek3 | TinyDeepSeek | 48,040 | 3.47 | 0.9063 | 3.8× |
| 4 | qwen3 | TinyQwen | 19,648 | 3.47 | 1.1683 | 3.0× |

## Üretilen mineral adları (T=0.8)

- **gemma4:** hausmanit, selen, ksonomalit, morimorit, böhmit, kintonit, fransevillin, ferokz, nevillin, trondit
- **qwen3_5:** kalkofillit, barrerit, yugavaralit, nikelin, pirotin, tomsonit, kalkofillit, fenikokroit, mustit, landit
- **deepseek3:** kireçtaşı, ferrit, götit, ferokobaltit, dilonit, evenkit, saverit, vurmak, bişonit, karneol
- **qwen3:** akimbtait, maghematit, manganortanit, inezit, toryit, dalit, klinoklor, aulşen, mikronit, biyonit

## Üretilen mineral adları (T=1.1)

- **gemma4:** benjaminit, langingit, iserit, sular, huderokonit, levinit, gloropat, kupvanit, imojolumit, hieratit
- **qwen3_5:** ferrierit, ransevit, illit, plajgadoit, siderofillit, trüversutit, barrertit, frankiraz, biyosparit, forstefrerit
- **deepseek3:** simplezit, paratokit, pseiklehekzahidrrit, ferroit, erion, pakokinit, hahnit, ksebergit, meinoxel, olenit
- **qwen3:** ponzit, atafit, doikzit, mellür, ferbilit, olastronskuntit, argentanit, imonit, rokint, lsitan
