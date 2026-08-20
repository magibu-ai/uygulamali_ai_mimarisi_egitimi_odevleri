# Ornek Konusmalar

Yerel model: `gemma4` (Ollama) — asagidaki ciktilar dogrudan terminalden alinmistir.

## Ders kitabindan cevap (fizik)

```
Siz > Fotoelektrik olayi nedir, nasil aciklanir?
  [arac] ders_ara({'ders': 'fizik', 'soru': 'Fotoelektrik olayi nedir, nasil aciklanir?'})

Asistan > Fotoelektrik olay, belirli bir metalik yüzeye gelen ışığın bu yüzeyden elektronlar salmasına sebep olması olayıdır. Bu olgu, XIX. yüzyılın ikinci yarısında belirli bir metalik yüzeye gelen ışığın bu yüzeyden elektronlar salınmasına sebep olduğu deneylerle gösterilmiştir.

Bu olay, ışığın tanecik özelliğine bağlanır. Bir foton, enerjisini metalde bulunan bir elektrona verir ve kendisi soğurulur. Ayrıca, bir foton ancak bir elektron sökebilir.

Kaynaklar:
- fizik kitabi, parca 415 (benzerlik 0.646)
- fizik kitabi, parca 376 (benzerlik 0.597)
- fizik kitabi, parca 229 (benzerlik 0.582)
- fizik kitabi, parca 37 (benzerlik 0.545)
```

## Ders kitabindan cevap (kimya)

```
Siz > Mol kavramini ve mol sayisinin nasil hesaplandigini anlatir misin?
  [arac] ders_ara({'ders': 'kimya', 'soru': 'Mol kavramı ve mol sayısının hesaplanması'})

Asistan > Mol kavramı, küçük taneciklere sahip maddelerin tanecik sayısı ve kütlesi arasındaki ilişkiyi veren bir birimdir. Bu birim, kimya biliminde de aynı amaçla tanımlanmıştır.

Mol sayısının hesaplanmasıyla ilgili olarak, mol kavramının tanımı verilmiştir.

(Ek bilgi olarak, çözeltide çözünmüş maddenin mol sayısına 1 litre çözeltide molarite denir ve bu, "M" ile gösterilir.)

Kaynaklar:
- kimya kitabi, parca 288 (benzerlik 0.659)
- kimya kitabi, parca 728 (benzerlik 0.638)
- kimya kitabi, parca 597 (benzerlik 0.633)
- kimya kitabi, parca 614 (benzerlik 0.627)
```

## Ders kitabindan cevap (tarih)

```
Siz > Kurtulus Savasi'nda TBMM'nin acilmasinin onemi neydi?
  [arac] ders_ara({'ders': 'tarih', 'soru': "Kurtuluş Savaşı'nda TBMM'nin açılmasının önemi neydi?"})

Asistan > Tarih

Kurtuluş Savaşı'nda TBMM'nin açılmasının önemi, millî iradenin merkezi olması ve cumhuriyet yönetimine geçilmesi için atılan büyük bir adım olmasıydı. Ayrıca, 23 Nisan 1920'de Büyük Millet Meclisi (BMM) olarak açılmasıyla, Mustafa Kemal'in önderliğinde millet egemenliğine dayalı bir yönetime geçme çalışmaları başlatılmıştır.

Kaynaklar:
- tarih kitabi, parca 449 (benzerlik 0.597)
- tarih kitabi, parca 125 (benzerlik 0.588)
- tarih kitabi, parca 223 (benzerlik 0.57)
- tarih kitabi, parca 224 (benzerlik 0.541)
```

## Kitapta olmayan guncel bilgi -> internet

```
Siz > 2026 yilinda Nobel Fizik Odulu'nu kim kazandi?
  [arac] internet_ara({'sorgu': '2026 Nobel Fizik Ödülü'})

Asistan > Bu bilgi ders kitaplarında yok, internetten alindi.

Ben bir yapay zeka asistanıyım ve benim bilgi kesim tarihim güncel olayları kapsamayabilir. Ayrıca, Nobel ödülleri gibi gelecekteki olaylar hakkında kesin bilgiye sahip olamam. Verdiğim internet araması sonuçlarına göre, 2026 Nobel Fizik Ödülü'nü kimin kazandığı bilgisi şu an için mevcut değil.
```

## Calisma plani

```
Siz > Kimyada mol konusuna 3 gunde calismak istiyorum, plan yapar misin?
  [arac] calisma_plani({'ders': 'kimya', 'gun': 3, 'konu': 'mol'})

Asistan > Bu, kimyada mol konusunu 3 güne yayabileceğin bir çalışma planı taslağıdır. Bu plan, ders kitaplarındaki içeriğe dayanmaktadır. Başarılar dilerim!
```

## Hesaplama

```
Siz > Bir cismin kutlesi 12 kg, ivmesi 9.8 m/s2. Kuvveti hesaplar misin?
  [arac] ders_ara({'ders': 'fizik', 'soru': 'kütle 12 kg, ivme 9.8 m/s2 olan cismin kuvveti'})
  [arac] hesapla({'ifade': '12 * 9.8'})

Asistan > $F = 12 \text{ kg} \cdot 9.8 \text{ m/s}^2 = 117.6 \text{ N}$

**Cismin üzerine etki eden kuvvet $117.6 \text{ Newton (N)}$'dur.**
```

## Arac gerektirmeyen sohbet

```
Siz > Merhaba, bugun nasilsin?

Asistan > Merhaba! Ben bir ders çalışma asistanıyım ve bugün sana yardımcı olmak için buradayım. Sen nasılsın? Hangi derste yardıma ihtiyacın var? 😊
```
