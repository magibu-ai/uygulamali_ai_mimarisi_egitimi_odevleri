import 'dart:convert';

import 'package:adhan_dart/adhan_dart.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/timezone.dart' as tz;

enum PrayerTimesSource { alAdhan, cache, offlineCalculation }

class PrayerTimesResult {
  const PrayerTimesResult({
    required this.timings,
    required this.source,
    required this.fetchedAt,
  });

  final Map<String, String> timings;
  final PrayerTimesSource source;
  final DateTime fetchedAt;
}

/// Retrieves Diyanet-method timings from AlAdhan and falls back to an on-device,
/// open-source astronomical calculation when the network is unavailable.
class PrayerTimesService {
  PrayerTimesService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  static const _cachePrefix = 'prayer_times_v2_';

  Future<PrayerTimesResult> getToday({
    required String city,
    required String district,
    DateTime? now,
  }) async {
    final date = now ?? DateTime.now();
    final cacheKey = '$_cachePrefix${city}_$district';

    try {
      final uri = Uri.https('api.aladhan.com', '/v1/timingsByCity', {
        'city': city,
        'country': 'Turkey',
        'method': '13',
      });
      final response =
          await _client.get(uri).timeout(const Duration(seconds: 8));
      final timings = _parseAlAdhan(response);
      if (timings != null) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(
            cacheKey,
            jsonEncode({
              'date': DateFormat('yyyy-MM-dd').format(date),
              'savedAt': DateTime.now().toIso8601String(),
              'timings': timings,
            }));
        return PrayerTimesResult(
          timings: timings,
          source: PrayerTimesSource.alAdhan,
          fetchedAt: DateTime.now(),
        );
      }
    } catch (_) {
      // The cache and offline calculation below deliberately keep the app useful.
    }

    final cached = await _readCache(cacheKey, date);
    if (cached != null) return cached;

    return PrayerTimesResult(
      timings: calculateOffline(city, date),
      source: PrayerTimesSource.offlineCalculation,
      fetchedAt: DateTime.now(),
    );
  }

  Map<String, String>? _parseAlAdhan(http.Response response) {
    if (response.statusCode != 200) return null;
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final data = payload['data'] as Map<String, dynamic>?;
    final raw = data?['timings'] as Map<String, dynamic>?;
    if (payload['code'] != 200 || raw == null) return null;
    final values = <String, String>{
      'İmsak': _cleanTime(raw['Fajr']),
      'Güneş': _cleanTime(raw['Sunrise']),
      'Öğle': _cleanTime(raw['Dhuhr']),
      'İkindi': _cleanTime(raw['Asr']),
      'Akşam': _cleanTime(raw['Maghrib']),
      'Yatsı': _cleanTime(raw['Isha']),
    };
    return values.values.any((value) => value == '--:--') ? null : values;
  }

  String _cleanTime(Object? value) {
    final match = RegExp(r'^\d{1,2}:\d{2}').firstMatch(value?.toString() ?? '');
    return match?.group(0)?.padLeft(5, '0') ?? '--:--';
  }

  Future<PrayerTimesResult?> _readCache(String key, DateTime date) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null) return null;
    try {
      final cache = jsonDecode(raw) as Map<String, dynamic>;
      if (cache['date'] != DateFormat('yyyy-MM-dd').format(date)) return null;
      final values = (cache['timings'] as Map<String, dynamic>).map(
        (key, value) => MapEntry(key, value.toString()),
      );
      return PrayerTimesResult(
        timings: values,
        source: PrayerTimesSource.cache,
        fetchedAt: DateTime.parse(cache['savedAt'] as String),
      );
    } on FormatException {
      return null;
    }
  }

  static Map<String, String> calculateOffline(String city, DateTime date) {
    final coordinates = TurkeyCityCoordinates.forCity(city);
    if (coordinates == null) {
      throw StateError('Bu şehir için çevrimdışı koordinat bulunamadı: $city');
    }
    final parameters = CalculationMethodParameters.turkiye()
      ..madhab = Madhab.hanafi;
    final times = PrayerTimes(
      coordinates: coordinates,
      date: date,
      calculationParameters: parameters,
    );
    final location = tz.getLocation('Europe/Istanbul');
    String format(DateTime value) =>
        DateFormat('HH:mm').format(tz.TZDateTime.from(value, location));
    return {
      'İmsak': format(times.fajr),
      'Güneş': format(times.sunrise),
      'Öğle': format(times.dhuhr),
      'İkindi': format(times.asr),
      'Akşam': format(times.maghrib),
      'Yatsı': format(times.isha),
    };
  }
}

