# GökPusula — Yerel LLM Gökyüzü Gözlem Asistanı

Ollama üzerinde yerel çalışan, **tool-calling** yapabilen bir terminal asistanı.
Amatör gökyüzü gözlemcilerine şu gece ne görünür, hava açık mı ve güncel gök
olayları (meteor yağmuru, tutulma, ISS geçişi) hakkında Türkçe rehberlik eder.

> **Mimari:** `malibayram/single_letter_transformers/ollama_asistan` referansından
> uyarlanmıştır. Medikal RAG bileşenleri kaldırılmış; gökyüzüne özel araçlar
> (`goksel_gorunurluk`, `gozlem_kosullari`) eklenmiştir.
> API anahtarı gerektiren hiçbir servis yoktur (Open-Meteo ve ephem anahtarsız çalışır).

---

## Kurulum

```bash
# 1) Ollama kurulu ve çalışıyor olmalı
ollama serve

# 2) Tool-calling yapabilen modeli çek (tercihen):
ollama pull qwen2.5:7b-instruct
# alternatif: ollama pull llama3.1:8b

# 3) Python bağımlılıklarını kur:
pip install -r requirements.txt   # requests>=2.31, ephem>=4.1

# 4) Asistanı başlat:
python chat.py

# Farklı model kullanmak için:
python chat.py --chat-model llama3.1:8b
```

---

## Araçlar

| Araç | Ne Yapar |
|------|----------|
| `goksel_gorunurluk(sehir, tarih?)` | Ay evresi + %, ay doğuş/batış, astronomik karanlık başlangıcı, görünür gezegenler (ephem) |
| `gozlem_kosullari(sehir)` | Anlık bulut oranı, sıcaklık, rüzgar + verdikt |
| `get_weather(sehir)` | Genel hava durumu (sıcaklık, nem, rüzgar, durum kodu) |
| `internet_search(query)` | DuckDuckGo lite + Wikipedia — güncel gök olayları |

---

## Örnek Konuşmalar

### Konuşma 1 — Bu gece Sivas'tan gözlem yapabilir miyim?

```
Siz: Bu gece Sivas'tan gözlem yapabilir miyim?

  🔧 goksel_gorunurluk(sehir='Sivas')
  🔧 gozlem_kosullari(sehir='Sivas')

[goksel_gorunurluk çıktısı]
=== Sivas Gökyüzü Raporu ===
Tarih / Saat: 2026-08-13 21:00 yerel (UTC+3)

🌙 Ay Evresi  : Yeni Ay (%1 aydınlanma)
   Ay Doğuşu : 06:13 (yerel)
   Ay Batışı  : 19:58 (yerel)

🌑 Karanlık Başlangıcı: 21:12 (yerel)

🔭 Görünür Gezegenler (ufkun >10° üzerinde):
   Bu saatte görünür parlak gezegen yok.

💡 Gözlem İpucu: Ufkun 30°+ üzerindeki cisimler en net görünür.

[gozlem_kosullari çıktısı]
Sivas gözlem koşulları:
  Gözlem Uygunluğu : Mükemmel (gökyüzü açık)
  Bulut Oranı      : %0
  Sıcaklık         : 25.2°C
  Rüzgar           : 28.7 km/h

GökPusula: Bu gece Sivas için koşullar harika! Gökyüzü tamamen açık ve
ay yeni ay evresinde olduğundan (%1 aydınlanma) gökyüzü çok karanlık —
derin gökyüzü nesneleri (nebulalar, küme yıldızlar) için ideal.
Astronomik karanlık 21:12'de başlıyor. Sıcaklık 25°C civarında ama
rüzgar biraz var (28.7 km/h); teleskopunuzu sabit bir zemine oturtun.
```

---

### Konuşma 2 — Bu ay meteor yağmuru var mı?

