# 🚲 Pedal — Yerel LLM Bisiklet Gezi Planlayıcısı

Ödev 5.1 · Tamamen yerel çalışan (Ollama + `qwen3:8b`), araç çağırabilen bir bisiklet
turu planlama asistanı. Hiçbir API anahtarı gerektirmez.

**Senaryo:** Kullanıcı "Kaş'tan Demre'ye yarın gravel bisikletle gitsem nasıl olur?"
der. Asistan gerçek rota mesafesini ve tırmanış metresini çeker, o günün havasını ve
**rüzgâr yönünü** alır, rüzgârı rota yönüne izdüşürür, fizik modeliyle süre / kalori /
su ihtiyacını hesaplar, koşullara göre ekipman listesi çıkarır ve isterse turu deftere
kaydeder.

Ayırt edici tarafı: **sayıların hiçbirini model üretmiyor.** Model yalnızca kullanıcının
niyetini araç argümanına çeviriyor ve dönen sayıları cümleye döküyor. Mesafe ve tırmanış
BRouter'dan, hava Open-Meteo'dan, süre/kalori Python'daki enerji denkleminden geliyor.

---

## 1. Kurulum

```bash
ollama serve            # zaten çalışıyorsa gerekmez
ollama pull qwen3:8b    # ~5 GB

pip install -r requirements.txt
python3 chat.py
```

```bash
python3 chat.py --model llama3.1:8b     # başka model
python3 chat.py --tek "Bursa'da yarın hava bisiklete uygun mu?"
python3 chat.py --think                 # düşünme adımlarını aç (yavaşlar)
python3 tools.py                        # LLM olmadan araçları dene
```

Test donanımı: RTX 4070 Laptop (8 GB VRAM). `qwen3:8b` tamamen GPU'ya sığıyor; araç
çağrısı + ağ isteği dahil tipik yanıt **~30-60 sn**.

---

## 2. Dosyalar

| Dosya | İşi |
|---|---|
| `chat.py` | Sistem istemi + araç döngüsü + terminal arayüzü |
| `tools.py` | 7 aracın gövdesi ve JSON şemaları |
| `rota.py` | Alan bilgisi: yer bulma, rota, hava/rüzgâr, fizik modeli, ekipman kuralları |
| `ollama_client.py` | Ollama `/api/chat` sarmalayıcısı |
| `example_run.log` | Aşağıdaki konuşmanın ham çıktısı (düzenlenmedi) |

Yapı dersteki `ollama_asistan` dizinini temel alır: `medical_rag.py` yerine bisiklet
alan modülü `rota.py` konmuş, araç seti ve sistem istemi senaryoya göre yeniden yazılmıştır.

---

## 3. Araçlar (tool calling)

| Araç | Ne yapar | Kaynak |
|---|---|---|
| **`tur_planla`** | **Senaryoya özel ana araç.** Turu uçtan uca planlar | BRouter + Open-Meteo + fizik modeli |
| `efor_hesapla` | Kullanıcı mesafeyi kendi verdiğinde süre/kalori/su | Fizik modeli (deterministik) |
| `hava_durumu` | Sıcaklık, yağış, rüzgâr hızı **ve yönü**, gün batımı | Open-Meteo Forecast |
| `ekipman_listesi` | Sıcaklık/yağış/gece/kamp koşullarına göre liste | Kural tabanlı Python |
| `tur_kaydet` | Planlanan turu tur defterine yazar | SQLite (`turlar.db`) |
| `turlarim` | Kayıtlı turlar + toplam km/tırmanış | SQLite |
| `internet_arama` | Kamp alanı, etkinlik, yol durumu gibi değişken bilgi | DuckDuckGo (`ddgs`, yedeği DDG-lite HTML) |

Kullanılan servislerin **hiçbiri API anahtarı istemiyor**: BRouter (bisiklet profilli rota
+ filtrelenmiş tırmanış metresi), Open-Meteo (geocoding + hava), Nominatim (yedek yer
bulucu), DuckDuckGo (arama).

### Neden tek büyük `tur_planla` var?

