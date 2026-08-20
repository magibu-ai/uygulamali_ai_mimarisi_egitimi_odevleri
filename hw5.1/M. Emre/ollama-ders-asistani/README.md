# Ders Çalışma Asistanı — Yerel Model + Araç Çağırma

Tamamen yerelde çalışan, araç çağırabilen yani tool calling yapabilen  bir ders çalışma asistanıdır.
Sohbet modeli Ollama üzerinde, embedding üretimi ve vektör araması aynı makinede ve 
hiçbir ücretli servis veya API anahtarı kullanılmıyor.

Asistanın temel davranışı şu şekilde ayarland: bir fizik, kimya veya tarih sorusu geldiğinde önce
**ders kitabına** bakar. Kitapta karşılığı yoksa uydurmaz, açıkça bilmediğini söyler
ve gerekirse internete çıkıp bilginin kitaptan gelmediğini belirtir.

## Senaryo

Öğrenci üç dersin kitabıyla çalışıyor: fizik, kimya, tarih. Asistanın işi sadece
soru cevaplamaktan ziyade cevabın kaynağını doğru yönetmek. Sınavda ders kitabından
sorumlu olan bir öğrenci için "bu bilgi kitapta mı, internetten mi geldi?" ayrımı,
bilginin kendisi kadar önemli.

Bu yüzden sistemin merkezinde bir kaynak önceliği kuralı var: **önce kitap, sonra
internet, hiçbiri yoksa sessiz kalma değil açık ret.**

## Mimari

```
öğrenci sorusu
   │
   ▼
chat.py ── sistem istemi + araç şemaları ──► Ollama (gemma4)
   │                                            │
   │◄──────── tool_calls ───────────────────────┘
   │
   ├─ ders_ara ──► ders_rag.py ──► ChromaDB (2.427 parça)
   │                   │                │
   │                   │                └─ magibu/embeddingmagibu-200m (768 boyut)
   │                   └─ iki kapı: benzerlik eşiği + üretim talimatı
   │
   ├─ internet_ara ──► DuckDuckGo (yedek: Wikipedia)
   ├─ calisma_plani ──► ders kitabı içeriğinden gün gün program
   └─ hesapla ──► güvenli aritmetik (ast tabanlı, eval yok)
```

| Dosya | Sorumluluk |
|---|---|
| `chat.py` | Terminal sohbet döngüsü, sistem istemi, araç yönlendirme |
| `tools.py` | Dört araç ve JSON şemaları |
| `ders_rag.py` | Parçalama, embedding, vektör arama, iki kapılı cevap üretimi |
| `index_dersler.py` | Ders kitaplarını parçalayıp ChromaDB'ye yazar |
| `ollama_client.py` | Ollama `/api/chat` sarmalayıcısı |
| `ornek_konusmalar.py` | Aşağıdaki örnek konuşmaları üreten betik |

## Model seçimi

**Sohbet modeli: `gemma4` (Ollama, yerel).** Seçim ölçütü araç çağırma desteğiydi;
Ollama'da `ollama show gemma4` çıktısındaki yetenekler arasında `tools` bulunuyor.
Aynı makinedeki `qwen3:8b` ve `llama3.1:8b` de destekliyor, `--model` bayrağıyla
değiştirilebilir.

**Embedding modeli: `magibu/embeddingmagibu-200m`, 768 boyut.** Türkçe odaklı, 8192
token bağlam penceresi olan 430 MB'lık bir model. Bağlam penceresi burada önemli:
800 karakterlik parçalar hiçbir koşulda kırpılmıyor.

Embedding tarafı bilinçli olarak Ollama üzerinden değil, `sentence-transformers` ile
çalışıyor. Sebep hacim: 2.427 parçanın toplu (batch) vektörleştirilmesi Apple Silicon
üzerinde MPS hızlandırmasıyla 291 saniye sürdü. Sohbet modeli ise tamamen Ollama'da.

## Sistem istemi (system prompt)

Sistem istemi üç davranışı garanti altına almak için yazıldı:

**1. Kaynak önceliği.** Ders konusu bir soru geldiğinde önce `ders_ara` çağrılır,
modelin kendi bilgisiyle cevap vermesi yasaklanır. Bu olmadan model, kitapta olmayan
bilgileri kendi eğitiminden doldurur ve öğrenci farkı anlayamaz.

**2. Aktarma disiplini.** `ders_ara` çıktısı değiştirilmeden aktarılır — genişletme,
düzeltme, yorumlama yok. Araç zaten topraklanmış bir cevap döndürüyor; model onu
"iyileştirmeye" kalkarsa topraklama bozulur.

**3. Şeffaflık.** Bilgi internetten geldiyse cevaba açık bir not eklenir:
*"Bu bilgi ders kitaplarında yok, internetten alındı."*

İstemin tam metni `chat.py` içinde. Araç açıklamalarında da yönlendirme var:
`internet_ara` şemasında *"fizik/kimya/tarih sorularında önce ders_ara denenmeli"*
yazıyor. Kural yalnızca sistem isteminde değil, aracın kendi tanımında da tekrarlanıyor;
model iki yerden aynı sinyali alıyor.

