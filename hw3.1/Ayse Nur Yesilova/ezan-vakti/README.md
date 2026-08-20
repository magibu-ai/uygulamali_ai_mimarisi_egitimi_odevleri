# Ezan Vakti

Türkiye için namaz vakitlerini, vakit öncesi hatırlatmaları, kıble yönünü,
Kur'an okuma bağlantılarını ve zikirmatiği tek bir uygulamada sunan Flutter
uygulaması.

## Öne çıkanlar

- Seçilen il ve ilçeye göre günlük vakitler
- Uygulama kapalıyken çalışan vakit ve vakit öncesi hatırlatmaları
- Ana ekranda sıradaki vakit ve kalan süre widget'ı
- Koyu tema, yazı boyutu ve arka plan tercihleri
- Günün ayeti, hadisi, duası ve zikirmatik

## Vakit verisi ve çevrimdışı çalışma

Birincil kaynak, Türkiye için Diyanet hesaplama metodunu destekleyen
[AlAdhan Prayer Times API](https://aladhan.com/prayer-times-api)'dir. Sonuçlar
gün bazında cihazda saklanır. Ağ erişimi yoksa uygulama, MIT lisanslı açık
kaynak [Adhan Dart](https://pub.dev/packages/adhan_dart) kütüphanesiyle cihaz
üzerinde Türkiye metoduna yakın astronomik hesaplama yapar. Çevrimdışı
hesaplama resmi yerel çizelgeden birkaç dakika farklı olabilir; ekranda veri
kaynağı her zaman görünür.

Resmî Diyanet REST API'si başvuru ve erişim onayı gerektirir. Erişim anahtarı
tanımlanmadığı için uygulama bu servise doğrudan bağlanmaz.

## Geliştirme

```bash
flutter pub get
flutter analyze
flutter test
```

## Güvenlik ve yayınlama

Android imzalama bilgileri repoya eklenmez. Yerel `key.properties` dosyası
şu anahtarları içerir: `storePassword`, `keyPassword`, `keyAlias`, `storeFile`.
Bu dosya ve `.jks` anahtarı `.gitignore` kapsamındadır. Yayın anahtarını veya
şifreleri asla kaynak koduna yazmayın.

## İzinler

- Bildirim: vakit ve vakit öncesi hatırlatmalar için
- Kesin alarm: Android'in uygulama kapalıyken zamanında bildirim teslimi için
- İnternet: vakit ve içerik kaynaklarına ulaşmak için

Uygulama konumu istemez; kullanıcı il ve ilçesini kendisi seçer.