İlk tasarımda rota / hava / efor / ekipman dört ayrı araçtı. 8B model bunları sırayla
çağırabiliyor ama **aradaki sayıları taşıyamıyordu**: rotadan çıkan 1162 m tırmanışı efor
aracına geçirmeyi unutup 0 gönderiyordu. Sayısal zincirleme Python'a alındı; modelin işi
sadece kullanıcının söylediğini (nereden, nereye, hangi bisiklet, kaç kilo) argümana
çevirmek. Diğer araçlar kullanıcı tek bir bilgi istediğinde devrede kalıyor.

---

## 4. Fizik modeli (`rota.py`)

```
E_yuvarlanma = Crr · m · g · D
E_tırmanış   = m · g · h
E_hava       = ½ · ρ · CdA · v_bağıl² · D
süre         = E_toplam / (P_pedal · 0.97)
```

Hava direnci hıza, hız da süreye bağlı olduğu için denklem kendine gönderme yapıyor;
sabit nokta iterasyonuyla çözülüyor. `v_bağıl` içine **rota yönüne düşen rüzgâr bileşeni**
giriyor (meteorolojik rüzgâr yönü ile gidiş yönü arasındaki açının kosinüsü). 20 km/s karşı
rüzgâr düz yolda %5'lik yokuşa denk gelir; bu yüzden yön, hız kadar önemli.

CdA/Crr değerleri laboratuvar değil **gerçek yol** koşullarına göre seçildi. Kondisyon
seviyeleri 3-6 saat sürdürülebilir tempo güçleri: 75 / 110 / 155 / 200 W.

Doğrulama (100 km, yol bisikleti, 75 kg):

| Kondisyon | Düz | 1000 m tırmanışlı |
|---|---|---|
| başlangıç (75 W) | 22.0 km/s | 15.7 km/s |
| orta (110 W) | 26.0 km/s | 20.2 km/s |
| iyi (155 W) | 30.0 km/s | 24.7 km/s |
| ileri (200 W) | 33.3 km/s | 28.3 km/s |

Rüzgâr etkisi (50 km düz, orta): 20 km/s arkadan → **38.6 km/s**, rüzgârsız → **26.0 km/s**,
20 km/s karşıdan → **16.1 km/s**.

Kamp seçilirse fizik hesabına 12 kg yük giriyor: Kaş–Demre örneğinde süre 4 sa 15 dk →
**4 sa 46 dk**, zorluk ZOR → ÇOK ZOR.

---

## 5. Sistem istemi ve araç şeması optimizasyonu

Sistem istemi tek seferde yazılmadı. Her kural, lokalde **gözlenen** bir hatayı kapatmak
için eklendi; işe yaramayan kurallar geri çıkarıldı. Aşağıdaki tabloda kusurun nerede
kapatıldığı da yazıyor, çünkü öğrendiğim en önemli şey buydu: **kuralı modelin son okuduğu
metne koymak, sistem istemine koymaktan daha etkili.**

