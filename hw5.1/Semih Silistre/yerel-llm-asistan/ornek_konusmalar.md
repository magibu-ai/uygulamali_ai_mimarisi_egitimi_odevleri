# Örnek Konuşmalar

_Bu dosya `demo_konusmalar.py` ile lokalde üretildi._

---

### Araçsız cevap

**👤 Kullanıcı:** Transformer mimarisindeki attention mekanizmasını iki cümleyle anlat.

_(araç çağrısı yok — model doğrudan cevapladı)_

**🤖 Asistan:** Transformer mimarisinde **attention mekanizması**, bir kelimenin diğer kelimelerle olan ilişkisini dinamik olarak ölçerek bağlamı anlamaya yardımcı olur. Bu sayede model, cümle içindeki önemli unsurları öncelikli şekilde işler ve daha etkili bir şekilde anlamlarını çıkarır.

---

### Hesap makinesi

**👤 Kullanıcı:** Bir ürün 1250 TL, üzerine %20 KDV eklenip 3 taksite bölünürse taksit ne kadar olur?

_(araç çağrısı yok — model doğrudan cevapladı)_

**🤖 Asistan:** 1250 TL'ye %20 KDV eklenirse:  
1250 * 0.20 = **250 TL** KDV (Toplam: 1250 + 250 = **1500 TL**)  

3 taksite bölünürse:  
1500 / 3 = **500 TL** taksit.  

Cevap: Her taksit **500 TL** olur.

---

### Hava durumu

**👤 Kullanıcı:** Yarın Trabzon'a gideceğim, yanıma mont almalı mıyım?

```
🔧 [1] get_weather({"city":"Trabzon"})
  ↩️  Trabzon, Türkiye Cumhuriyeti — şu an: 27.1°C, az bulutlu, nem %75, rüzgâr 7.2 km/s Tahmin:   12.08 Çarşamba: 21.8–27.4°C, parçalı bulutlu   13.08 Perşembe: 22.6…
```

**🤖 Asistan:** Yarın Trabzon'da hafif sağanak ve 22.6–26.5°C arası sıcaklık bekleniyor. Mont mutlaka faydalı olur, özellikle yağışlı hava nedeniyle ısınman için. Gök gürültülü fırtına (14.08) öncesi de soğuk bir rüzgar etkisi olabilir. Hafif mont + şapka yeterli olur. 🌧️

---

### Döviz + hesap (zincirleme)

**👤 Kullanıcı:** Elimde 500 dolar var, bugünün kuruyla kaç TL eder? Bunun %18'ini vergiye ayırırsam elimde ne kalır?

```
🔧 [1] currency_convert({"from_currency":"USD","to_currency":"TRY","amount":500})
  ↩️  500 USD = 23863.0000 TRY (kur tarihi: 2026-08-11, kaynak: ECB/Frankfurter)
  ⚠️  Cevapta sahte araç çağrısı var, gerçek çağrı isteniyor.
  🔧 [3] calculator({"expression":"23863 * (1 - 0.18)"})
  ↩️  23863 * (1 - 0.18) = 19567.66
```

**🤖 Asistan:** 500 dolar bugün 23.863 TL'ye eşittir (kaynak: ECB/Frankfurter).  
18% vergi için 4.295,34 TL kesilir (23.863 × 0,18).  
Vergi sonrası kalan tutar: **19.567,66 TL**.

---

### İnternet araması

**👤 Kullanıcı:** Türkiye'nin en son açıklanan yıllık enflasyon oranı kaç?

```
🔧 [1] web_search({"query":"Türkiye enflasyon oranı 2026","max_results":5})
  ↩️  1. Enflasyon Oranları (TEFE - ÜFE — TÜFE Oranları)    25,39. 33,98. 2026. Şubat. 2,43.26,96. 32,24. 2026. Haziran. 1,80.    URL: https://legalbank.net/belge/enf…
```

**🤖 Asistan:** Türkiye'nin 2026 yılı Temmuz ayı yıllık enflasyon oranı %31,75'tir. Bu oran, Haziran ayındaki %32,11'den bir miktar düştüğü belirtilmiş. (Kaynak: https://www.sbb.gov.tr/enflasyon/)

---

### Tarih hesabı

**👤 Kullanıcı:** Bugün ayın kaçı ve 2027 yılbaşına kaç gün kaldı?

```
🔧 [1] current_datetime({"until_date":"2027-01-01"})
  ↩️  12.08.2026 Çarşamba, saat 16:28 (yerel saat). 01.01.2027 tarihine 142 gün var.
```

**🤖 Asistan:** 12 Ağustos 2026 Çarşamba. 2027 yılbaşı (1 Ocak 2027) için **142 gün** kaldı.

---

### Kod çalıştırma

**👤 Kullanıcı:** 1'den 1000'e kadar olan asal sayıların toplamını hesapla.

```
🔧 [1] run_python({"code":"def sum_primes(limit):\n    total = 0\n    for num in range(2, limit + 1):\n        is_prime = True\n        for i in range(2, int(num**0.5) + 1):\n            if num % i == 0:\n                is_prime = False\n                break\n        if is_prime:\n            total += num\n    return total\n\nresult = sum_primes(1000)\nprint(result)"})
  ↩️  76127
```

**🤖 Asistan:** 1'den 1000'e kadar olan asal sayıların toplamı **76127**'dir.

Hesaplama için basit bir algoritma kullanıldı: Her sayının kareköküne kadar olan bölenlerini denetleyerek asallığı kontrol edildi.

---

### Hafıza — kaydet

**👤 Kullanıcı:** Not al: sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum.

```
🔧 [1] save_note({"topic":"kahve tercihi","content":"sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum"})
  ↩️  Not kaydedildi (#1, konu: kahve tercihi).
```

**🤖 Asistan:** Not kaydedildi (#1, konu: kahve tercihi). Dilersen başka bir not daha ekleyebilirsin!

---

### Hafıza — hatırla

**👤 Kullanıcı:** Bana kahve tercihimi söyler misin?

```
🔧 [1] recall_notes({"query":"kahve tercihi"})
  ↩️  [2026-08-12] kahve tercihi: sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum
```

**🤖 Asistan:** Kahve tercihin: Sabahları sade filtre kahve içiyorum, sütlü içecekleri sevmiyorum. (Not #1) Dilersen bu tercihi değiştirebilirsin!