class TurkeyCityCoordinates {
  static const _coordinates = <String, Coordinates>{
    'Adana': Coordinates(37.0000, 35.3213),
    'Adıyaman': Coordinates(37.7648, 38.2786),
    'Afyonkarahisar': Coordinates(38.7569, 30.5387),
    'Ağrı': Coordinates(39.7191, 43.0503),
    'Amasya': Coordinates(40.6499, 35.8353),
    'Ankara': Coordinates(39.9334, 32.8597),
    'Antalya': Coordinates(36.8969, 30.7133),
    'Artvin': Coordinates(41.1828, 41.8183),
    'Aydın': Coordinates(37.8560, 27.8416),
    'Balıkesir': Coordinates(39.6484, 27.8826),
    'Bilecik': Coordinates(40.1501, 29.9833),
    'Bingöl': Coordinates(38.8847, 40.4939),
    'Bitlis': Coordinates(38.4006, 42.1095),
    'Bolu': Coordinates(40.7395, 31.6116),
    'Burdur': Coordinates(37.7203, 30.2908),
    'Bursa': Coordinates(40.1950, 29.0600),
    'Çanakkale': Coordinates(40.1553, 26.4142),
    'Çankırı': Coordinates(40.6013, 33.6134),
    'Çorum': Coordinates(40.5506, 34.9556),
    'Denizli': Coordinates(37.7765, 29.0864),
    'Diyarbakır': Coordinates(37.9144, 40.2306),
    'Edirne': Coordinates(41.6818, 26.5623),
    'Elazığ': Coordinates(38.6748, 39.2225),
    'Erzincan': Coordinates(39.7500, 39.5000),
    'Erzurum': Coordinates(39.9043, 41.2679),
    'Eskişehir': Coordinates(39.7667, 30.5256),
    'Gaziantep': Coordinates(37.0662, 37.3833),
    'Giresun': Coordinates(40.9128, 38.3895),
    'Gümüşhane': Coordinates(40.4603, 39.4814),
    'Hakkâri': Coordinates(37.5744, 43.7408),
    'Hatay': Coordinates(36.2021, 36.1603),
    'Isparta': Coordinates(37.7648, 30.5566),
    'Mersin': Coordinates(36.8121, 34.6415),
    'İstanbul': Coordinates(41.0082, 28.9784),
    'İzmir': Coordinates(38.4237, 27.1428),
    'Kars': Coordinates(40.6013, 43.0975),
    'Kastamonu': Coordinates(41.3887, 33.7827),
    'Kayseri': Coordinates(38.7225, 35.4875),
    'Kırklareli': Coordinates(41.7351, 27.2242),
    'Kırşehir': Coordinates(39.1425, 34.1709),
    'Kocaeli': Coordinates(40.8533, 29.8815),
    'Konya': Coordinates(37.8746, 32.4932),
    'Kütahya': Coordinates(39.4199, 29.9857),
    'Malatya': Coordinates(38.3552, 38.3095),
    'Manisa': Coordinates(38.6191, 27.4289),
    'Kahramanmaraş': Coordinates(37.5858, 36.9371),
    'Mardin': Coordinates(37.3122, 40.7351),
    'Muğla': Coordinates(37.2153, 28.3636),
    'Muş': Coordinates(38.9462, 41.7539),
    'Nevşehir': Coordinates(38.6244, 34.7144),
    'Niğde': Coordinates(37.9667, 34.6833),
    'Ordu': Coordinates(40.9862, 37.8797),
    'Rize': Coordinates(41.0201, 40.5234),
    'Sakarya': Coordinates(40.7569, 30.3781),
    'Samsun': Coordinates(41.2867, 36.3300),
    'Siirt': Coordinates(37.9333, 41.9500),
    'Sinop': Coordinates(42.0231, 35.1531),
    'Sivas': Coordinates(39.7477, 37.0179),
    'Tekirdağ': Coordinates(40.9781, 27.5117),
    'Tokat': Coordinates(40.3167, 36.5500),
    'Trabzon': Coordinates(41.0015, 39.7178),
    'Tunceli': Coordinates(39.1079, 39.5401),
    'Şanlıurfa': Coordinates(37.1674, 38.7955),
    'Uşak': Coordinates(38.6823, 29.4082),
    'Van': Coordinates(38.4891, 43.4089),
    'Yozgat': Coordinates(39.8181, 34.8147),
    'Zonguldak': Coordinates(41.4564, 31.7987),
    'Aksaray': Coordinates(38.3687, 34.0370),
    'Bayburt': Coordinates(40.2552, 40.2249),
    'Karaman': Coordinates(37.1759, 33.2287),
    'Kırıkkale': Coordinates(39.8468, 33.5153),
    'Batman': Coordinates(37.8812, 41.1351),
    'Şırnak': Coordinates(37.5164, 42.4611),
    'Bartın': Coordinates(41.6344, 32.3375),
    'Ardahan': Coordinates(41.1105, 42.7022),
    'Iğdır': Coordinates(39.9237, 44.0450),
    'Yalova': Coordinates(40.6500, 29.2667),
    'Karabük': Coordinates(41.2061, 32.6204),
    'Kilis': Coordinates(36.7184, 37.1212),
    'Osmaniye': Coordinates(37.0742, 36.2478),
    'Düzce': Coordinates(40.8438, 31.1565),
  };

  static Coordinates? forCity(String city) => _coordinates[city];
}