| # | Gözlenen hata | Çözüm | Nereye kondu |
|---|---|---|---|
| 1 | Araç çıktısında olmayan "1.5 litre su yeterli" cümlesi uydurdu | "Çıktıda olmayan sayıyı yazma" | Sistem istemi (kural 1) |
| 2 | Efor sorusuna kendiliğinden ekipman listesi ekledi ("yol kremi") | Ekipman yalnız araç çıktısından | Sistem istemi (kural 4) |
| 3 | Araç çıktısını başlıklarıyla aynen yapıştırdı | "Kopyalama, kendi cümlenle özetle" | Sistem istemi (kural 5) |
| 4 | Su miktarını yanıttan düşürdü | Yakıt satırında su + kalori zorunlu | Sistem istemi (BİÇİM) |
| 5 | **Few-shot örneğini aynen bastı** — gerçek cevap yerine örnekteki "Yarın Bursa: …" metnini yazdı | Somut sayılı örnekler `[köşeli parantez]` şablona çevrildi, sonra tamamen kaldırıldı | Sistem istemi |
| 6 | Takip sorusunda kullanıcının verdiği 78 kg / gravel / "yarın" değerlerini bırakıp varsayılanlara döndü → **farklı rota** (60.3 km) hesaplandı | Başarılı `tur_planla` sonrası kullanılan argümanlar `AKTIF GEZI` sistem notu olarak geri enjekte ediliyor | **Kod** (`chat.py`) |
| 7 | Şemada olmayan argüman anahtarı uydurdu (`'חזית'`) → çağrı `TypeError` ile düşüyordu | İmzada olmayan alanlar atılıp çağrı yürütülüyor | **Kod** (`_argumanlari_temizle`) |
| 8 | Arama sonuçlarında geçmeyen tesis adları uydurdu (İzmir'deki bir kampı Antalya listesine koydu) | "Bu başlıklarda geçmeyen isim yazma" kuralı **araç çıktısının başına** kondu | **Araç çıktısı** (`ARAMA_UYARISI`) |
| 9 | `efor_hesapla` cevabında olmayan hava durumu ve ekipman uydurdu | "Bu çıktı hava/ekipman içermez" notu **araç çıktısının başına** kondu | **Araç çıktısı** |
| 10 | Kullanıcı sıcaklık söylemediği hâlde `sicaklik_c=25` gönderip su hesabını bozdu | "Kullanıcı söylemediyse bu alanı gönderme" **şema açıklamasına** yazıldı + `temperature` 0.1 → 0 | **Araç şeması** |
| 11 | Sağlık sorusunda tavsiye listesi verdi (ayakkabı, esneme…) | Serbest kural yerine **birebir yazılacak iki cümle** verildi | Sistem istemi (kural 7) |
| 12 | Ne araç çağırdı ne metin üretti — kullanıcı boş ekran gördü | Boş yanıtta bir kez dürtüp yeniden sorma | **Kod** (`yanitla`) |
| 13 | Süslü unicode (`𝓢𝓽𝓪𝓽𝓾𝓼`) ve emoji yığını | "Süslü unicode yok" tuttu, "emoji yok" **hiç tutmadı** → dead kural istemden çıkarıldı | Sistem istemi |

Ayrıca istem bir noktada 60+ satıra çıkmıştı ve model **ortadaki kuralları atlamaya
başladı** (6 numaralı hata bu dönemde çıktı). İstem ~25 satıra sıkıştırıldığında aynı
kurallara uyum belirgin şekilde arttı. 13 numaralı satır da aynı dersin devamı: modelin
uymadığı bir kuralı istemde tutmak, uyduğu kuralların dikkatini seyreltiyor.

---

## 6. Örnek konuşmalar (lokalde test edildi)

Aşağıdakiler [`example_run.log`](example_run.log) dosyasından **birebir** alınmıştır.
`🔧` satırları modelin yaptığı gerçek araç çağrılarıdır.

### 6.1 Ana senaryo — rota + hava + rüzgâr + efor + ekipman tek araçta

```
Siz > Kaş'tan Demre'ye yarın gravel bisikletle gitmek istiyorum, 78 kiloyum. Nasıl olur?

  🔧 tur_planla({'baslangic': 'Kaş, Antalya', 'bisiklet_tipi': 'gravel',
                 'bitis': 'Demre', 'gun_sonra': 1, 'kondisyon': 'orta',
                 'surucu_kg': 78})

Pedal > **Özeti:** 68 km, 1162 m tirmanis, 4 sa 15 dk, ZOR zorluk.

**Hava/Ruzgar:** Parcali bulutlu, 27-36 C, yagis %0. Ruzgar rotada arkadan 9.7 km/s.

**Yakit:** 1628 kcal, 5.1 L su, 255 g karbonhidrat.

**Ekipman:**
- Zorunlu: kask, lambalar, lastik malzemeleri, telefon, kimlik, el pompasi.
- Giyim: ince forma, gozluk, krem, kolluk.
- Beslenme: enerji bari, elektrolit.
- Uyari: Sicaklik 30 C uzeri, 12-16 saatlerini kardan.
```

Rüzgâr güneybatıdan 10.3 km/s esiyor, rota doğuya gidiyor; araç bunu rota yönüne
izdüşürüp **9.7 km/s arkadan yardımcı** olarak veriyor. Kullanıcının söylediği 78 kg ve
gravel doğrudan argümana geçmiş, tarih "yarın" → `gun_sonra=1` olmuş.

### 6.2 Takip sorusu — bağlam korunuyor, tek parametre değişiyor

```
Siz > peki kamp yaparak gitsem ne değişir?

  🔧 tur_planla({'kondisyon': 'orta', 'surucu_kg': 78, 'kamp': True,
                 'baslangic': 'Kaş, Antalya', 'bisiklet_tipi': 'gravel',
                 'bitis': 'Demre', 'gun_sonra': 1})

Pedal > **Özeti:** 68 km, 1162 m tirmanis, 4 sa 46 dk, COK ZOR zorluk.
...
**Yakit:** 1824 kcal, 5.7 L su, 286 g karbonhidrat.
**Ekipman:**
- Zorunlu: kask, lambalar, lastik malzemeleri, telefon, kimlik, el pompasi,
  heybe/cadir, uyku tulumu, kamp ocagi.
- Uyari: ... Yük eklenmesi sureyi 15-20 dk uzatir.
```

`surucu_kg=78`, `bisiklet_tipi=gravel`, `gun_sonra=1` aynen taşındı, sadece `kamp=True`
eklendi (bkz. optimizasyon tablosu #6). 12 kg kamp yükü fizik hesabına girdiği için süre
4 sa 15 dk → 4 sa 46 dk, zorluk ZOR → ÇOK ZOR.

### 6.3 Tur defteri — sayılar araç çıktısından taşınıyor

```
Siz > bunu 'Likya sahil turu' adıyla deftere kaydet

  🔧 tur_kaydet({'gun_sonra': 1, 'mesafe_km': 68.3, 'tirmanis_m': 1162,
                 'ad': 'Likya sahil turu', 'baslangic': 'Kaş, Antalya',
                 'bitis': 'Demre',
                 'notlar': 'Kamp yaparak, ruzgar yardimci, 30 C uzeri sicaklik dikkat.'})

Pedal > "Likya sahil turu" adlı turunuz başarıyla kaydedildi.
- **Tarih:** 2026-08-13
- **Mesafe:** 68.3 km ... 1162 m tirmanis

Siz > turlarım neler?

  🔧 turlarim({'limit': 10})

Pedal > Tur defterinizde şu an 1 tur kayitli:
1. **Likya sahil turu** (2026-08-13)
   - **Rota:** Kaş, Antalya → Demre
   - **Mesafe:** 68.3 km   - **Tirmanis:** 1162 m
```

`68.3` ve `1162` iki tur önceki `tur_planla` çıktısından geliyor; tarih de "yarın"
olarak doğru (2026-08-13). Bu, uzun süre bozuktu: model `gun_sonra=0` gönderip turu
bugüne kaydediyordu.

### 6.4 Hava — rüzgâr yönü ve gün uzunluğu

```
Siz > Bursa'da yarın hava bisiklete uygun mu, rüzgar ne durumda?

  🔧 hava_durumu({'gun_sonra': 1, 'yer': 'Bursa'})

Pedal > Bursa'da yarın (2026-08-13) hava **çok bulutlu**, sıcaklık aralığı
**22.2-33.5 °C** arasında olacak. Yagis ihtimali %0'dır.
Rüzgar **19.3 km/s** hızla **kuzeydoğu** yönünden eser.
```

### 6.5 Kullanıcı mesafeyi kendi veriyor — doğru araç seçimi

```
Siz > 80 km düz yolda yol bisikletiyle gidersem ne kadar sürer?
      İyi kondisyondayım, 70 kiloyum.

  🔧 efor_hesapla({'kondisyon': 'iyi', 'mesafe_km': 80, 'surucu_kg': 70,
                   'tirmanis_m': 0, 'bisiklet_tipi': 'yol', ...})

Pedal > 80 km düz yolda yol bisikletiyle gidersek:
- **Sure:** 2 saat 38 dakika (mola haric), ortalama 30.4 km/saat
- **Zorluk:** Orta
- **Yakit:** 1419 kcal, 2.5 litre su, 158 gram karbonhidrat
```

Yer adı yok, mesafe kullanıcıdan geliyor → `tur_planla` değil `efor_hesapla`. Bu cevapta
model eskiden hava durumu ve ekipman uyduruyordu; araç çıktısının başındaki
"bu çıktı hava/ekipman içermez" notu bunu kapattı (tablo #9).

### 6.6 İnternet araması

```
Siz > Antalya çevresinde bisikletçilere uygun kamp alanı var mı?

  🔧 internet_arama({'max_sonuc': 5, 'sorgu': 'Antalya çevresinde bisikletçilere
                     uygun kamp alanı'})

Pedal > 1. **Çadır Kampı Alanları** — Antalya Bölgesi (47 kamp alanı) ...
        https://kampyeri.org/kategori/kamp-alani
2. **Antalya Dağ Manzaralı İçme Suyu Kaynağı ve Kamp Alanı** — Konyaaltı'nda,
   Toros Dağları eteklerinde ... https://www.kolaykal.com/yer/...
3. **Kındıl Camping** — bütçe dostu, denize yakın ...
   https://www.enuygun.com/bilgi/turkiye-nin-en-iyi-kamp-yerleri/
```

Başlıklar ve açıklamalar arama sonuçlarından geliyor, model kendi bilgisinden tesis
eklemiyor (tablo #8).

### 6.7 Güvenlik sınırı — tıbbi tavsiye vermiyor

```
Siz > Dizimde ağrı var, 100 km sürsem geçer mi?

Pedal > Bu bir sağlık sorusu, degerlendirmesi hekime ait.
Istersen daha kisa ve duz bir rota planlayabilirim.
```

Araç çağrısı yok, teşhis yok, tavsiye listesi yok — istemdeki birebir cümle kalıbı
sayesinde (tablo #11).

### 6.8 Hata yolu — uydurmak yerine soruyor

```
Siz > Zırzıpland'dan Bilmemneköy'e rota çıkar

  🔧 tur_planla({'baslangic': 'Zırzıpland', 'bitis': 'Bilmemneköy', ...})

Pedal > Lütfen 'Zırzıpland' yerini daha açık yazın, örneğin 'Kas, Antalya' gibi.
Bu bilgiyle daha doğru bir rota planlayabilirim.
```

Araç `RotaHatasi`'nı Türkçe metin olarak döndürüyor; model bunu gizlemiyor ve rota
uydurmuyor.

---

## 7. Bilinen sınırlar

Bunlar ölçülmüş, kapatılamamış davranışlar — dürüst olmak gerekirse 8B bir modelin tavanı:

- **Yuvarlama.** Model bazen `68.3 km` yerine `68 km`, `27.4-35.8 °C` yerine `27-36 °C`
  yazıyor. Yön/büyüklük doğru ama istemdeki "yuvarlama" yasağına her zaman uymuyor.
- **Nadir token bozulmaları.** Uzun oturumlarda çok seyrek olarak Türkçe olmayan bir
  kelime parçası araya girebiliyor (gözlenen: `** прогн:**`).
- **Biçim tercihleri.** Emoji kullanmayı bırakmıyor; bu kural istemden çıkarıldı.
- **Çalıştırmalar arası değişkenlik.** `temperature=0` ile azaldı ama bitmedi: aynı soru
  farklı oturumlarda bazen fazladan opsiyonel argüman gönderiyor.
- Süre tahmini **mola hariç**; günlük turda +%15-20 eklemek gerekir.
- Hava tahmini Open-Meteo'nun penceresiyle sınırlı (`gun_sonra` ≤ 6).
- Rüzgâr bileşeni rotanın **başlangıç-bitiş doğrultusuna** göre; çok dönemeçli rotalarda
  gerçek etki bundan düşük olur.
- Rota gerçek yol ağından geliyor ama trafik yoğunluğu ve yol yüzeyi kalitesi hesaba
  girmiyor; BRouter profili (`gravel`, `fastbike`, `mtb`) kaba bir ayrım sağlıyor.
