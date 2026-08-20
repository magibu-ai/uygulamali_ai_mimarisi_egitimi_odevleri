import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'package:ezan_vakti/core/prayer_times_service.dart';

void main() {
  setUpAll(() {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Europe/Istanbul'));
  });

  test('Türkiye illerinin çevrimdışı koordinatları bulunur', () {
    expect(TurkeyCityCoordinates.forCity('İstanbul'), isNotNull);
    expect(TurkeyCityCoordinates.forCity('Ankara'), isNotNull);
    expect(TurkeyCityCoordinates.forCity('Bilinmeyen'), isNull);
  });

  test('çevrimdışı hesaplama altı vakti geçerli saat biçiminde döndürür', () {
    final timings =
        PrayerTimesService.calculateOffline('İstanbul', DateTime(2026, 8, 17));

    expect(timings.keys,
        containsAll(['İmsak', 'Güneş', 'Öğle', 'İkindi', 'Akşam', 'Yatsı']));
    expect(timings.values, everyElement(matches(RegExp(r'^\d{2}:\d{2}$'))));
  });
}