## Araçlar

| Araç | Tür | İş |
|---|---|---|
| `ders_ara(soru, ders?)` | Senaryoya özel | Ders kitabı RAG'i, kaynak göstererek topraklanmış cevap |
| `calisma_plani(konu, gun, ders?)` | Senaryoya özel | Konuyu kitap içeriğine dayanarak günlere böler |
| `internet_ara(sorgu, adet)` | Genel | DuckDuckGo; erişilemezse Wikipedia API'sine düşer |
| `hesapla(ifade)` | Yardımcı | Fizik/kimya işlemleri için aritmetik |

`hesapla` aracında `eval()` kullanılmıyor. Modelin ürettiği metni doğrudan çalıştırmak,
modele kod yürütme yetkisi vermek demektir. Bunun yerine ifade `ast` ile ayrıştırılıyor
ve yalnızca dört işlem, üs alma ve mod düğümleri kabul ediliyor; geri kalan her şey
reddediliyor.

`calisma_plani` de plan uydurmuyor: konuyu önce vektör veritabanında arıyor, bulunan
parçaları günlere bölüyor. Kitapta karşılığı yoksa plan üretmiyor.

## RAG: iki kapı

Modelin ders kitabında olmayan bir şeyi uydurmasını iki bağımsız kapı engelliyor.

**1. Arama kapısı.** Getirilen parçaların hiçbiri benzerlik eşiğini geçemezse dil
modeli **hiç çağrılmaz**. Çağrılmayan model uyduramaz.

**2. Üretim kapısı.** Eşiği geçen parçalar modele verilirken talimat da veriliyor:
"sadece bu metinlerden cevapla, yetmiyorsa şu cümleyi yaz". Model kendi genel bilgisini
kullanmakla değil, önündeki metne sadık kalmakla yükümlü.

İkisi de gerekli, çünkü tek başına ikisi de yetmiyor. Somut örnek:

```
Soru : "2026 Nobel Fizik Ödülü kime verildi?"
1. kapı: benzerlik 0.521 ≥ 0.45  →  GEÇTİ (soruda "fizik" geçtiği için)
2. kapı: LLM parçaları okudu     →  "Bilmiyorum — bu bilgi ders kitaplarında bulunmuyor."
```

Birinci kapı bu soruyu durduramadı; "fizik" kelimesi fizik kitabı parçalarına yeterince
benzerlik üretti. İkinci kapı yakaladı. Tersi durumlar da var: alakasız bir soru
(`"Python'da liste nasıl oluşturulur?"` → 0.191) birinci kapıda eleniyor ve dil modeli
hiç çalıştırılmıyor, yani boşuna hesaplama yapılmıyor.

## Eşik değeri

Eşik `ders_rag.ESIK = 0.45`. Ölçülen skorlar:

| Sorgu | Skor | Sonuç |
|---|---|---|
| Mol sayısı nasıl hesaplanır? | 0,655 | kimya kitabından cevap |
| Fotoelektrik olayı nedir? | 0,642 | fizik kitabından cevap |
| Newton'un hareket yasaları | 0,618 | fizik kitabından cevap |
| Atatürk ilkeleri nelerdir? | 0,501 | tarih kitabından cevap |
| 2026 Nobel Fizik Ödülü | 0,521 | 1. kapıyı geçti, 2. kapıda reddedildi |
| İstanbul'da hava nasıl? | 0,442 | 1. kapıda elendi |
| Futbol maçı kaç dakika? | 0,331 | 1. kapıda elendi |
| Kurtuluş Savaşı ne zaman başladı? | 0,305 | 1. kapıda elendi (aşağıya bakınız) |
| Python'da liste oluşturma | 0,191 | 1. kapıda elendi |

Eşiği daha yükseğe çekmek (örneğin 0,55) Nobel sorusunu birinci kapıda elerdi, ama
"Atatürk ilkeleri" gibi gerçek ders sorularını da elemeye başlıyor. 0,45 bu iki hata
türü arasındaki denge noktası; birinci kapıdan sızan durumlar için zaten ikinci kapı var.

## Bilinen sınır: örnekleme

Ders kitaplarının tamamı 11,7 milyon karakter tutuyor ve yaklaşık 17.000 parça üretiyor.
Bu çalışmada kitap başına 500.000 karakter alındı, toplam 2.427 parça indekslendi.

Örnekleme kitabın başından değil, **eşit aralıklarla beş ayrı bölümünden** yapılıyor
(`index_dersler.py` içindeki `ornekle`); böylece tek bir üniteye sıkışmak yerine kitabın
geneline yayılıyor. Yine de kaçınılmaz bir sonucu var: örneklenmeyen bölümlerdeki
konular indekste bulunmuyor.

Yukarıdaki tabloda *"Kurtuluş Savaşı ne zaman başladı?"* sorusunun 0,305 alması bunun
somut örneği. Sistem hata yapmıyor — indekste o bölüm yok ve doğru biçimde "bilmiyorum"
diyor. Tam kapsama için `KITAP_BASINA_KARAKTER` değerini yükseltmek yeterli; maliyeti
yalnızca embedding süresi.