```
Siz: Bu ay meteor yağmuru var mı?

  🔧 internet_search(query='2026 meteor yagmuru takvimi')

[internet_search gerçek çıktısı]
Arama sonuçları (2026 meteor yagmuru takvimi):

İşte 12-13 Ağustos 2026 gökyüzü takvimi, tutulmanın görünürlük alanı ve
meteor yağmurunun zirve saatlerine ilişkin merak edilen ayrıntılar.

2026 meteor yağmurları takvimi rehberiyle Quadrantidler, Lyridler, Perseidler,
Leonidler ve Geminidlerin tarihlerini, en iyi gözlem saatlerini ve
Türkiye&#x27;den izleme ipuçlarını keşfedin.

Perseid meteor yağmuru canlı izleme yerleri ve noktaları 2026 Ağustos ayının
gelmesiyle beraber merak konusu oldu. Gökyüzü tutkunları, yılın en etkileyici
doğa olaylarından biri olarak gösterilen Perseid Meteor Yağmuru için geri
sayım başladı.

2026 meteor yağmuru ne zaman? Perseid meteor yağmuru 12-13 Ağustos gecesi
zirveye çıkacak. Türkiye&#x27;den izleme saati, yönü ve tüm detaylar.

Meteor yağmuru ne zaman, hangi gün sorusu, doğa olayları tutkunları
tarafından sorgulanıyor. Perseid meteor yağmuru canlı izleme yerleri ve
noktaları 2026 Ağustos ayının gelmesiyle ...

GökPusula: Evet! Ağustos 2026'nın en büyük gök olayı Perseid meteor
yağmuruydu, zirve 12-13 Ağustos gecesiydi. Bunun dışında yıl genelinde
Quadrantidler (Ocak), Lyridler (Nisan), Leonidler (Kasım) ve Geminidler
(Aralık) takvimde yer alıyor. Gözlemlemek istediğiniz etkinlik için tarih
verirseniz o geceye özel gökyüzü raporu çıkarabilirim.
```

---

### Konuşma 3 — 15 Ağustos'ta İzmir'den Satürn görünür mü?

```
Siz: 15 Ağustos'ta İzmir'den Satürn görünür mü?

  🔧 goksel_gorunurluk(sehir='İzmir', tarih='2026-08-15')

[goksel_gorunurluk çıktısı]
=== İzmir Gökyüzü Raporu ===
Tarih / Saat: 2026-08-15 21:00 yerel (UTC+3)

🌙 Ay Evresi  : Büyüyen Hilal (%11 aydınlanma)
   Ay Doğuşu : 09:17 (yerel)
   Ay Batışı  : 21:27 (yerel)

🌑 Karanlık Başlangıcı: 21:43 (yerel)

🔭 Görünür Gezegenler (ufkun >10° üzerinde):
   Bu saatte görünür parlak gezegen yok.

💡 Gözlem İpucu: Ufkun 30°+ üzerindeki cisimler en net görünür.

GökPusula: 15 Ağustos 2026 saat 21:00'de İzmir'den Satürn, hesaplanan
verilere göre ufkun 10°'sinin altında kaldığından görünür değil.
Gece ilerledikçe yükselebilir; gözlemi biraz daha geç saate (23:00 sonrası)
almayı deneyebilirsiniz. Ay ince bir büyüyen hilal (%11) olduğundan
gökyüzü karanlığını engellemiyor — bu olumlu.
```

---

### Konuşma 4 — 26 Ekim'de Bursa'da ay dolunay mı, gözlem bozar mı?

```
Siz: 26 Ekim'de Bursa'da ay dolunay mı, gözlem bozar mı?

  🔧 goksel_gorunurluk(sehir='Bursa', tarih='2026-10-26')

[goksel_gorunurluk gerçek çıktısı]
=== Bursa Gökyüzü Raporu ===
Tarih / Saat: 2026-10-26 21:00 yerel (UTC+3)

🌙 Ay Evresi  : Dolunay (%99 aydınlanma)
   ⚠️  Ay parlak, sönük cisimleri yıkar; Ay batışını beklemek daha iyi.
   Ay Doğuşu : 17:57 (yerel)
   Ay Batışı  : 07:40 (yerel)

🌑 Karanlık Başlangıcı: 19:39 (yerel)

🔭 Görünür Gezegenler (ufkun >10° üzerinde):
   Satürn: ufkun ~39° üzerinde, Güneydoğu

💡 Gözlem İpucu: Ufkun 30°+ üzerindeki cisimler en net görünür.
   Işık kirliliğinden uzak, karanlık bir alana gidin.

GökPusula: 26 Ekim'de Bursa'da ay gerçekten dolunay (%99 aydınlanma) ve
gece boyunca gökyüzünde kalıyor — batışı sabah 07:40'ta. Bu kadar parlak
bir ay nebula ve gökadalar için ciddi sorun yaratır. Olumlu haber: Satürn
bu gece güneydoğuda ufkun 39° üzerinde ve gayet iyi konumda; parlak
gezegenler ay ışığından çok etkilenmez. Derin gökyüzü nesneleri için
dolunaydan uzak bir geceyi beklemenizi öneririm.
```

---

## Dosya Yapısı

```
gokpusula/
├── ollama_client.py   # Ollama /api/chat sarmalayıcı (embed'siz)
├── tools.py           # 4 araç + TOOLS + TOOL_SCHEMAS
├── chat.py            # Terminal döngüsü + SYSTEM_PROMPT
├── requirements.txt   # requests, ephem
└── README.md
```

## Gereksinimler

- Python 3.9+
- [Ollama](https://ollama.com/) kurulu ve çalışıyor (`ollama serve`)
- `qwen2.5:7b-instruct` veya `llama3.1:8b` modeli indirilmiş