## Kurulum

Gereksinim: Python 3.12+, [Ollama](https://ollama.com) çalışır durumda.

```bash
ollama pull gemma4

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Ders metinlerini veri/ klasörüne koyun (dosya adı = ders adı)
#   veri/fizik.txt  veri/kimya.txt  veri/tarih.txt
python index_dersler.py     # parçalama + embedding + ChromaDB

python chat.py              # sohbeti başlat
python chat.py --model qwen3:8b
```

Ortam değişkenleri: `OLLAMA_HOST` (varsayılan `http://localhost:11434`),
`OLLAMA_CHAT_MODEL` (varsayılan `gemma4`).

### Veri hakkında

Ders kitabı metinleri telifli olduğu için depoya dahil edilmedi (`.gitignore`).
`veri/ornek.txt` beklenen biçimi gösteren küçük bir örnektir. Sistem düz metinle
çalışır, özel bir biçim aranmaz.

## Örnek konuşmalar

Aşağıdaki çıktılar `python ornek_konusmalar.py` ile doğrudan terminalden alınmıştır.
Yerel model: `gemma4`.

### 1. Ders kitabından cevap (fizik)

```
Siz > Fotoelektrik olayi nedir, nasil aciklanir?
  [arac] ders_ara({'ders': 'fizik', 'soru': 'Fotoelektrik olayı nedir, nasıl açıklanır?'})

Asistan > Fotoelektrik olay, XIX. yüzyılın ikinci yarısında belirli bir metalik yüzeye
gelen ışığın bu yüzeyden elektronlar salınmasına sebep olduğu deneylerle gösterilmiştir.
...
Kaynaklar:
- fizik kitabi, parca 512 (benzerlik 0.642)
```

### 2. Ders kitabından cevap (kimya)

```
Siz > Mol kavramini ve mol sayisinin nasil hesaplandigini anlatir misin?
  [arac] ders_ara({'ders': 'kimya', 'soru': 'Mol kavramı ve mol sayısının hesaplanması'})

Asistan > Mol kavramı, küçük taneciklere sahip maddelerin tanecik sayısı ve kütlesi
arasındaki ilişkiyi veren bir birimdir. Bu birim, kimya biliminde de aynı amaçla
tanımlanmıştır. Mol sayısının hesaplanmasıyla...
```

### 3. Ders kitabından cevap (tarih)

```
Siz > Kurtulus Savasi'nda TBMM'nin acilmasinin onemi neydi?
  [arac] ders_ara({'ders': 'tarih', 'soru': "Kurtuluş Savaşı'nda TBMM'nin açılmasının önemi neydi?"})

Asistan > Kurtuluş Savaşı'nda TBMM'nin açılmasının önemi, millî iradenin merkezi olması
ve cumhuriyet yönetimine geçilmesi için atılan büyük bir adım olmasıydı. Ayrıca,
23 Nisan 1920'de Büyük Millet Meclisi...
```

### 4. Kitapta olmayan bilgi → internete yönlenme

```
Siz > 2026 yilinda Nobel Fizik Odulu'nu kim kazandi?
  [arac] internet_ara({'sorgu': '2026 Nobel Fizik Ödülü'})

Asistan > Bu bilgi ders kitaplarında yok, internetten alindi.
...
```

Sistem isteminin şeffaflık kuralı burada devreye giriyor: model bilginin kaynağını
kendiliğinden belirtiyor.

### 5. Çalışma planı (senaryoya özel araç)

```
Siz > Kimyada mol konusuna 3 gunde calismak istiyorum, plan yapar misin?
  [arac] calisma_plani({'ders': 'kimya', 'gun': 3, 'konu': 'mol'})

Asistan > Bu, kimyada mol konusunu 3 güne yayabileceğin bir çalışma planı taslağıdır.
Bu plan, ders kitaplarındaki içeriğe dayanmaktadır. Başarılar dilerim!
```

### 6. İki aracın zincirlenmesi

```
Siz > Bir cismin kutlesi 12 kg, ivmesi 9.8 m/s2. Kuvveti hesaplar misin?
  [arac] ders_ara({'ders': 'fizik', 'soru': 'kütle 12 kg, ivme 9.8 m/s2 olan cismin kuvveti'})
  [arac] hesapla({'ifade': '12 * 9.8'})

Asistan > F = 12 kg · 9.8 m/s² = 117.6 N
Cismin üzerine etki eden kuvvet 117.6 Newton'dur.
```

Model önce formülü ders kitabında doğruladı, sonra işlemi hesap aracına yaptırdı.
İki araç tek turda arka arkaya çağrıldı.

### 7. Araç gerektirmeyen sohbet

```
Siz > Merhaba, bugun nasilsin?

Asistan > Merhaba! Ben bir ders çalışma asistanıyım ve bugün sana yardımcı olmak için
buradayım. Sen nasılsın? Hangi derste yardıma ihtiyacın var?
```

Sistem istemindeki son kural gereği basit sohbette araç çağrılmıyor — gereksiz
vektör araması ve gecikme önleniyor.
