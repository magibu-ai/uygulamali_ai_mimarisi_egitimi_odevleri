import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'dart:typed_data';
import 'dart:ui' show ImageFilter;
import 'package:intl/intl.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:webview_flutter/webview_flutter.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;
import 'package:share_plus/share_plus.dart';
import 'core/home_widget_service.dart';
import 'core/prayer_notification_service.dart';
import 'core/prayer_times_service.dart';

final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin =
    FlutterLocalNotificationsPlugin();

// ==================== KUSURSUZ VE CANLI iOS TEMA MOTORU ====================
// ==================== KUSURSUZ VE CANLI iOS TEMA MOTORU ====================
enum AppThemeMode {
  emerald, // Zümrüt Yeşili (Nebevî Yeşil)
  rose, // Gül Pembe (Gül-i Muhammedi)
  navy, // Safir Gece Mavisi
  obsidian, // Obsidian Altın (Kâbe Siyah & Altın)
  amber, // Kehribar & Bal
  purple, // Mor & Leylak
  teal, // Kubbe Turkuazı
  ruby, // Yakut Kırmızı
  olive, // Kutsal Zeytin
  saffron, // Manevi Safran
  sky, // Semavi Gök Mavisi
  pearl, // İnci & Gümüş
  lotus, // Nilüfer Bahçesi (Özel Palet 1)
  vanilla, // Vanilya & Gül (Özel Palet 2)
  sakura, // Sakura Gecesi (Özel Palet 3)
  fig, // İncir & Seramik (Özel Palet 4)
}

class AppThemeData {
  final String name;
  final Color primary;
  final Color secondary;
  final Color accent;
  final Color backgroundLight;
  final Color backgroundDark;
  final Color cardLight;
  final Color cardDark;
  final Color textLight;
  final Color textDark;
  final List<Color> bgGradientLight;
  final List<Color> bgGradientDark;
  final List<Color> cardGradientLight;
  final List<Color> cardGradientDark;

  const AppThemeData({
    required this.name,
    required this.primary,
    required this.secondary,
    required this.accent,
    required this.backgroundLight,
    required this.backgroundDark,
    required this.cardLight,
    required this.cardDark,
    required this.textLight,
    required this.textDark,
    required this.bgGradientLight,
    required this.bgGradientDark,
    required this.cardGradientLight,
    required this.cardGradientDark,
  });

  static AppThemeData getTheme(AppThemeMode mode) {
    switch (mode) {
      case AppThemeMode.emerald:
        return const AppThemeData(
          name: "Zümrüt (Nebevî Yeşil) 🌿",
          primary: Color(0xFF059669),
          secondary: Color(0xFF10B981),
          accent: Color(0xFFECFDF5),
          backgroundLight: Color(0xFFECFDF5),
          backgroundDark: Color(0xFF022C22),
          cardLight: Color(0xFFD1FAE5),
          cardDark: Color(0xFF064E3B),
          textLight: Color(0xFF065F46),
          textDark: Color(0xFFA7F3D0),
          bgGradientLight: [
            Color(0xFFECFDF5),
            Color(0xFFA7F3D0),
            Color(0xFF6EE7B7)
          ],
          bgGradientDark: [
            Color(0xFF022C22),
            Color(0xFF064E3B),
            Color(0xFF021B15)
          ],
          cardGradientLight: [Color(0xFFD1FAE5), Color(0xFFA7F3D0)],
          cardGradientDark: [Color(0xFF064E3B), Color(0xFF022C22)],
        );
      case AppThemeMode.rose:
        return const AppThemeData(
          name: "Gül Pembe 🌸",
          primary: Color(0xFFE11D48),
          secondary: Color(0xFFFB7185),
          accent: Color(0xFFFFF1F2),
          backgroundLight: Color(0xFFFFF1F2),
          backgroundDark: Color(0xFF2A040D),
          cardLight: Color(0xFFFFE4E6),
          cardDark: Color(0xFF4C081A),
          textLight: Color(0xFF9F1239),
          textDark: Color(0xFFFECDD3),
          bgGradientLight: [
            Color(0xFFFFF1F2),
            Color(0xFFFFD6E0),
            Color(0xFFFFB3C6)
          ],
          bgGradientDark: [
            Color(0xFF2A040D),
            Color(0xFF4A0818),
            Color(0xFF1F0208)
          ],
          cardGradientLight: [Color(0xFFFFE4E6), Color(0xFFFFC2D1)],
          cardGradientDark: [Color(0xFF5C0A21), Color(0xFF380514)],
        );
      case AppThemeMode.navy:
        return const AppThemeData(
          name: "Safir Gece Mavisi 🌌",
          primary: Color(0xFF1D4ED8),
          secondary: Color(0xFF3B82F6),
          accent: Color(0xFFEFF6FF),
          backgroundLight: Color(0xFFEFF6FF),
          backgroundDark: Color(0xFF0B132B),
          cardLight: Color(0xFFDBEAFE),
          cardDark: Color(0xFF1C2541),
          textLight: Color(0xFF1E40AF),
          textDark: Color(0xFFBFDBFE),
          bgGradientLight: [
            Color(0xFFEFF6FF),
            Color(0xFFBFDBFE),
            Color(0xFF93C5FD)
          ],
          bgGradientDark: [
            Color(0xFF0B132B),
            Color(0xFF1C2541),
            Color(0xFF060B18)
          ],
          cardGradientLight: [Color(0xFFDBEAFE), Color(0xFFBFDBFE)],
          cardGradientDark: [Color(0xFF1C2541), Color(0xFF0B132B)],
        );
      case AppThemeMode.obsidian:
        return const AppThemeData(
          name: "Obsidian Altın (Kâbe) 🖤",
          primary: Color(0xFFD97706),
          secondary: Color(0xFFFACC15),
          accent: Color(0xFFFEFCE8),
          backgroundLight: Color(0xFFFEFCE8),
          backgroundDark: Color(0xFF09090B),
          cardLight: Color(0xFFFEF08A),
          cardDark: Color(0xFF18181B),
          textLight: Color(0xFF854D0E),
          textDark: Color(0xFFFDE047),
          bgGradientLight: [
            Color(0xFFFEFCE8),
            Color(0xFFFEF08A),
            Color(0xFFFDE047)
          ],
          bgGradientDark: [
            Color(0xFF09090B),
            Color(0xFF18181B),
            Color(0xFF000000)
          ],
          cardGradientLight: [Color(0xFFFEF08A), Color(0xFFFDE047)],
          cardGradientDark: [Color(0xFF27272A), Color(0xFF18181B)],
        );
      case AppThemeMode.amber:
        return const AppThemeData(
          name: "Kehribar & Bal 🍯",
          primary: Color(0xFFD97706),
          secondary: Color(0xFFF59E0B),
          accent: Color(0xFFFFFBEB),
          backgroundLight: Color(0xFFFFFBEB),
          backgroundDark: Color(0xFF1C1917),
          cardLight: Color(0xFFFEF3C7),
          cardDark: Color(0xFF292524),
          textLight: Color(0xFF92400E),
          textDark: Color(0xFFFDE68A),
          bgGradientLight: [
            Color(0xFFFFFBEB),
            Color(0xFFFDE68A),
            Color(0xFFFCD34D)
          ],
          bgGradientDark: [
            Color(0xFF1C1917),
            Color(0xFF292524),
            Color(0xFF0C0A09)
          ],
          cardGradientLight: [Color(0xFFFEF3C7), Color(0xFFFDE68A)],
          cardGradientDark: [Color(0xFF44403C), Color(0xFF292524)],
        );
      case AppThemeMode.purple:
        return const AppThemeData(
          name: "Mor & Leylak 💜",
          primary: Color(0xFF7E22CE),
          secondary: Color(0xFFA855F7),
          accent: Color(0xFFFAF5FF),
          backgroundLight: Color(0xFFFAF5FF),
          backgroundDark: Color(0xFF170624),
          cardLight: Color(0xFFF3E8FF),
          cardDark: Color(0xFF2D0945),
          textLight: Color(0xFF6B21A8),
          textDark: Color(0xFFE9D5FF),
          bgGradientLight: [
            Color(0xFFFAF5FF),
            Color(0xFFE9D5FF),
            Color(0xFFD8B4FE)
          ],
          bgGradientDark: [
            Color(0xFF170624),
            Color(0xFF2D0945),
            Color(0xFF0E0317)
          ],
          cardGradientLight: [Color(0xFFF3E8FF), Color(0xFFE9D5FF)],
          cardGradientDark: [Color(0xFF3B0C5A), Color(0xFF2D0945)],
        );
      case AppThemeMode.teal:
        return const AppThemeData(
          name: "Kubbe Turkuazı 🕌",
          primary: Color(0xFF0D9488),
          secondary: Color(0xFF14B8A6),
          accent: Color(0xFFF0FDFA),
          backgroundLight: Color(0xFFF0FDFA),
          backgroundDark: Color(0xFF042F2C),
          cardLight: Color(0xFFCCFBF1),
          cardDark: Color(0xFF0D4744),
          textLight: Color(0xFF115E59),
          textDark: Color(0xFF99F6E4),
          bgGradientLight: [
            Color(0xFFF0FDFA),
            Color(0xFF99F6E4),
            Color(0xFF5EEAD4)
          ],
          bgGradientDark: [
            Color(0xFF042F2C),
            Color(0xFF0D4744),
            Color(0xFF021E1C)
          ],
          cardGradientLight: [Color(0xFFCCFBF1), Color(0xFF99F6E4)],
          cardGradientDark: [Color(0xFF115E59), Color(0xFF0D4744)],
        );
      case AppThemeMode.ruby:
        return const AppThemeData(
          name: "Yakut Kırmızı 🍷",
          primary: Color(0xFFBE123C),
          secondary: Color(0xFFFB7185),
          accent: Color(0xFFFFF1F2),
          backgroundLight: Color(0xFFFFF1F2),
          backgroundDark: Color(0xFF1F040A),
          cardLight: Color(0xFFFFE4E6),
          cardDark: Color(0xFF380714),
          textLight: Color(0xFF9F1239),
          textDark: Color(0xFFFECDD3),
          bgGradientLight: [
            Color(0xFFFFF1F2),
            Color(0xFFFECDD3),
            Color(0xFFFDA4AF)
          ],
          bgGradientDark: [
            Color(0xFF1F040A),
            Color(0xFF380714),
            Color(0xFF120206)
          ],
          cardGradientLight: [Color(0xFFFFE4E6), Color(0xFFFECDD3)],
          cardGradientDark: [Color(0xFF4C091C), Color(0xFF380714)],
        );
      case AppThemeMode.olive:
        return const AppThemeData(
          name: "Kutsal Zeytin 🫒",
          primary: Color(0xFF65A30D),
          secondary: Color(0xFF84CC16),
          accent: Color(0xFFF7FEE7),
          backgroundLight: Color(0xFFF7FEE7),
          backgroundDark: Color(0xFF1A2E05),
          cardLight: Color(0xFFECFCCB),
          cardDark: Color(0xFF2C4C0B),
          textLight: Color(0xFF3F6212),
          textDark: Color(0xFFD9F99D),
          bgGradientLight: [
            Color(0xFFF7FEE7),
            Color(0xFFD9F99D),
            Color(0xFFA3E635)
          ],
          bgGradientDark: [
            Color(0xFF1A2E05),
            Color(0xFF2C4C0B),
            Color(0xFF0F1B03)
          ],
          cardGradientLight: [Color(0xFFECFCCB), Color(0xFFD9F99D)],
          cardGradientDark: [Color(0xFF365E0D), Color(0xFF2C4C0B)],
        );
      case AppThemeMode.saffron:
        return const AppThemeData(
          name: "Manevi Safran 🍊",
          primary: Color(0xFFEA580C),
          secondary: Color(0xFFF97316),
          accent: Color(0xFFFFF7ED),
          backgroundLight: Color(0xFFFFF7ED),
          backgroundDark: Color(0xFF2C0B02),
          cardLight: Color(0xFFFFEDD5),
          cardDark: Color(0xFF4A1505),
          textLight: Color(0xFF9A3412),
          textDark: Color(0xFFFED7AA),
          bgGradientLight: [
            Color(0xFFFFF7ED),
            Color(0xFFFED7AA),
            Color(0xFFFDBA74)
          ],
          bgGradientDark: [
            Color(0xFF2C0B02),
            Color(0xFF4A1505),
            Color(0xFF1A0501)
          ],
          cardGradientLight: [Color(0xFFFFEDD5), Color(0xFFFED7AA)],
          cardGradientDark: [Color(0xFF5C1B07), Color(0xFF4A1505)],
        );
      case AppThemeMode.sky:
        return const AppThemeData(
          name: "Semavi Gök Mavisi 💎",
          primary: Color(0xFF0284C7),
          secondary: Color(0xFF38BDF8),
          accent: Color(0xFFF0F9FF),
          backgroundLight: Color(0xFFF0F9FF),
          backgroundDark: Color(0xFF032B45),
          cardLight: Color(0xFFE0F2FE),
          cardDark: Color(0xFF07456F),
          textLight: Color(0xFF075985),
          textDark: Color(0xFFBAE6FD),
          bgGradientLight: [
            Color(0xFFF0F9FF),
            Color(0xFFBAE6FD),
            Color(0xFF7DD3FC)
          ],
          bgGradientDark: [
            Color(0xFF032B45),
            Color(0xFF07456F),
            Color(0xFF01192A)
          ],
          cardGradientLight: [Color(0xFFE0F2FE), Color(0xFFBAE6FD)],
          cardGradientDark: [Color(0xFF09568B), Color(0xFF07456F)],
        );
      case AppThemeMode.pearl:
        return const AppThemeData(
          name: "İnci & Gümüş 🤍",
          primary: Color(0xFF475569),
          secondary: Color(0xFF64748B),
          accent: Color(0xFFF8FAFC),
          backgroundLight: Color(0xFFF8FAFC),
          backgroundDark: Color(0xFF0F172A),
          cardLight: Color(0xFFF1F5F9),
          cardDark: Color(0xFF1E293B),
          textLight: Color(0xFF334155),
          textDark: Color(0xFFCBD5E1),
          bgGradientLight: [
            Color(0xFFF8FAFC),
            Color(0xFFE2E8F0),
            Color(0xFFCBD5E1)
          ],
          bgGradientDark: [
            Color(0xFF0F172A),
            Color(0xFF1E293B),
            Color(0xFF080D1A)
          ],
          cardGradientLight: [Color(0xFFF1F5F9), Color(0xFFE2E8F0)],
          cardGradientDark: [Color(0xFF334155), Color(0xFF1E293B)],
        );
      case AppThemeMode.lotus:
        return const AppThemeData(
          name: "Nilüfer Bahçesi 🪷",
          primary: Color(0xFF105666),
          secondary: Color(0xFF839958),
          accent: Color(0xFFF7F4D5),
          backgroundLight: Color(0xFFF7F4D5),
          backgroundDark: Color(0xFF0A3323),
          cardLight: Color(0xFFEBE7C0),
          cardDark: Color(0xFF164936),
          textLight: Color(0xFF0A3323),
          textDark: Color(0xFFF7F4D5),
          bgGradientLight: [
            Color(0xFFF7F4D5),
            Color(0xFFD3968C),
            Color(0xFF839958)
          ],
          bgGradientDark: [
            Color(0xFF0A3323),
            Color(0xFF105666),
            Color(0xFF051A12)
          ],
          cardGradientLight: [Color(0xFFEBE7C0), Color(0xFFD3968C)],
          cardGradientDark: [Color(0xFF164936), Color(0xFF105666)],
        );
      case AppThemeMode.vanilla:
        return const AppThemeData(
          name: "Vanilya & Gül 🍨",
          primary: Color(0xFFB46A72),
          secondary: Color(0xFFA8B58A),
          accent: Color(0xFFFFF7E6),
          backgroundLight: Color(0xFFFFF7E6),
          backgroundDark: Color(0xFF2D3A47),
          cardLight: Color(0xFFF7C8D3),
          cardDark: Color(0xFF3E4D5E),
          textLight: Color(0xFF733C43),
          textDark: Color(0xFFFFF7E6),
          bgGradientLight: [
            Color(0xFFFFF7E6),
            Color(0xFFF7C8D3),
            Color(0xFFA9B7C6)
          ],
          bgGradientDark: [
            Color(0xFF2D3A47),
            Color(0xFF3E4D5E),
            Color(0xFF1A242E)
          ],
          cardGradientLight: [Color(0xFFF7C8D3), Color(0xFFA9B7C6)],
          cardGradientDark: [Color(0xFF3E4D5E), Color(0xFF2D3A47)],
        );
      case AppThemeMode.sakura:
        return const AppThemeData(
          name: "Sakura Gecesi 🌸",
          primary: Color(0xFF806C79),
          secondary: Color(0xFFC1A0AC),
          accent: Color(0xFFF0D9E4),
          backgroundLight: Color(0xFFF0D9E4),
          backgroundDark: Color(0xFF16131F),
          cardLight: Color(0xFFE0C4D0),
          cardDark: Color(0xFF2D2536),
          textLight: Color(0xFF4A3F4B),
          textDark: Color(0xFFF0D9E4),
          bgGradientLight: [
            Color(0xFFF0D9E4),
            Color(0xFFC1A0AC),
            Color(0xFF806C79)
          ],
          bgGradientDark: [
            Color(0xFF16131F),
            Color(0xFF4A3F4B),
            Color(0xFF0B0910)
          ],
          cardGradientLight: [Color(0xFFE0C4D0), Color(0xFFC1A0AC)],
          cardGradientDark: [Color(0xFF2D2536), Color(0xFF16131F)],
        );
      case AppThemeMode.fig:
        return const AppThemeData(
          name: "İncir & Seramik 🫒",
          primary: Color(0xFF613C4E),
          secondary: Color(0xFF9FA764),
          accent: Color(0xFFD9D8D0),
          backgroundLight: Color(0xFFD9D8D0),
          backgroundDark: Color(0xFF302B1A),
          cardLight: Color(0xFFC5C4B9),
          cardDark: Color(0xFF463D27),
          textLight: Color(0xFF613C4E),
          textDark: Color(0xFFD9D8D0),
          bgGradientLight: [
            Color(0xFFD9D8D0),
            Color(0xFF9FA764),
            Color(0xFF816A60)
          ],
          bgGradientDark: [
            Color(0xFF302B1A),
            Color(0xFF613C4E),
            Color(0xFF1F1B10)
          ],
          cardGradientLight: [Color(0xFFC5C4B9), Color(0xFF9FA764)],
          cardGradientDark: [Color(0xFF463D27), Color(0xFF302B1A)],
        );
    }
  }
}

// TÜRKİYE EXHAUSTIVE 81 İL VE TÜM İLÇELERİ LİSTESİ
class TurkiyeSehirler {
  static final Map<String, List<String>> ilIlceMap = {
    "Adana": [
      "Aladağ",
      "Ceyhan",
      "Çukurova",
      "Feke",
      "İmamoğlu",
      "Karaisalı",
      "Karataş",
      "Kozan",
      "Pozantı",
      "Saimbeyli",
      "Sarıçam",
      "Seyhan",
      "Tufanbeyli",
      "Yumurtalık",
      "Yüreğir"
    ],
    "Adıyaman": [
      "Besni",
      "Çelikhan",
      "Gerger",
      "Gölbaşı",
      "Kahta",
      "Merkez",
      "Samsat",
      "Sincik",
      "Tut"
    ],
    "Afyonkarahisar": [
      "Başmakçı",
      "Bayat",
      "Bolvadin",
      "Çay",
      "Çobanlar",
      "Dazkırı",
      "Dinar",
      "Emirdağ",
      "Evciler",
      "Hocalar",
      "İhsaniye",
      "İscehisar",
      "Kızılören",
      "Merkez",
      "Sandıklı",
      "Sinanpaşa",
      "Sultandağı",
      "Şuhut"
    ],
    "Ağrı": [
      "Diyadin",
      "Doğubayazıt",
      "Eleşkirt",
      "Hamur",
      "Merkez",
      "Patnos",
      "Taşlıçay",
      "Tutak"
    ],
    "Amasya": [
      "Göynücek",
      "Gümüşhacıköy",
      "Hamamözü",
      "Merkez",
      "Merzifon",
      "Suluova",
      "Taşova"
    ],
    "Ankara": [
      "Akyurt",
      "Altındağ",
      "Ayaş",
      "Bala",
      "Beypazarı",
      "Çamlıdere",
      "Çankaya",
      "Çubuk",
      "Elmadağ",
      "Etimesgut",
      "Evren",
      "Gölbaşı",
      "Güdül",
      "Haymana",
      "Kahramankazan",
      "Kalecik",
      "Keçiören",
      "Kızılcahamam",
      "Mamak",
      "Nallıhan",
      "Polatlı",
      "Pursaklar",
      "Sincan",
      "Şereflikoçhisar",
      "Yenimahalle"
    ],
    "Antalya": [
      "Akseki",
      "Aksu",
      "Alanya",
      "Demre",
      "Döşemealtı",
      "Elmalı",
      "Finike",
      "Gazipaşa",
      "Gündoğmuş",
      "İbradı",
      "Kaş",
      "Kemer",
      "Kepez",
      "Konyaaltı",
      "Korkuteli",
      "Kumluca",
      "Manavgat",
      "Muratpaşa",
      "Serik"
    ],
    "Artvin": [
      "Ardanuç",
      "Arhavi",
      "Borçka",
      "Hopa",
      "Kemalpaşa",
      "Merkez",
      "Murgul",
      "Şavşat",
      "Yusufeli"
    ],
    "Aydın": [
      "Bozdoğan",
      "Buharkent",
      "Çine",
      "Didim",
      "Efeler",
      "Germencik",
      "İncirliova",
      "Karacasu",
      "Karpuzlu",
      "Koçarlı",
      "Köşk",
      "Kuşadası",
      "Kuyucak",
      "Nazilli",
      "Söke",
      "Sultanhisar",
      "Yenipazar"
    ],
    "Balıkesir": [
      "Altıeylül",
      "Ayvalık",
      "Balya",
      "Bandırma",
      "Bigadiç",
      "Burhaniye",
      "Dursunbey",
      "Edremit",
      "Erdek",
      "Gömeç",
      "Gönen",
      "Havran",
      "İvrindi",
      "Karesi",
      "Kepsut",
      "Manyas",
      "Marmara",
      "Savaştepe",
      "Sındırgı",
      "Susurluk"
    ],
    "Bilecik": [
      "Bozüyük",
      "Gölpazarı",
      "İnhisar",
      "Merkez",
      "Osmaneli",
      "Pazaryeri",
      "Söğüt",
      "Yenipazar"
    ],
    "Bingöl": [
      "Adaklı",
      "Genç",
      "Karlıova",
      "Kiğı",
      "Merkez",
      "Solhan",
      "Yayladere",
      "Yedisu"
    ],
    "Bitlis": [
      "Adilcevaz",
      "Ahlat",
      "Güroymak",
      "Hizan",
      "Merkez",
      "Mutki",
      "Tatvan"
    ],
    "Bolu": [
      "Dörtdivan",
      "Gerede",
      "Göynük",
      "Kıbrıscık",
      "Mengen",
      "Merkez",
      "Mudurnu",
      "Seben",
      "Yeniçağa"
    ],
    "Burdur": [
      "Ağlasun",
      "Altınyayla",
      "Bucak",
      "Çavdır",
      "Çeltikçi",
      "Gölhisar",
      "Karamanlı",
      "Kemer",
      "Merkez",
      "Tefenni",
      "Yeşilova"
    ],
    "Bursa": [
      "Büyükorhan",
      "Gemlik",
      "Gürsu",
      "Harmancık",
      "İnegöl",
      "İznik",
      "Karacabey",
      "Keles",
      "Kestel",
      "Mudanya",
      "Mustafakemalpaşa",
      "Nilüfer",
      "Orhaneli",
      "Orhangazi",
      "Osmangazi",
      "Yenişehir",
      "Yıldırım"
    ],
    "Çanakkale": [
      "Ayvacık",
      "Bayramiç",
      "Biga",
      "Bozcaada",
      "Çan",
      "Eceabat",
      "Ezine",
      "Gelibolu",
      "Gökçeada",
      "Lapseki",
      "Merkez",
      "Yenice"
    ],
    "Çankırı": [
      "Atkaracalar",
      "Bayramören",
      "Çerkeş",
      "Eldivan",
      "Ilgaz",
      "Kızılırmak",
      "Korgun",
      "Kurşunlu",
      "Merkez",
      "Orta",
      "Şabanözü",
      "Yapraklı"
    ],
    "Çorum": [
      "Alaca",
      "Bayat",
      "Boğazkale",
      "Dodurga",
      "İskilip",
      "Kargı",
      "Laçin",
      "Mecitözü",
      "Merkez",
      "Oğuzlar",
      "Ortaköy",
      "Osmancık",
      "Sungurlu",
      "Uğurludağ"
    ],
    "Denizli": [
      "Acıpayam",
      "Babadağ",
      "Baklan",
      "Bekilli",
      "Beyağaç",
      "Bozkurt",
      "Buldan",
      "Çal",
      "Çameli",
      "Çardak",
      "Çivril",
      "Güney",
      "Honaz",
      "Kale",
      "Merkezefendi",
      "Pamukkale",
      "Sarayköy",
      "Serinhisar",
      "Tavas"
    ],
    "Diyarbakır": [
      "Bağlar",
      "Bismil",
      "Çermik",
      "Çınar",
      "Çüngüş",
      "Dicle",
      "Eğil",
      "Ergani",
      "Hani",
      "Hazro",
      "Kayapınar",
      "Kocaköy",
      "Kulp",
      "Lice",
      "Silvan",
      "Sur",
      "Yenişehir"
    ],
    "Edirne": [
      "Enez",
      "Havsa",
      "İpsala",
      "Keşan",
      "Lalapaşa",
      "Meriç",
      "Merkez",
      "Süloğlu",
      "Uzunköprü"
    ],
    "Elazığ": [
      "Ağın",
      "Alacakaya",
      "Arıcak",
      "Baskil",
      "Karakoçan",
      "Keban",
      "Kovancılar",
      "Maden",
      "Merkez",
      "Palu",
      "Sivrice"
    ],
    "Erzincan": [
      "Çayırlı",
      "İliç",
      "Kemah",
      "Kemaliye",
      "Merkez",
      "Otlukbeli",
      "Refahiye",
      "Tercan",
      "Üzümlü"
    ],
    "Erzurum": [
      "Aşkale",
      "Aziziye",
      "Çat",
      "Hınıs",
      "Horasan",
      "İspir",
      "Karaçoban",
      "Karayazı",
      "Köprüköy",
      "Narman",
      "Oltu",
      "Olur",
      "Palandöken",
      "Pasinler",
      "Pazaryolu",
      "Şenkaya",
      "Tekman",
      "Tortum",
      "Uzundere",
      "Yakutiye"
    ],
    "Eskişehir": [
      "Alpu",
      "Beylikova",
      "Çifteler",
      "Günyüzü",
      "Han",
      "İnönü",
      "Mahmudiye",
      "Mihalgazi",
      "Mihalıççık",
      "Odunpazarı",
      "Seyitgazi",
      "Sivrihisar",
      "Tepebaşı"
    ],
    "Gaziantep": [
      "Arabam",
      "İslahiye",
      "Karkamış",
      "Nizip",
      "Oğuzeli",
      "Nurdağı",
      "Şahinbey",
      "Şehitkamil",
      "Yavuzeli"
    ],
    "Giresun": [
      "Alucra",
      "Bulancak",
      "Çamoluk",
      "Çanakçı",
      "Dereli",
      "Doğankent",
      "Espiye",
      "Eynesil",
      "Görele",
      "Güce",
      "Keşap",
      "Merkez",
      "Piraziz",
      "Şebinkarahisar",
      "Tirebolu",
      "Yağlıdere"
    ],
    "Gümüşhane": ["Kelkit", "Köse", "Kürtün", "Merkez", "Şiran", "Torul"],
    "Hakkari": ["Çukurca", "Derecik", "Merkez", "Şemdinli", "Yüksekova"],
    "Hatay": [
      "Altınözü",
      "Antakya",
      "Arsuz",
      "Belen",
      "Defne",
      "Dörtyol",
      "Ezin",
      "Hassa",
      "İskenderun",
      "Kırıkhan",
      "Kumlu",
      "Payas",
      "Reyhanlı",
      "Samandağ",
      "Yayladağı"
    ],
    "Isparta": [
      "Aksu",
      "Atabey",
      "Eğirdir",
      "Gelendost",
      "Gönen",
      "Keçiborlu",
      "Merkez",
      "Senirkent",
      "Sütçüler",
      "Şarkikaraağaç",
      "Uluborlu",
      "Yalvaç",
      "Yenişarbademli"
    ],
    "Mersin": [
      "Akdeniz",
      "Anamur",
      "Aydıncık",
      "Bozyazı",
      "Çamlıyayla",
      "Erdemli",
      "Gülnar",
      "Mezitli",
      "Mut",
      "Silifke",
      "Tarsus",
      "Toroslar",
      "Yenişehir"
    ],
    "İstanbul": [
      "Adalar",
      "Arnavutköy",
      "Ataşehir",
      "Avcılar",
      "Bağcılar",
      "Bahçelievler",
      "Bakırköy",
      "Başakşehir",
      "Bayrampaşa",
      "Beşiktaş",
      "Beykoz",
      "Beylikdüzü",
      "Beyoğlu",
      "Büyükçekmece",
      "Çatalca",
      "Çekmeköy",
      "Esenler",
      "Esenyurt",
      "Eyüpsultan",
      "Fatih",
      "Gaziosmanpaşa",
      "Güngören",
      "Kadıköy",
      "Kağıthane",
      "Kartal",
      "Küçükçekmece",
      "Maltepe",
      "Pendik",
      "Sancaktepe",
      "Sarıyer",
      "Silivri",
      "Sultanbeyli",
      "Sultangazi",
      "Şile",
      "Şişli",
      "Tuzla",
      "Ümraniye",
      "Üsküdar",
      "Zeytinburnu"
    ],
    "İzmir": [
      "Aliağa",
      "Balçova",
      "Bayındır",
      "Bayraklı",
      "Bergama",
      "Beydağ",
      "Bornova",
      "Buca",
      "Çeşme",
      "Çiğli",
      "Dikili",
      "Foça",
      "Gaziemir",
      "Güzelbahçe",
      "Karabağlar",
      "Karaburun",
      "Karşıyaka",
      "Kemalpaşa",
      "Kınık",
      "Kiraz",
      "Konak",
      "Menderes",
      "Menemen",
      "Narlıdere",
      "Ödemiş",
      "Seferihisar",
      "Selçuk",
      "Tire",
      "Torbalı",
      "Urla"
    ],
    "Kars": [
      "Akyaka",
      "Arpaçay",
      "Digor",
      "Kağızman",
      "Merkez",
      "Sarıkamış",
      "Selim",
      "Susuz"
    ],
    "Kastamonu": [
      "Abana",
      "Ağlı",
      "Araç",
      "Azdavay",
      "Bozkurt",
      "Cide",
      "Çatalzeytin",
      "Daday",
      "Devrekani",
      "Doğanyurt",
      "Hanönü",
      "İhsangazi",
      "İnebolu",
      "Küre",
      "Merkez",
      "Pınarbaşı",
      "Seydiler",
      "Şenpazar",
      "Taşköprü",
      "Tosya"
    ],
    "Kayseri": [
      "Akkışla",
      "Bünyan",
      "Develi",
      "Felahiye",
      "Hacılar",
      "İncesu",
      "Kocasinan",
      "Melikgazi",
      "Özvatan",
      "Pınarbaşı",
      "Sarıoğlan",
      "Sarız",
      "Talas",
      "Tomarza",
      "Yahyalı",
      "Yeşilhisar"
    ],
    "Kırklareli": [
      "Babaeski",
      "Demirköy",
      "Kofçaz",
      "Lüleburgaz",
      "Merkez",
      "Pehlivanköy",
      "Pınarhisar",
      "Vize"
    ],
    "Kırşehir": [
      "Akçakent",
      "Akpınar",
      "Boztepe",
      "Çiçekdağı",
      "Kaman",
      "Merkez",
      "Mucur"
    ],
    "Kocaeli": [
      "Başiskele",
      "Çayırova",
      "Darıca",
      "Derince",
      "Dilovası",
      "Gebze",
      "Gölcük",
      "İzmit",
      "Kandıra",
      "Karamürsel",
      "Kartepe",
      "Körfez"
    ],
    "Konya": [
      "Ahırlı",
      "Akören",
      "Akşehir",
      "Altınekin",
      "Beyşehir",
      "Bozkır",
      "Cihanbeyli",
      "Çeltik",
      "Çumra",
      "Derbent",
      "Derebucak",
      "Doğanhisar",
      "Emirgazi",
      "Ereğli",
      "Güneysınır",
      "Hadim",
      "Halkapınar",
      "Hüyük",
      "Ilgın",
      "Kadınhanı",
      "Karapınar",
      "Karatay",
      "Kulu",
      "Meram",
      "Sarayönü",
      "Selçuklu",
      "Seydişehir",
      "Taşkent",
      "Tuzlukçu",
      "Yalıhüyük",
      "Yunak"
    ],
    "Kütahya": [
      "Altıntaş",
      "Aslanapa",
      "Çavdarhisar",
      "Domaniç",
      "Dumlupınar",
      "Emet",
      "Gediz",
      "Hisarcık",
      "Merkez",
      "Pazarlar",
      "Şaphane",
      "Simav",
      "Tavşanlı"
    ],
    "Malatya": [
      "Akçadağ",
      "Arapgir",
      "Arguvan",
      "Battalgazi",
      "Darende",
      "Doğanşehir",
      "Doğanyol",
      "Hekimhan",
      "Kale",
      "Kuluncak",
      "Pütürge",
      "Yazıhan",
      "Yeşilyurt"
    ],
    "Manisa": [
      "Ahmetli",
      "Akhisar",
      "Alaşehir",
      "Demirci",
      "Gölmarmara",
      "Gördes",
      "Kırkağaç",
      "Köprübaşı",
      "Kula",
      "Salihli",
      "Sarıgöl",
      "Saruhanlı",
      "Selendi",
      "Soma",
      "Şehzadeler",
      "Turgutlu",
      "Yunusemre"
    ],
    "Kahramanmaraş": [
      "Afşin",
      "Andırın",
      "Çağlayancerit",
      "Dulkadiroğlu",
      "Ekinözü",
      "Elbistan",
      "Göksun",
      "Nurhak",
      "Onikişubat",
      "Pazarcık",
      "Türkoğlu"
    ],
    "Mardin": [
      "Artuklu",
      "Dargeçit",
      "Derik",
      "Kızıltepe",
      "Mazıdağı",
      "Midyat",
      "Nusaybin",
      "Ömerli",
      "Savur",
      "Yeşilli"
    ],
    "Muğla": [
      "Bodrum",
      "Dalaman",
      "Datça",
      "Fethiye",
      "Kavaklıdere",
      "Köyceğiz",
      "Marmaris",
      "Menteşe",
      "Milas",
      "Ortaca",
      "Seydikemer",
      "Ula",
      "Yatağan"
    ],
    "Muş": ["Bulanık", "Hasköy", "Korkut", "Malazgirt", "Merkez", "Varto"],
    "Nevşehir": [
      "Acıgöl",
      "Avanos",
      "Derinkuyu",
      "Gülşehir",
      "Hacıbektaş",
      "Kozaklı",
      "Merkez",
      "Ürgüp"
    ],
    "Niğde": ["Altunhisar", "Bor", "Çamardı", "Çiftlik", "Merkez", "Ulukışla"],
    "Ordu": [
      "Akkuş",
      "Altınordu",
      "Aybastı",
      "Çamaş",
      "Çatalpınar",
      "Çaybaşı",
      "Fatsa",
      "Gölköy",
      "Gülyalı",
      "Gürgentepe",
      "İkizce",
      "Kabadüz",
      "Kabataş",
      "Korgan",
      "Kumru",
      "Mescudiye",
      "Ünye",
      "Ulubey"
    ],
    "Rize": [
      "Ardeşen",
      "Çamlıhemşin",
      "Çayeli",
      "Derepazarı",
      "Fındıklı",
      "Güneysu",
      "Hemşin",
      "İkizdere",
      "İyidere",
      "Kalkandere",
      "Merkez",
      "Pazar"
    ],
    "Sakarya": [
      "Adapazarı",
      "Akyazı",
      "Arifiye",
      "Erenler",
      "Ferizli",
      "Geyve",
      "Hendek",
      "Karapürçek",
      "Karasu",
      "Kaynarca",
      "Kocaali",
      "Pamukova",
      "Sapanca",
      "Serdivan",
      "Söğütlü",
      "Taraklı"
    ],
    "Samsun": [
      "19 Mayıs",
      "Alaçam",
      "Asarcık",
      "Atakum",
      "Bafra",
      "Canik",
      "Çarşamba",
      "Havza",
      "İlkadım",
      "Kavak",
      "Ladik",
      "Salıpazarı",
      "Tekkeköy",
      "Terme",
      "Vezirköprü",
      "Yakakent"
    ],
    "Siirt": [
      "Baykan",
      "Eruh",
      "Kurtalan",
      "Merkez",
      "Pervari",
      "Şirvan",
      "Tillo"
    ],
    "Sinop": [
      "Boyabat",
      "Dikmen",
      "Durağan",
      "Erfelek",
      "Gerze",
      "Merkez",
      "Saraydüzü",
      "Türkeli"
    ],
    "Sivas": [
      "Akıncılar",
      "Altınyayla",
      "Divriği",
      "Doğanşar",
      "Gemerek",
      "Gölova",
      "Gürün",
      "Hafik",
      "İmranlı",
      "Kangal",
      "Koyulhisar",
      "Merkez",
      "Suşehri",
      "Şarkışla",
      "Ulaş",
      "Yıldızeli",
      "Zara"
    ],
    "Tekirdağ": [
      "Çerkezköy",
      "Çorlu",
      "Ergene",
      "Hayrabolu",
      "Kapaklı",
      "Malkara",
      "Marmaraereğlisi",
      "Muratlı",
      "Saray",
      "Süleymanpaşa",
      "Şarköy"
    ],
    "Tokat": [
      "Almus",
      "Artova",
      "Başçiftlik",
      "Erbaa",
      "Merkez",
      "Niksar",
      "Pazar",
      "Reşadiye",
      "Sulusaray",
      "Yeşilyurt",
      "Zile"
    ],
    "Trabzon": [
      "Akçaabat",
      "Araklı",
      "Arsin",
      "Beşikdüzü",
      "Çarşıbaşı",
      "Çaykara",
      "Dernekpazarı",
      "Düzköy",
      "Hayrat",
      "Köprübaşı",
      "Maçka",
      "Of",
      "Ortahisar",
      "Sürmene",
      "Şalpazarı",
      "Tonya",
      "Vakfıkebir",
      "Yomra"
    ],
    "Tunceli": [
      "Çemişgezek",
      "Hozat",
      "Mazgirt",
      "Nazımiye",
      "Ovacık",
      "Pertek",
      "Pülümür",
      "Merkez"
    ],
    "Şanlıurfa": [
      "Akçakale",
      "Birecik",
      "Bozova",
      "Ceylanpınar",
      "Eyyübiye",
      "Halfeti",
      "Haliliye",
      "Harran",
      "Hilvan",
      "Karaköprü",
      "Siverek",
      "Suruç",
      "Viranşehir"
    ],
    "Uşak": ["Banaz", "Eşme", "Karahallı", "Merkez", "Sivaslı", "Ulubey"],
    "Van": [
      "Bahçesaray",
      "Başkale",
      "Çaldıran",
      "Çatak",
      "Edremit",
      "Erciş",
      "Gevaş",
      "Gürpınar",
      "İpekyolu",
      "Muradiye",
      "Özalp",
      "Saray",
      "Tuşba"
    ],
    "Yozgat": [
      "Akdağmadeni",
      "Aydıncık",
      "Boğazlıyan",
      "Çandır",
      "Çayıralan",
      "Çekerek",
      "Kadışehri",
      "Merkez",
      "Saraykent",
      "Sarıkaya",
      "Sorgun",
      "Şefaatli",
      "Yenifakılı",
      "Yerköy"
    ],
    "Zonguldak": [
      "Alaplı",
      "Çaycuma",
      "Devrek",
      "Gökçebey",
      "Kilimli",
      "Kozlu",
      "Merkez"
    ],
    "Aksaray": [
      "Ağaçören",
      "Eskil",
      "Gülağaç",
      "Güzelyurt",
      "Merkez",
      "Ortaköy",
      "Sarıyahşi",
      "Sultanhanı"
    ],
    "Bayburt": ["Aydıntepe", "Demirözü", "Merkez"],
    "Karaman": [
      "Ayrancı",
      "Başyayla",
      "Ermenek",
      "Kazımkarabekir",
      "Merkez",
      "Sarıveliler"
    ],
    "Kırıkkale": [
      "Bahşılı",
      "Balışeyh",
      "Çelebi",
      "Delice",
      "Karakeçili",
      "Keskin",
      "Merkez",
      "Sulakyurt",
      "Yahşihan"
    ],
    "Batman": ["Beşiri", "Gercüş", "Hasankeyf", "Kozluk", "Merkez", "Sason"],
    "Şırnak": [
      "Beytüşşebap",
      "Cizre",
      "Güçlükonak",
      "İdil",
      "Merkez",
      "Silopi",
      "Uludere"
    ],
    "Bartın": ["Amasra", "Kurucaşile", "Merkez", "Ulus"],
    "Ardahan": ["Çıldır", "Damal", "Göle", "Hanak", "Merkez", "Posof"],
    "Iğdır": ["Aralık", "Karakoyunlu", "Merkez", "Tuzluca"],
    "Yalova": [
      "Altınova",
      "Armutlu",
      "Çınarcık",
      "Çiftlikköy",
      "Merkez",
      "Termal"
    ],
    "Karabük": [
      "Eflani",
      "Eskipazar",
      "Merkez",
      "Ovacık",
      "Safranbolu",
      "Yenice"
    ],
    "Kilis": ["Elbeyli", "Merkez", "Musabeyli", "Polateli"],
    "Osmaniye": [
      "Bahçe",
      "Düziçi",
      "Hasanbeyli",
      "Kadirli",
      "Merkez",
      "Sumbas",
      "Toprakkale"
    ],
    "Düzce": [
      "Akçakoca",
      "Cumayeri",
      "Çilimli",
      "Gölyaka",
      "Gümüşova",
      "Kaynaşlı",
      "Merkez",
      "Yığılca"
    ]
  };

  static List<String> get iller {
    final list = ilIlceMap.keys.toList();
    list.sort((a, b) => a.compareTo(b));
    return list;
  }

  static List<String> getIlceler(String il) {
    return ilIlceMap[il] ?? ["Merkez"];
  }
}

// ==================== ONLİNE DUA/AYET/HADİS/ESMA SERVİSİ ====================
class OnlineIcerikServisi {
  static const List<Map<String, String>> zenginAyetler = [
    {
      "ayet":
          "Şüphesiz güçlükle beraber bir kolaylık vardır. Gerçekten, güçlükle beraber bir kolaylık vardır.",
      "sure": "İnşirah Sûresi, 5-6"
    },
    {
      "ayet": "Bilesiniz ki, kalpler ancak Allah'ı anmakla huzur bulur.",
      "sure": "Ra'd Sûresi, 28"
    },
    {
      "ayet":
          "Ey iman edenler! Sabır ve namaz ile Allah'tan yardım isteyin. Çünkü Allah sabredenlerle beraberdir.",
      "sure": "Bakara Sûresi, 153"
    },
    {
      "ayet": "Eğer şükrederseniz, elbette size nimetimi artırırım.",
      "sure": "İbrahim Sûresi, 7"
    },
    {
      "ayet":
          "Rabbimiz! Bize dünyada da iyilik ver, ahirette de iyilik ver ve bizi cehennem azabından koru.",
      "sure": "Bakara Sûresi, 201"
    },
    {
      "ayet":
          "Kullarıma söyle: En güzel sözü söylesinler. Çünkü şeytan aralarını bozmaya çalışır.",
      "sure": "İsrâ Sûresi, 53"
    },
    {
      "ayet":
          "Nerede olursanız olun O sizinle beraberdir. Allah yaptıklarınızı hakkıyla görendir.",
      "sure": "Hadîd Sûresi, 4"
    },
  ];

  static const List<Map<String, String>> zenginHadisler = [
    {
      "hadis":
          "Namaz, dinin direğidir. Onu kılan dinini ihya etmiş, terk eden ise dinini yıkmış olur.",
      "kaynak": "Tirmizî, İman 8"
    },
    {
      "hadis": "Sizin en hayırlınız, ahlakı en güzel olanınızdır.",
      "kaynak": "Buhârî, Edeb 38"
    },
    {
      "hadis":
          "Müslüman, elinden ve dilinden diğer müslümanların güvende olduğu kimsedir.",
      "kaynak": "Buhârî, İman 4"
    },
    {
      "hadis":
          "Kolaylaştırınız, zorlaştırmayınız; müjdeleyiniz, nefret ettirmeyiniz.",
      "kaynak": "Buhârî, İlim 11"
    },
    {
      "hadis":
          "Hiçbir baba, çocuğuna güzel ahlaktan daha üstün bir miras bırakamaz.",
      "kaynak": "Tirmizî, Birr 33"
    },
    {"hadis": "Veren el, alan elden hayırlıdır.", "kaynak": "Buhârî, Zekât 18"},
  ];

  static const List<Map<String, String>> zenginDualar = [
    {
      "arapca":
          "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ",
      "okunusu":
          "Rabbena atina fid-dunya haseneten ve fil-ahirati haseneten ve qina 'azaben-nar.",
      "anlamı":
          "Rabbimiz! Bize dünyada da iyilik ver, ahirette de iyilik ver ve bizi cehennem azabından koru."
    },
    {
      "arapca":
          "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْهُدَى وَالتُّقَى وَالْعَفَافَ وَالْغِنَى",
      "okunusu": "Allahümme inni es-elükel-hüda vet-tuqa vel-'afafe vel-ghina.",
      "anlamı":
          "Allah'ım! Senden hidayet, takva, iffet ve gönül zenginliği istiyorum."
    },
    {
      "arapca": "رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي",
      "okunusu": "Rabbişrah li sadri ve yessir li emri.",
      "anlamı": "Rabbim! Göğsümü genişlet, işimi kolaylaştır."
    },
    {
      "arapca": "اللَّهُمَّ اهْدِنِي وَسَدِّدْنِي",
      "okunusu": "Allahümmehdini ve seddidni.",
      "anlamı": "Allah'ım! Beni doğru yola ilet ve işlerimde başarıya ulaştır."
    },
  ];

  static const List<Map<String, String>> zenginEsmalar = [
    {
      "esma": "Er-Rahmân (الرَّحْمَنُ)",
      "anlam":
          "Dünyada inanan inanmayan bütün canlılara merhamet gösteren mutlak lütuf sahibi."
    },
    {
      "esma": "Er-Rahîm (الرَّحِيمُ)",
      "anlam": "Ahirette sadece müminlere ebedi merhamet ve ihsanda bulunan."
    },
    {
      "esma": "El-Melik (الْمَلِكُ)",
      "anlam": "Mülkün, evrenin ve bütün varlıkların tek ve mutlak sahibi."
    },
    {
      "esma": "El-Kuddûs (الْقُدُّوسُ)",
      "anlam": "Bütün noksanlıklardan münezzeh, pek kutsal ve tertemiz olan."
    },
    {
      "esma": "Es-Selâm (السَّلاَمُ)",
      "anlam": "Esenlik veren, yarattıklarını tehlikelerden selamete çıkaran."
    },
    {
      "esma": "El-Mü'min (الْمُؤْمِنُ)",
      "anlam": "Gönüllere iman ve huzur veren, sığınanları emniyette kılan."
    },
  ];

  static Future<Map<String, dynamic>> getGununIcerikleri() async {
    final gunHash = DateTime.now().year * 1000 + DateTime.now().dayOfYear();
    try {
      final res = await http
          .get(Uri.parse('https://api.alquran.cloud/v1/ayah/random/tr.yazir'))
          .timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        if (data['code'] == 200 && data['data'] != null) {
          final text = data['data']['text'] ?? "";
          final surahName = data['data']['surah']['name'] ?? "";
          final ayahNum = data['data']['numberInSurah'] ?? 1;
          if (text.isNotEmpty) {
            final hItem = zenginHadisler[gunHash % zenginHadisler.length];
            final dItem = zenginDualar[gunHash % zenginDualar.length];
            final eItem = zenginEsmalar[gunHash % zenginEsmalar.length];

            return {
              "ayet": "$text ($surahName, $ayahNum)",
              "hadis": "${hItem['hadis']} (${hItem['kaynak']})",
              "dua": dItem,
              "esma": "${eItem['esma']}\n${eItem['anlam']}",
            };
          }
        }
      }
    } catch (e) {
      debugPrint("Online API fallback kullanıldı: $e");
    }

    var a = zenginAyetler[gunHash % zenginAyetler.length];
    var h = zenginHadisler[gunHash % zenginHadisler.length];
    var d = zenginDualar[gunHash % zenginDualar.length];
    var e = zenginEsmalar[gunHash % zenginEsmalar.length];

    return {
      "ayet": "${a['ayet']} (${a['sure']})",
      "hadis": "${h['hadis']} (${h['kaynak']})",
      "dua": d,
      "esma": "${e['esma']}\n${e['anlam']}",
    };
  }
}

extension DateTimeDayOfYear on DateTime {
  int dayOfYear() {
    final diff = difference(DateTime(year, 1, 1));
    return diff.inDays + 1;
  }
}

// ==================== ANA GİRİŞ NOKTASI ====================
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('tr_TR', null);
  tz_data.initializeTimeZones();
  tz.setLocalLocation(tz.getLocation('Europe/Istanbul'));

  if (!kIsWeb) {
    try {
      final status = await Permission.notification.status;
      if (status.isDenied) {
        await Permission.notification.request();
      }

      const AndroidInitializationSettings initializationSettingsAndroid =
          AndroidInitializationSettings('@mipmap/ic_launcher');
      const InitializationSettings initializationSettings =
          InitializationSettings(android: initializationSettingsAndroid);

      await flutterLocalNotificationsPlugin.initialize(
        initializationSettings,
        onDidReceiveNotificationResponse: (NotificationResponse response) {},
      );

      final androidImplementation =
          flutterLocalNotificationsPlugin.resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>();

      if (androidImplementation != null) {
        const AndroidNotificationChannel channelMax = AndroidNotificationChannel(
          'namaz_vakitleri_max_v2',
          'Namaz Vakitleri & Hatırlatmalar',
          description: 'Tam ekran ve kilit ekranı ezan/vakit öncesi hatırlatıcı bildirimleri',
          importance: Importance.max,
          enableVibration: true,
          playSound: true,
        );
        await androidImplementation.createNotificationChannel(channelMax);

        const AndroidNotificationChannel channel1 = AndroidNotificationChannel(
          'namaz_vakitleri',
          'Namaz Vakitleri',
          description: 'Namaz vakitleri ve hatırlatıcı bildirimleri',
          importance: Importance.high,
        );
        await androidImplementation.createNotificationChannel(channel1);

        const AndroidNotificationChannel channel2 = AndroidNotificationChannel(
          'namaz_vakitleri_sabit',
          'Sabit Namaz Vakti',
          description: 'Namaz vakitlerini gösterir',
          importance: Importance.low,
        );
        await androidImplementation.createNotificationChannel(channel2);
      }
    } catch (e) {
      debugPrint("Başlangıç bildirim hatası: $e");
    }
  }

  runApp(const MyApp());
}

// ==================== APP THEME SCOPE (INHERITED WIDGET) ====================
class AppThemeScope extends InheritedWidget {
  final AppThemeData themeData;
  final AppThemeMode themeMode;
  final bool isDark;
  final double fontScale;
  final Function(AppThemeMode, bool) onThemeChanged;
  final Function(double) onFontScaleChanged;

  const AppThemeScope({
    super.key,
    required this.themeData,
    required this.themeMode,
    required this.isDark,
    required this.fontScale,
    required this.onThemeChanged,
    required this.onFontScaleChanged,
    required super.child,
  });

  static AppThemeScope of(BuildContext context) {
    final result = context.dependOnInheritedWidgetOfExactType<AppThemeScope>();
    assert(result != null, 'AppThemeScope context ulaşılamadı');
    return result!;
  }

  static AppThemeScope? ofMaybe(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<AppThemeScope>();
  }

  @override
  bool updateShouldNotify(AppThemeScope oldWidget) {
    return themeMode != oldWidget.themeMode ||
        isDark != oldWidget.isDark ||
        fontScale != oldWidget.fontScale;
  }
}

// ==================== MYAPP ====================
class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  AppThemeMode _currentTheme = AppThemeMode.rose;
  bool _isDarkMode = false;
  double _fontScale = 1.0;
  bool _isFirstLaunch = true;
  bool _isLoaded = false;

  @override
  void initState() {
    super.initState();
    _ayarlariYukle();
  }

  Future<void> _ayarlariYukle() async {
    final prefs = await SharedPreferences.getInstance();
    final themeStr = prefs.getString('app_theme_mode') ?? 'rose';
    final dark = prefs.getBool('gece_modu') ?? false;
    final scale = prefs.getDouble('font_scale_factor') ?? 1.0;
    final firstLaunch = prefs.getBool('onboarding_completed') != true;

    setState(() {
      _currentTheme = AppThemeMode.values.firstWhere(
        (e) => e.name == themeStr,
        orElse: () => AppThemeMode.rose,
      );
      _isDarkMode = dark;
      _fontScale = scale;
      _isFirstLaunch = firstLaunch;
      _isLoaded = true;
    });
  }

  void _updateTheme(AppThemeMode mode, bool isDark) async {
    setState(() {
      _currentTheme = mode;
      _isDarkMode = isDark;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('app_theme_mode', mode.name);
    await prefs.setBool('gece_modu', isDark);
  }

  void _updateFontScale(double scale) async {
    setState(() {
      _fontScale = scale;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('font_scale_factor', scale);
  }

  void _completeOnboarding() async {
    setState(() {
      _isFirstLaunch = false;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('onboarding_completed', true);
  }

  @override
  Widget build(BuildContext context) {
    if (!_isLoaded) {
      return const MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      );
    }

    final themeData = AppThemeData.getTheme(_currentTheme);
    final primaryColor = themeData.primary;
    final cardBg = _isDarkMode ? themeData.cardDark : themeData.cardLight;
    final bg =
        _isDarkMode ? themeData.backgroundDark : themeData.backgroundLight;
    final textColor = _isDarkMode ? themeData.textDark : themeData.textLight;

    return AppThemeScope(
      themeData: themeData,
      themeMode: _currentTheme,
      isDark: _isDarkMode,
      fontScale: _fontScale,
      onThemeChanged: _updateTheme,
      onFontScaleChanged: _updateFontScale,
      child: MaterialApp(
        title: 'Ezan Vakti 🌸',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: _isDarkMode ? Brightness.dark : Brightness.light,
          primaryColor: primaryColor,
          scaffoldBackgroundColor: bg,
          fontFamily: 'Schyler',
          colorScheme: ColorScheme.fromSeed(
            seedColor: primaryColor,
            brightness: _isDarkMode ? Brightness.dark : Brightness.light,
            primary: primaryColor,
            secondary: themeData.secondary,
            surface: cardBg,
            onPrimary: Colors.white,
            onSurface: textColor,
          ),
          textTheme: TextTheme(
            displayLarge: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            displayMedium: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            displaySmall: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            headlineLarge: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            headlineMedium: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            headlineSmall: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            titleLarge: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            titleMedium: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            titleSmall: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.bold),
            bodyLarge: TextStyle(color: textColor, fontFamily: 'Schyler'),
            bodyMedium: TextStyle(
                color: textColor.withValues(alpha: 0.9), fontFamily: 'Schyler'),
            bodySmall: TextStyle(
                color: textColor.withValues(alpha: 0.7), fontFamily: 'Schyler'),
            labelLarge: TextStyle(
                color: textColor,
                fontFamily: 'Schyler',
                fontWeight: FontWeight.w500),
            labelMedium: TextStyle(
                color: textColor.withValues(alpha: 0.9), fontFamily: 'Schyler'),
            labelSmall: TextStyle(
                color: textColor.withValues(alpha: 0.7), fontFamily: 'Schyler'),
          ),
          appBarTheme: AppBarTheme(
            backgroundColor: Colors.transparent,
            elevation: 0,
            iconTheme: IconThemeData(color: primaryColor),
            titleTextStyle: TextStyle(
                color: textColor,
                fontSize: 20,
                fontWeight: FontWeight.bold,
                fontFamily: 'Schyler'),
          ),
          cardTheme: CardThemeData(
            color: cardBg,
            elevation: 4,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          ),
          dialogTheme: DialogThemeData(
            backgroundColor: cardBg,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            titleTextStyle: TextStyle(
                color: textColor,
                fontSize: 20,
                fontWeight: FontWeight.bold,
                fontFamily: 'Schyler'),
            contentTextStyle: TextStyle(
                color: textColor.withValues(alpha: 0.9),
                fontSize: 16,
                fontFamily: 'Schyler'),
          ),
          bottomNavigationBarTheme: BottomNavigationBarThemeData(
            backgroundColor: cardBg,
            selectedItemColor: primaryColor,
            unselectedItemColor: _isDarkMode ? Colors.white38 : Colors.black38,
            selectedLabelStyle: const TextStyle(fontWeight: FontWeight.bold),
          ),
          navigationBarTheme: NavigationBarThemeData(
            backgroundColor: cardBg,
            indicatorColor: primaryColor.withValues(alpha: 0.3),
            iconTheme: WidgetStateProperty.resolveWith((states) {
              if (states.contains(WidgetState.selected)) {
                return IconThemeData(color: primaryColor);
              }
              return IconThemeData(
                  color: _isDarkMode ? Colors.white38 : Colors.black38);
            }),
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              backgroundColor: primaryColor,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18)),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            ),
          ),
          textButtonTheme: TextButtonThemeData(
            style: TextButton.styleFrom(
              foregroundColor: primaryColor,
            ),
          ),
          outlinedButtonTheme: OutlinedButtonThemeData(
            style: OutlinedButton.styleFrom(
              foregroundColor: primaryColor,
              side: BorderSide(color: primaryColor),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18)),
            ),
          ),
          iconTheme: IconThemeData(color: primaryColor),
          dividerTheme: DividerThemeData(
            color: _isDarkMode ? Colors.white12 : Colors.black12,
          ),
          chipTheme: ChipThemeData(
            backgroundColor: cardBg,
            selectedColor: primaryColor.withValues(alpha: 0.35),
            secondarySelectedColor: primaryColor,
            labelStyle:
                TextStyle(color: textColor, fontWeight: FontWeight.bold),
          ),
          switchTheme: SwitchThemeData(
            thumbColor: WidgetStateProperty.all(primaryColor),
            trackColor:
                WidgetStateProperty.all(primaryColor.withValues(alpha: 0.3)),
          ),
          sliderTheme: SliderThemeData(
            activeTrackColor: primaryColor,
            thumbColor: primaryColor,
            overlayColor: primaryColor.withValues(alpha: 0.2),
          ),
          bottomSheetTheme: BottomSheetThemeData(
            backgroundColor: cardBg,
            shape: const RoundedRectangleBorder(
              borderRadius: BorderRadius.vertical(top: Radius.circular(30)),
            ),
          ),
        ),
        builder: (context, child) {
          return MediaQuery(
            data: MediaQuery.of(context).copyWith(
              textScaler: TextScaler.linear(_fontScale),
            ),
            child: child!,
          );
        },
        home: _isFirstLaunch
            ? OnboardingScreen(
                themeData: themeData,
                isDark: _isDarkMode,
                onCompleted: _completeOnboarding,
              )
            : SplashScreen(
                currentTheme: _currentTheme,
                isDarkMode: _isDarkMode,
                fontScale: _fontScale,
                onThemeChanged: _updateTheme,
                onFontScaleChanged: _updateFontScale,
                onOpenOnboarding: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => OnboardingScreen(
                        themeData: themeData,
                        isDark: _isDarkMode,
                        onCompleted: () => Navigator.of(context).pop(),
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}

// ==================== ONBOARDING ====================
class OnboardingScreen extends StatefulWidget {
  final AppThemeData themeData;
  final bool isDark;
  final VoidCallback onCompleted;

  const OnboardingScreen({
    super.key,
    required this.themeData,
    required this.isDark,
    required this.onCompleted,
  });

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  final List<Map<String, String>> _pages = [
    {
      "icon": "🕌",
      "title": "Ezan Vakti'ne Hoş Geldiniz",
      "subtitle": "81 İl ve Tüm İlçelerin Namaz Vakitleri",
      "desc": "Tüm illerin ve ilçelerin ezan vakitlerini anlık takip edin.",
    },
    {
      "icon": "🎨",
      "title": "Zengin Renk Temaları",
      "subtitle": "Tüm Uygulamayı Bürünen Canlı Renkler",
      "desc": "Gül Pembe, Zümrüt, Safir, Obsidian, Kehribar, Yakut temaları.",
    },
    {
      "icon": "🌳",
      "title": "Büyüyen Zikir Ormanı",
      "subtitle": "Her 33 Zikirde Büyüyen Ağaçlar",
      "desc":
          "1000 zikre kadar adım adım büyüyen dev ağacınız ve kişiselleştirilebilir zikir hedefleri.",
    },
    {
      "icon": "🕋",
      "title": "Diyanet Kur'an & Çeşitli Kıble API",
      "subtitle": "Çoklu Kıble Seçeneği & Diyanet Mushaf",
      "desc":
          "Google, Al-Adhan veya Diyanet kıble seçenekleriyle yönünüzü bulun.",
    },
  ];

  @override
  Widget build(BuildContext context) {
    final theme = widget.themeData;
    final isDark = widget.isDark;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: isDark ? theme.bgGradientDark : theme.bgGradientLight,
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Align(
                alignment: Alignment.topRight,
                child: TextButton(
                  onPressed: widget.onCompleted,
                  child: Text(
                    "Geç 🌸",
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: isDark ? theme.textDark : theme.primary,
                    ),
                  ),
                ),
              ),
              Expanded(
                child: PageView.builder(
                  controller: _pageController,
                  onPageChanged: (idx) {
                    setState(() => _currentPage = idx);
                  },
                  itemCount: _pages.length,
                  itemBuilder: (context, index) {
                    final item = _pages[index];
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            item["icon"]!,
                            style: const TextStyle(fontSize: 64),
                          ),
                          const SizedBox(height: 32),
                          Text(
                            item["title"]!,
                            style: TextStyle(
                              fontSize: 26,
                              fontWeight: FontWeight.bold,
                              color: isDark ? theme.textDark : theme.primary,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            item["subtitle"]!,
                            style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w600,
                              color: isDark
                                  ? Colors.white.withValues(alpha: 0.9)
                                  : Colors.black87,
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            item["desc"]!,
                            style: TextStyle(
                              fontSize: 15,
                              height: 1.5,
                              color: isDark ? Colors.white70 : Colors.black54,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  _pages.length,
                  (i) => AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: _currentPage == i ? 24 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: _currentPage == i
                          ? theme.primary
                          : (isDark ? Colors.white30 : Colors.black26),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Padding(
                padding: const EdgeInsets.all(24),
                child: SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: () {
                      if (_currentPage < _pages.length - 1) {
                        _pageController.nextPage(
                          duration: const Duration(milliseconds: 300),
                          curve: Curves.easeInOut,
                        );
                      } else {
                        widget.onCompleted();
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: theme.primary,
                      foregroundColor: Colors.white,
                      elevation: 4,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(26),
                      ),
                    ),
                    child: Text(
                      _currentPage == _pages.length - 1
                          ? "Başla 🌸"
                          : "Devam Et ➔",
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ==================== BİLDİRİM FONKSİYONLARI ====================
Future<void> showNotification(
  String title,
  String body, {
  bool sesli = true,
  String? sound,
}) async {
  if (kIsWeb) return;

  try {
    AndroidNotificationDetails androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'namaz_vakitleri',
      'Namaz Vakitleri',
      importance: Importance.max,
      priority: Priority.max,
      playSound: sesli,
      fullScreenIntent: true,
      sound: sound != null && sound != "default" && sound != "silent"
          ? RawResourceAndroidNotificationSound(sound)
          : null,
      enableVibration: true,
      vibrationPattern: Int64List.fromList([0, 500, 1000, 500]),
    );

    final NotificationDetails platformChannelSpecifics = NotificationDetails(
      android: androidPlatformChannelSpecifics,
    );

    await flutterLocalNotificationsPlugin.show(
      DateTime.now().millisecondsSinceEpoch.remainder(100000),
      title,
      body,
      platformChannelSpecifics,
    );
  } catch (e) {
    debugPrint("Bildirim hatası: $e");
  }
}

Future<void> updateVakitBilgiCubugu(
  Map<String, String> vakitler,
) async {
  if (kIsWeb) return;

  try {
    const sira = ["İmsak", "Güneş", "Öğle", "İkindi", "Akşam", "Yatsı"];
    List<String> vakitListesi = [];

    for (var v in sira) {
      if (vakitler[v] != null && vakitler[v] != "--:--") {
        vakitListesi.add("$v ${vakitler[v]}");
      }
    }

    String vakitSatiri = vakitListesi.join(" | ");

    final bigText = BigTextStyleInformation(
      vakitSatiri,
      contentTitle: "",
      summaryText: "",
    );

    final details = NotificationDetails(
      android: AndroidNotificationDetails(
        'namaz_vakitleri_sabit',
        'Namaz Vakitleri',
        importance: Importance.low,
        priority: Priority.low,
        ongoing: true,
        autoCancel: false,
        playSound: false,
        enableVibration: false,
        onlyAlertOnce: true,
        showWhen: false,
        styleInformation: bigText,
      ),
    );

    await flutterLocalNotificationsPlugin.show(
      999,
      "",
      vakitSatiri,
      details,
    );
  } catch (e) {
    debugPrint("Vakit bilgi çubuğu hatası: $e");
  }
}

Future<void> cancelNotification() async {
  try {
    await flutterLocalNotificationsPlugin.cancel(999);
  } catch (e) {
    debugPrint("Bildirim kapatma hatası: $e");
  }
}

// ==================== SPLASH SCREEN ====================
class SplashScreen extends StatefulWidget {
  final AppThemeMode currentTheme;
  final bool isDarkMode;
  final double fontScale;
  final Function(AppThemeMode, bool) onThemeChanged;
  final Function(double) onFontScaleChanged;
  final VoidCallback onOpenOnboarding;

  const SplashScreen({
    super.key,
    required this.currentTheme,
    required this.isDarkMode,
    required this.fontScale,
    required this.onThemeChanged,
    required this.onFontScaleChanged,
    required this.onOpenOnboarding,
  });

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (context) => EzanVaktiApp(
              currentTheme: widget.currentTheme,
              isDarkMode: widget.isDarkMode,
              fontScale: widget.fontScale,
              onThemeChanged: widget.onThemeChanged,
              onFontScaleChanged: widget.onFontScaleChanged,
              onOpenOnboarding: widget.onOpenOnboarding,
            ),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = AppThemeData.getTheme(widget.currentTheme);
    final isDark = widget.isDarkMode;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: isDark ? theme.bgGradientDark : theme.bgGradientLight,
          ),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                "🌸 HOŞ GELDİNİZ 🌸",
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: isDark ? theme.textDark : theme.primary,
                  letterSpacing: 2,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 40),
              CircularProgressIndicator(color: theme.primary),
            ],
          ),
        ),
      ),
    );
  }
}

// ==================== iOS GLASS CARD WIDGET ====================
class IosGlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry margin;
  final BorderRadius? borderRadius;
  final bool? isDark;
  final AppThemeData? themeData;
  final VoidCallback? onTap;

  const IosGlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin = const EdgeInsets.only(bottom: 12),
    this.borderRadius,
    this.isDark,
    this.themeData,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scope = AppThemeScope.ofMaybe(context);
    final effectiveIsDark = isDark ??
        scope?.isDark ??
        (Theme.of(context).brightness == Brightness.dark);
    final effectiveTheme = themeData ??
        scope?.themeData ??
        AppThemeData.getTheme(AppThemeMode.rose);

    final br = borderRadius ?? BorderRadius.circular(24);
    final cardGrad = effectiveIsDark
        ? effectiveTheme.cardGradientDark
        : effectiveTheme.cardGradientLight;

    return Container(
      margin: margin,
      child: ClipRRect(
        borderRadius: br,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: InkWell(
            onTap: onTap != null
                ? () {
                    HapticFeedback.lightImpact();
                    onTap!();
                  }
                : null,
            borderRadius: br,
            child: Container(
              padding: padding,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: cardGrad,
                ),
                borderRadius: br,
                border: Border.all(
                  color: effectiveIsDark
                      ? effectiveTheme.primary.withValues(alpha: 0.50)
                      : effectiveTheme.primary.withValues(alpha: 0.35),
                  width: 1.4,
                ),
                boxShadow: [
                  BoxShadow(
                    color: effectiveIsDark
                        ? Colors.black.withValues(alpha: 0.7)
                        : effectiveTheme.primary.withValues(alpha: 0.15),
                    blurRadius: 18,
                    offset: const Offset(0, 6),
                  )
                ],
              ),
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}

// ==================== KUR'AN & KİBLE WEBVIEW ====================
class KuranWebView extends StatefulWidget {
  final bool isDark;
  const KuranWebView({super.key, required this.isDark});

  @override
  State<KuranWebView> createState() => _KuranWebViewState();
}

class _KuranWebViewState extends State<KuranWebView> {
  WebViewController? _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    if (!kIsWeb) {
      _controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(
            widget.isDark ? const Color(0xFF18181B) : Colors.white)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageFinished: (url) {
              if (mounted) setState(() => _isLoading = false);
            },
          ),
        )
        ..loadRequest(Uri.parse('https://kuran.diyanet.gov.tr/mushaf'));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kIsWeb || _controller == null) {
      return const Center(child: Text("Kur'an-ı Kerim Diyanet okuma ekranı"));
    }
    return Stack(
      children: [
        WebViewWidget(controller: _controller!),
        if (_isLoading) const Center(child: CircularProgressIndicator()),
      ],
    );
  }
}

class KibleWebView extends StatefulWidget {
  final bool isDark;
  final AppThemeData themeData;

  const KibleWebView({
    super.key,
    required this.isDark,
    required this.themeData,
  });

  @override
  State<KibleWebView> createState() => _KibleWebViewState();
}

class _KibleWebViewState extends State<KibleWebView> {
  WebViewController? _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _initWebview('https://qiblafinder.withgoogle.com/');
  }

  void _initWebview(String url) {
    if (!kIsWeb) {
      setState(() => _isLoading = true);
      _controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(
            widget.isDark ? const Color(0xFF18181B) : Colors.white)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageFinished: (finishedUrl) {
              if (mounted) setState(() => _isLoading = false);
            },
          ),
        )
        ..loadRequest(Uri.parse(url));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = widget.themeData;

    if (kIsWeb || _controller == null) {
      return const Center(child: Text("Kıble Bulucu ekranı"));
    }

    return Stack(
      children: [
        WebViewWidget(controller: _controller!),
        if (_isLoading)
          Center(child: CircularProgressIndicator(color: theme.primary)),
      ],
    );
  }
}

// ==================== ZİKİRMATİK ====================
class ZikirmatikPage extends StatefulWidget {
  final bool isDark;
  final AppThemeData themeData;

  const ZikirmatikPage({
    super.key,
    required this.isDark,
    required this.themeData,
  });

  @override
  State<ZikirmatikPage> createState() => _ZikirmatikPageState();
}

class _ZikirmatikPageState extends State<ZikirmatikPage> {
  int _counter = 0;
  int _toplamZikirSayisi = 0;
  List<Map<String, dynamic>> _zikirler = [
    {"ad": "Sübhânallâh", "hedef": 33},
    {"ad": "Elhamdülillâh", "hedef": 33},
    {"ad": "Allâhuekber", "hedef": 33},
    {"ad": "Lâ ilâhe illallâh", "hedef": 100},
    {"ad": "Astağfirullâh", "hedef": 100},
  ];
  int _seciliIndex = 0;
  List<Map<String, String>> _zikirDefteri = [];

  @override
  void initState() {
    super.initState();
    _zikirleriYukle();
  }

  Future<void> _zikirleriYukle() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = prefs.getString('custom_zikirler');
    final defterStr = prefs.getString('zikir_defteri_logs');
    final toplam = prefs.getInt('toplam_zikir_sayisi') ?? 0;

    if (jsonStr != null) {
      List<dynamic> list = jsonDecode(jsonStr);
      _zikirler = list.map((e) => Map<String, dynamic>.from(e)).toList();
    }
    if (defterStr != null) {
      List<dynamic> dList = jsonDecode(defterStr);
      _zikirDefteri = dList.map((e) => Map<String, String>.from(e)).toList();
    }

    setState(() {
      _toplamZikirSayisi = toplam;
    });
  }

  Future<void> _zikirleriKaydet() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('custom_zikirler', jsonEncode(_zikirler));
    await prefs.setString('zikir_defteri_logs', jsonEncode(_zikirDefteri));
    await prefs.setInt('toplam_zikir_sayisi', _toplamZikirSayisi);
  }

  void _zikriDeftereKaydet() {
    if (_counter == 0) return;
    final zikIsim =
        _zikirler.isNotEmpty ? _zikirler[_seciliIndex]["ad"] : "Zikir";
    final agacObj = _getAgacDurumu(_counter);
    final tarih = DateFormat('d MMMM HH:mm', 'tr_TR').format(DateTime.now());

    setState(() {
      _zikirDefteri.insert(0, {
        "zikir": zikIsim,
        "sayi": "$_counter",
        "tarih": tarih,
        "agac": agacObj["emoji"]!,
      });
      _counter = 0;
    });
    _zikirleriKaydet();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text("Zikir Defterinize kaydedildi! 🌸"),
        backgroundColor: widget.themeData.primary,
      ),
    );
  }

  void _yeniZikirEkleDiyalog() {
    String ad = "";
    int hedef = 33;
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: widget.isDark
            ? widget.themeData.cardDark
            : widget.themeData.cardLight,
        title: Text(
          "Yeni Zikir Ekle 🌸",
          style: TextStyle(
              color: widget.isDark
                  ? widget.themeData.textDark
                  : widget.themeData.primary),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              decoration: const InputDecoration(labelText: "Zikir Adı"),
              onChanged: (val) => ad = val,
            ),
            TextField(
              decoration: const InputDecoration(
                  labelText: "Özel Hedef Sayısı (Örn: 33, 99, 500)"),
              keyboardType: TextInputType.number,
              onChanged: (val) => hedef = int.tryParse(val) ?? 33,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("İptal"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: widget.themeData.primary,
              foregroundColor: Colors.white,
            ),
            onPressed: () {
              if (ad.isNotEmpty) {
                setState(() {
                  _zikirler.add({"ad": ad, "hedef": hedef});
                  _seciliIndex = _zikirler.length - 1;
                  _counter = 0;
                });
                _zikirleriKaydet();
                Navigator.pop(context);
              }
            },
            child: const Text("Ekle"),
          ),
        ],
      ),
    );
  }

  void _hedefDegistirDiyalog() {
    int mevcutHedef = _zikirler[_seciliIndex]["hedef"] ?? 33;
    int yeniHedef = mevcutHedef;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: widget.isDark
            ? widget.themeData.cardDark
            : widget.themeData.cardLight,
        title: Text(
          "Hedef Sayısını Değiştir 🎯",
          style: TextStyle(
              color: widget.isDark
                  ? widget.themeData.textDark
                  : widget.themeData.primary),
        ),
        content: TextField(
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: "İstediğiniz Hedef Sayı",
            hintText: "$mevcutHedef",
          ),
          onChanged: (val) => yeniHedef = int.tryParse(val) ?? mevcutHedef,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("İptal"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: widget.themeData.primary,
              foregroundColor: Colors.white,
            ),
            onPressed: () {
              setState(() {
                _zikirler[_seciliIndex]["hedef"] = yeniHedef;
              });
              _zikirleriKaydet();
              Navigator.pop(context);
            },
            child: const Text("Kaydet"),
          ),
        ],
      ),
    );
  }

  Map<String, String> _getAgacDurumu(int count) {
    int stageIndex = (count ~/ 33) + 1;
    if (stageIndex > 200) stageIndex = 200;

    final List<String> agacEmojileri = [
      "🌱",
      "🌿",
      "🪴",
      "🌳",
      "🌸",
      "🍎",
      "🌴",
      "🫒",
      "🫐",
      "🌲",
      "🍇",
      "🍊",
      "🍐",
      "🥭",
      "🌺",
      "🪵",
      "🍁",
      "🌰",
      "🥑",
      "🌾",
      "🌴✨",
      "🌳✨",
      "🌸✨",
      "🍎✨",
      "🫒✨",
      "👑🌳",
      "👑🌴",
      "👑🌸",
      "👑🍎",
      "👑🫒"
    ];

    String emoji = agacEmojileri[(stageIndex - 1) % agacEmojileri.length];
    if (stageIndex >= 100) emoji = "👑 $emoji";

    int kalanZikir = 33 - (count % 33);
    if (count > 0 && count % 33 == 0) kalanZikir = 0;

    return {
      "emoji": emoji,
      "seviye": "Ağaç Seviyesi: $stageIndex / 200 (Her 33 Zikirde Yeni Ağaç)",
      "mesaj": kalanZikir == 0
          ? "🎉 Tebrikler! 33 zikri tamamladın ve bu seviyedeki ağacı büyüttün!"
          : "Sonraki ağacın büyümesine son $kalanZikir zikir kaldı!",
    };
  }

  @override
  Widget build(BuildContext context) {
    final theme = widget.themeData;
    final isDark = widget.isDark;
    final mevcutzikir = _zikirler.isNotEmpty
        ? _zikirler[_seciliIndex]
        : {"ad": "Zikir", "hedef": 33};
    final int hedefSayi = mevcutzikir["hedef"] ?? 33;
    final agac = _getAgacDurumu(_counter);

    int stageProgress = _counter % 33;
    double progressVal =
        (_counter > 0 && stageProgress == 0) ? 1.0 : (stageProgress / 33.0);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(18),
      child: Column(
        children: [
          IosGlassCard(
            isDark: isDark,
            themeData: theme,
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Text(
                  agac["emoji"]!,
                  style: const TextStyle(fontSize: 60),
                ),
                const SizedBox(height: 10),
                LinearProgressIndicator(
                  value: progressVal.clamp(0.0, 1.0),
                  backgroundColor: isDark ? Colors.white10 : Colors.black12,
                  color: theme.primary,
                  minHeight: 12,
                  borderRadius: BorderRadius.circular(6),
                ),
                const SizedBox(height: 10),
                Text(
                  agac["mesaj"]!,
                  style: TextStyle(
                    fontSize: 13,
                    color: isDark ? Colors.white70 : Colors.black54,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
          IosGlassCard(
            isDark: isDark,
            themeData: theme,
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    DropdownButton<int>(
                      value: _seciliIndex < _zikirler.length ? _seciliIndex : 0,
                      dropdownColor: isDark ? theme.cardDark : theme.cardLight,
                      items: List.generate(_zikirler.length, (idx) {
                        return DropdownMenuItem(
                          value: idx,
                          child: Text(
                            _zikirler[idx]["ad"],
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: isDark ? theme.textDark : theme.primary,
                            ),
                          ),
                        );
                      }),
                      onChanged: (val) {
                        if (val != null) {
                          setState(() {
                            _seciliIndex = val;
                            _counter = 0;
                          });
                        }
                      },
                    ),
                    IconButton(
                      icon: const Icon(Icons.add_circle_outline,
                          color: Colors.green),
                      onPressed: _yeniZikirEkleDiyalog,
                      tooltip: "Yeni Zikir Ekle",
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  "$_counter",
                  style: TextStyle(
                    fontSize: 64,
                    fontWeight: FontWeight.bold,
                    color: isDark ? theme.textDark : theme.primary,
                  ),
                ),
                InkWell(
                  onTap: _hedefDegistirDiyalog,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    decoration: BoxDecoration(
                      color: theme.primary.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                          color: theme.primary.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          "Hedef: $hedefSayi",
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: isDark ? theme.textDark : theme.primary,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Icon(Icons.edit, size: 16, color: theme.primary),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                GestureDetector(
                  onTap: () {
                    HapticFeedback.mediumImpact();
                    setState(() {
                      _counter++;
                      _toplamZikirSayisi++;
                    });
                    _zikirleriKaydet();
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 100),
                    width: 130,
                    height: 130,
                    decoration: BoxDecoration(
                      color: theme.primary,
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          theme.secondary,
                          theme.primary,
                        ],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: theme.primary.withValues(alpha: 0.5),
                          blurRadius: 25,
                          spreadRadius: 4,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.touch_app,
                              color: Colors.white, size: 38),
                          const SizedBox(height: 4),
                          Text(
                            mevcutzikir["ad"],
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    ElevatedButton.icon(
                      icon: const Icon(Icons.bookmark_add, size: 18),
                      label: const Text("Deftere Kaydet"),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: theme.primary,
                        foregroundColor: Colors.white,
                      ),
                      onPressed: _zikriDeftereKaydet,
                    ),
                    const SizedBox(width: 10),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.refresh,
                          color: Colors.red, size: 18),
                      label: const Text("Sıfırla",
                          style: TextStyle(color: Colors.red)),
                      onPressed: () {
                        setState(() => _counter = 0);
                      },
                    ),
                    if (_zikirler.length > 1) ...[
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.delete,
                            color: Colors.grey, size: 20),
                        onPressed: () {
                          setState(() {
                            _zikirler.removeAt(_seciliIndex);
                            _seciliIndex = 0;
                            _counter = 0;
                          });
                          _zikirleriKaydet();
                        },
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          if (_zikirDefteri.isNotEmpty) ...[
            const SizedBox(height: 14),
            IosGlassCard(
              isDark: isDark,
              themeData: theme,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "📖 Zikir Defterim & Kayıtlarım",
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                      color: isDark ? theme.textDark : theme.primary,
                    ),
                  ),
                  const Divider(),
                  ..._zikirDefteri.take(6).map((log) {
                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: Text(log["agac"] ?? "🌳",
                          style: const TextStyle(fontSize: 24)),
                      title: Text(
                        "${log['zikir']} - ${log['sayi']} Adet",
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: isDark ? Colors.white : Colors.black87,
                        ),
                      ),
                      subtitle: Text(log['tarih'] ?? ""),
                    );
                  }),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ==================== EZAN VAKTİ APP (MAIN WORKER) ====================
class EzanVaktiApp extends StatefulWidget {
  final AppThemeMode currentTheme;
  final bool isDarkMode;
  final double fontScale;
  final Function(AppThemeMode, bool) onThemeChanged;
  final Function(double) onFontScaleChanged;
  final VoidCallback onOpenOnboarding;

  const EzanVaktiApp({
    super.key,
    required this.currentTheme,
    required this.isDarkMode,
    required this.fontScale,
    required this.onThemeChanged,
    required this.onFontScaleChanged,
    required this.onOpenOnboarding,
  });

  @override
  State<EzanVaktiApp> createState() => _EzanVaktiAppState();
}

class _EzanVaktiAppState extends State<EzanVaktiApp> {
  int _aktifSayfaIndex = 0;
  String kalanSure = "00:00:00";
  String siradakiVakit = "Yükleniyor...";
  double ilerlemeOrani = 0.0;
  bool isLoading = true;

  String secilenSehir = "İstanbul";
  String secilenIlce = "Kadıköy";
  List<String> kayitliSehirler = [
    "İstanbul (Kadıköy)",
    "Malatya (Yeşilyurt)",
    "Ankara (Çankaya)"
  ];

  Map<String, String> bugununVakitleri = {
    "İmsak": "--:--",
    "Güneş": "--:--",
    "Öğle": "--:--",
    "İkindi": "--:--",
    "Akşam": "--:--",
    "Yatsı": "--:--",
  };

  Timer? _timer;
  bool _vakitOncesiUyari = false;
  double _kacDakikaOnceSlider = 15.0;
  bool _bildirimCubugu = false;
  bool _bildirimDuaHadisEkle = false;
  String _secilenDuvarKagidi = "papatya";
  String _vakitKaynagi = 'Güncelleniyor';
  final _prayerTimesService = PrayerTimesService();
  late final _prayerNotificationService =
      PrayerNotificationService(flutterLocalNotificationsPlugin);

  @override
  void initState() {
    super.initState();
    _yukleTumAyarlar().then((_) {
      ezanVakitleriniGetir();
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        _hesaplaKalanSure();
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> ezanVakitleriniGetir() async {
    setState(() => isLoading = true);
    try {
      final result = await _prayerTimesService.getToday(
        city: secilenSehir,
        district: secilenIlce,
      );
      if (!mounted) return;
      setState(() {
        bugununVakitleri = result.timings;
        _vakitKaynagi = switch (result.source) {
          PrayerTimesSource.alAdhan => 'AlAdhan · Diyanet metodu',
          PrayerTimesSource.cache => 'Bugünün kayıtlı verisi',
          PrayerTimesSource.offlineCalculation => 'Çevrimdışı Diyanet Vakti',
        };
        isLoading = false;
      });
      try {
        await _prayerNotificationService.scheduleToday(
          timings: result.timings,
          enabled: _vakitOncesiUyari,
          minutesBefore: _kacDakikaOnceSlider.round(),
        );
      } on Exception catch (error) {
        debugPrint('Bildirimler planlanamadı: $error');
      }
      if (_bildirimCubugu) await updateVakitBilgiCubugu(result.timings);
      _hesaplaKalanSure();
      return;
    } catch (e) {
      debugPrint("Vakit verisi alma hatası, çevrimdışı motor çalıştırılıyor: $e");
    }
    if (!mounted) return;
    final offlineTimings = PrayerTimesService.calculateOffline(secilenSehir, DateTime.now());
    setState(() {
      bugununVakitleri = offlineTimings;
      _vakitKaynagi = 'Çevrimdışı Diyanet Vakti';
      isLoading = false;
    });
    _hesaplaKalanSure();
  }

  void _hesaplaKalanSure() {
    final simdi = DateTime.now();
    DateTime? enYakinVakit;
    String vakitIsmi = "";
    DateTime? oncekiVakit;

    Map<String, DateTime> vakitDateTimes = {};
    bugununVakitleri.forEach((key, value) {
      if (value != "--:--") {
        vakitDateTimes[key] = parseTime(value);
      }
    });

    List<MapEntry<String, DateTime>> siraliVakitler = vakitDateTimes.entries
        .toList()
      ..sort((a, b) => a.value.compareTo(b.value));

    for (int i = 0; i < siraliVakitler.length; i++) {
      if (siraliVakitler[i].value.isAfter(simdi)) {
        enYakinVakit = siraliVakitler[i].value;
        vakitIsmi = siraliVakitler[i].key;
        oncekiVakit = i == 0
            ? siraliVakitler.last.value.subtract(const Duration(days: 1))
            : siraliVakitler[i - 1].value;
        break;
      }
    }

    if (enYakinVakit == null && siraliVakitler.isNotEmpty) {
      enYakinVakit = siraliVakitler.first.value.add(const Duration(days: 1));
      vakitIsmi = siraliVakitler.first.key;
      oncekiVakit = siraliVakitler.last.value;
    }

    if (enYakinVakit == null || oncekiVakit == null) return;

    Duration kalanSureDuration = enYakinVakit.difference(simdi);
    Duration toplamSure = enYakinVakit.difference(oncekiVakit);

    if (mounted) {
      setState(() {
        siradakiVakit = vakitIsmi;
        ilerlemeOrani = (kalanSureDuration.inSeconds / toplamSure.inSeconds)
            .clamp(0.0, 1.0);
        kalanSure =
            "${kalanSureDuration.inHours.toString().padLeft(2, '0')}:${(kalanSureDuration.inMinutes % 60).toString().padLeft(2, '0')}:${(kalanSureDuration.inSeconds % 60).toString().padLeft(2, '0')}";
      });

      unawaited(HomeWidgetService.update(
        location: '$secilenSehir ($secilenIlce)',
        nextPrayer: 'Sıradaki Vakit: $siradakiVakit',
        countdown: kalanSure,
        dailyHadith:
            "📖 Günün Hadisi: 'Kolaylaştırınız, zorlaştırmayınız; müjdeleyiniz, nefret ettirmeyiniz.' (Buhârî)",
        targetTime: enYakinVakit,
      ));
    }
  }

  DateTime parseTime(String timeStr) {
    List<String> parcalar = timeStr.split(":");
    final simdi = DateTime.now();
    return DateTime(
      simdi.year,
      simdi.month,
      simdi.day,
      int.parse(parcalar[0]),
      int.parse(parcalar[1]),
    );
  }

  Future<void> _kaydetTumAyarlar() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('vakit_oncesi_uyari', _vakitOncesiUyari);
    await prefs.setDouble('kac_dakika_once_slider', _kacDakikaOnceSlider);
    await prefs.setBool('bildirim_cubugu', _bildirimCubugu);
    await prefs.setBool('bildirim_dua_hadis_ekle', _bildirimDuaHadisEkle);
    await prefs.setString('secilen_sehir', secilenSehir);
    await prefs.setString('secilen_ilce', secilenIlce);
    await prefs.setStringList('kayitli_sehirler', kayitliSehirler);
  }

  Future<void> _yukleTumAyarlar() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _vakitOncesiUyari = prefs.getBool('vakit_oncesi_uyari') ?? true;
      _kacDakikaOnceSlider = prefs.getDouble('kac_dakika_once_slider') ?? 15.0;
      _bildirimCubugu = prefs.getBool('bildirim_cubugu') ?? true;
      _bildirimDuaHadisEkle = prefs.getBool('bildirim_dua_hadis_ekle') ?? true;
      secilenSehir = prefs.getString('secilen_sehir') ?? "İstanbul";
      secilenIlce = prefs.getString('secilen_ilce') ?? "Kadıköy";
      kayitliSehirler = prefs.getStringList('kayitli_sehirler') ??
          ["İstanbul (Kadıköy)", "Malatya (Yeşilyurt)", "Ankara (Çankaya)"];
    });
  }

  void _sehirVeIlceSecimiDiyalog() {
    String tempIl = secilenSehir;
    String tempIlce = secilenIlce;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDiyalogState) {
            final ilceler = TurkiyeSehirler.getIlceler(tempIl);
            if (!ilceler.contains(tempIlce)) {
              tempIlce = ilceler.first;
            }

            final theme = AppThemeData.getTheme(widget.currentTheme);
            final isDark = widget.isDarkMode;

            return AlertDialog(
              backgroundColor: isDark ? theme.cardDark : theme.cardLight,
              title: Text(
                "81 İl & İlçe Yönetimi 📍",
                style:
                    TextStyle(color: isDark ? theme.textDark : theme.primary),
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text("İl Seçin (81 İl):",
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isDark ? theme.textDark : theme.primary)),
                    const SizedBox(height: 6),
                    DropdownButton<String>(
                      isExpanded: true,
                      value: tempIl,
                      dropdownColor: isDark ? theme.cardDark : theme.cardLight,
                      items: TurkiyeSehirler.iller.map((il) {
                        return DropdownMenuItem(
                          value: il,
                          child: Text(il,
                              style: TextStyle(
                                  color:
                                      isDark ? theme.textDark : theme.primary)),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setDiyalogState(() {
                            tempIl = val;
                            tempIlce = TurkiyeSehirler.getIlceler(val).first;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 10),
                    Text("İlçe Seçin:",
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isDark ? theme.textDark : theme.primary)),
                    const SizedBox(height: 6),
                    DropdownButton<String>(
                      isExpanded: true,
                      value: tempIlce,
                      dropdownColor: isDark ? theme.cardDark : theme.cardLight,
                      items: ilceler.map((ilce) {
                        return DropdownMenuItem(
                          value: ilce,
                          child: Text(ilce,
                              style: TextStyle(
                                  color:
                                      isDark ? theme.textDark : theme.primary)),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setDiyalogState(() {
                            tempIlce = val;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: theme.primary,
                        foregroundColor: Colors.white,
                      ),
                      icon: const Icon(Icons.push_pin),
                      label: const Text("Bu Konumu Sabitle (Ana Şehir)"),
                      onPressed: () {
                        setState(() {
                          secilenSehir = tempIl;
                          secilenIlce = tempIlce;
                          String entry = "$tempIl ($tempIlce)";
                          if (!kayitliSehirler.contains(entry)) {
                            kayitliSehirler.add(entry);
                          }
                        });
                        _kaydetTumAyarlar();
                        ezanVakitleriniGetir();
                        Navigator.pop(context);
                      },
                    ),
                    const Divider(height: 24),
                    Text("Kayıtlı Konumlarınız:",
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: isDark ? theme.textDark : theme.primary)),
                    ...kayitliSehirler.map((item) {
                      bool isCurrent = item.contains(secilenSehir);
                      return ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          item,
                          style: TextStyle(
                            fontWeight:
                                isCurrent ? FontWeight.bold : FontWeight.normal,
                            color: isDark ? theme.textDark : theme.primary,
                          ),
                        ),
                        leading: Icon(
                            isCurrent ? Icons.push_pin : Icons.location_city,
                            color: theme.primary),
                        trailing: kayitliSehirler.length > 1
                            ? IconButton(
                                icon: const Icon(Icons.delete,
                                    size: 20, color: Colors.red),
                                onPressed: () {
                                  setDiyalogState(() {
                                    kayitliSehirler.remove(item);
                                  });
                                  _kaydetTumAyarlar();
                                },
                              )
                            : null,
                        onTap: () {
                          List<String> parts =
                              item.replaceAll(")", "").split(" (");
                          if (parts.length == 2) {
                            setState(() {
                              secilenSehir = parts[0];
                              secilenIlce = parts[1];
                            });
                            _kaydetTumAyarlar();
                            ezanVakitleriniGetir();
                            Navigator.pop(context);
                          }
                        },
                      );
                    }),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("Kapat"),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _ayarlarMenusunuAc() {
    final scope = AppThemeScope.of(context);
    final isDark = scope.isDark;
    final activeTheme = scope.themeData;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor:
          isDark ? activeTheme.backgroundDark : activeTheme.backgroundLight,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final currentScope = AppThemeScope.of(context);
            final activeTheme = currentScope.themeData;
            final theme = activeTheme;
            final isDark = currentScope.isDark;
            final currentMode = currentScope.themeMode;

            return DraggableScrollableSheet(
              initialChildSize: 0.76,
              minChildSize: 0.42,
              maxChildSize: 0.95,
              expand: false,
              builder: (context, scrollController) {
                return SingleChildScrollView(
                  controller: scrollController,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "🌸 Ayarlar",
                              style: TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                                color: isDark
                                    ? activeTheme.textDark
                                    : activeTheme.primary,
                              ),
                            ),
                            IconButton(
                              icon:
                                  Icon(Icons.close, color: activeTheme.primary),
                              onPressed: () => Navigator.pop(context),
                            ),
                          ],
                        ),
                        const Divider(),
                        const SizedBox(height: 10),
                        Text(
                          "Temalar 🎨",
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.bold,
                            color: isDark
                                ? activeTheme.textDark
                                : activeTheme.primary,
                          ),
                        ),
                        const SizedBox(height: 10),
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: AppThemeMode.values.map((tMode) {
                              final tData = AppThemeData.getTheme(tMode);
                              final isSelected = currentMode == tMode;

                              return Padding(
                                padding: const EdgeInsets.only(right: 8.0),
                                child: ChoiceChip(
                                  label: Text(tData.name),
                                  selected: isSelected,
                                  selectedColor:
                                      tData.primary.withValues(alpha: 0.4),
                                  onSelected: (val) {
                                    if (val) {
                                      currentScope.onThemeChanged(
                                          tMode, isDark);
                                      setState(() {});
                                      setModalState(() {});
                                      Navigator.pop(context);
                                      Future.delayed(
                                          const Duration(milliseconds: 100),
                                          () {
                                        _ayarlarMenusunuAc();
                                      });
                                    }
                                  },
                                ),
                              );
                            }).toList(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          "🖼️ Arka Plan Desenleri / Görseller 🌼",
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.bold,
                            color: isDark
                                ? activeTheme.textDark
                                : activeTheme.primary,
                          ),
                        ),
                        const SizedBox(height: 10),
                        SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: [
                              ChoiceChip(
                                label: const Text("Düz Renk 🎨"),
                                selected: _secilenDuvarKagidi == "yok",
                                selectedColor:
                                    activeTheme.primary.withValues(alpha: 0.4),
                                onSelected: (val) {
                                  if (val) {
                                    setState(() => _secilenDuvarKagidi = "yok");
                                    setModalState(() {});
                                  }
                                },
                              ),
                              const SizedBox(width: 8),
                              ChoiceChip(
                                label: const Text("Papatya Bahçesi 🌼"),
                                selected: _secilenDuvarKagidi == "papatya",
                                selectedColor:
                                    activeTheme.primary.withValues(alpha: 0.4),
                                onSelected: (val) {
                                  if (val) {
                                    setState(
                                        () => _secilenDuvarKagidi = "papatya");
                                    setModalState(() {});
                                  }
                                },
                              ),
                              const SizedBox(width: 8),
                              ChoiceChip(
                                label: const Text("Ebru Sanatı 🎨"),
                                selected: _secilenDuvarKagidi == "ebru",
                                selectedColor:
                                    activeTheme.primary.withValues(alpha: 0.4),
                                onSelected: (val) {
                                  if (val) {
                                    setState(
                                        () => _secilenDuvarKagidi = "ebru");
                                    setModalState(() {});
                                  }
                                },
                              ),
                              const SizedBox(width: 8),
                              ChoiceChip(
                                label: const Text("Cami & Hilal 🌙"),
                                selected: _secilenDuvarKagidi == "cami",
                                selectedColor:
                                    activeTheme.primary.withValues(alpha: 0.4),
                                onSelected: (val) {
                                  if (val) {
                                    setState(
                                        () => _secilenDuvarKagidi = "cami");
                                    setModalState(() {});
                                  }
                                },
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        SwitchListTile(
                          title: Text("🌙 Gece Modu (Koyu Tema)",
                              style: TextStyle(
                                  color: isDark
                                      ? activeTheme.textDark
                                      : activeTheme.primary)),
                          subtitle: const Text(
                              "Tüm kutucukları ve arka planı karanlık renklere bürür"),
                          value: isDark,
                          onChanged: (val) {
                            currentScope.onThemeChanged(currentMode, val);
                            setState(() {});
                            setModalState(() {});
                            Navigator.pop(context);
                            Future.delayed(const Duration(milliseconds: 100),
                                () {
                              _ayarlarMenusunuAc();
                            });
                          },
                        ),
                        const Divider(),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "🔤 Yazı Boyutu (Font Ölçeği)",
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: isDark
                                    ? activeTheme.textDark
                                    : activeTheme.primary,
                              ),
                            ),
                            Text(
                              "%${(currentScope.fontScale.clamp(0.80, 1.40) * 100).round()}",
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.bold,
                                color: isDark
                                    ? activeTheme.textDark
                                    : activeTheme.primary,
                              ),
                            ),
                          ],
                        ),
                        Slider(
                          value: currentScope.fontScale.clamp(0.80, 1.40),
                          min: 0.80,
                          max: 1.40,
                          divisions: 12,
                          activeColor: activeTheme.primary,
                          onChanged: (val) {
                            currentScope.onFontScaleChanged(val);
                            setModalState(() {});
                            setState(() {});
                          },
                        ),
                        const Divider(),
                        SwitchListTile.adaptive(
                          contentPadding: EdgeInsets.zero,
                          title: Text("Vakit öncesi hatırlatma",
                              style: TextStyle(
                                  color:
                                      isDark ? theme.textDark : theme.primary)),
                          subtitle:
                              const Text("Uygulama kapalıyken de bildirim al"),
                          value: _vakitOncesiUyari,
                          onChanged: (val) async {
                            if (val) {
                              await Permission.notification.request();
                              await Permission.scheduleExactAlarm.request();
                              await Permission.ignoreBatteryOptimizations.request();
                            }
                            setModalState(() => _vakitOncesiUyari = val);
                            setState(() => _vakitOncesiUyari = val);
                            await _kaydetTumAyarlar();
                            await _prayerNotificationService.scheduleToday(
                              timings: bugununVakitleri,
                              enabled: val,
                              minutesBefore: _kacDakikaOnceSlider.round(),
                            );
                          },
                        ),
                        if (_vakitOncesiUyari) ...[
                          Text(
                              "Hatırlatma: ${_kacDakikaOnceSlider.round()} dakika önce",
                              style: TextStyle(
                                  color:
                                      isDark ? theme.textDark : theme.primary)),
                          Slider(
                            value: _kacDakikaOnceSlider,
                            min: 5,
                            max: 60,
                            divisions: 11,
                            label: '${_kacDakikaOnceSlider.round()} dk',
                            activeColor: theme.primary,
                            onChanged: (val) {
                              setModalState(() => _kacDakikaOnceSlider = val);
                              setState(() => _kacDakikaOnceSlider = val);
                            },
                            onChangeEnd: (val) async {
                              await _kaydetTumAyarlar();
                              await _prayerNotificationService.scheduleToday(
                                timings: bugununVakitleri,
                                enabled: true,
                                minutesBefore: val.round(),
                              );
                            },
                          ),
                        ],
                        const Divider(),
                        SwitchListTile.adaptive(
                          contentPadding: EdgeInsets.zero,
                          title: Text("Sabit Vakit Bilgi Çubuğu",
                              style: TextStyle(
                                  color: isDark
                                      ? theme.textDark
                                      : theme.primary)),
                          subtitle:
                              const Text("Namaz vakitleri çubukta gösterilsin"),
                          value: _bildirimCubugu,
                          onChanged: (val) async {
                            setModalState(() => _bildirimCubugu = val);
                            setState(() => _bildirimCubugu = val);
                            _kaydetTumAyarlar();
                            if (val) {
                              updateVakitBilgiCubugu(bugununVakitleri);
                            } else {
                              await cancelNotification();
                            }
                          },
                        ),
                        const Divider(),
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: activeTheme.primary.withValues(alpha: 0.15),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(Icons.widgets, color: activeTheme.primary, size: 22),
                          ),
                          title: Text(
                            "📲 Masaüstü Widget'ı Ekleyin",
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: isDark ? activeTheme.textDark : activeTheme.primary,
                            ),
                          ),
                          subtitle: Text(
                            "Ana ekrana canlı namaz saatleri ve Günün Hadisi çubuğunu yerleştirin",
                            style: TextStyle(
                              fontSize: 13,
                              color: isDark ? Colors.white70 : Colors.black54,
                            ),
                          ),
                          trailing: Icon(Icons.arrow_forward_ios, size: 16, color: activeTheme.primary),
                          onTap: () {
                            HomeWidgetService.update(
                              location: "$secilenSehir ($secilenIlce)",
                              nextPrayer: siradakiVakit,
                              countdown: kalanSure,
                            );
                            showDialog(
                              context: context,
                              builder: (ctx) => AlertDialog(
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                                title: const Text("📲 Masaüstü Widget Rehberi"),
                                content: const Text(
                                  "1. Telefonunuzun ana ekranında boş bir alana basılı tutun.\n"
                                  "2. Açılan menüden 'Widget'lar' seçeneğine tıklayın.\n"
                                  "3. 'EZAN VAKTİ' uygulamasını bulun ve ekrana sürükleyin!\n\n"
                                  "Widget canlı namaz vakitlerini ve Günün Hadisi'ni telefonunuzun ekranında gösterecektir.",
                                ),
                                actions: [
                                  ElevatedButton(
                                    style: ElevatedButton.styleFrom(backgroundColor: activeTheme.primary),
                                    onPressed: () => Navigator.pop(ctx),
                                    child: const Text("Anladım", style: TextStyle(color: Colors.white)),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                        const Divider(),
                        ListTile(
                          title: Text("📍 Konum ve 81 İl/İlçe Yönetimi",
                              style: TextStyle(
                                  color: widget.isDarkMode
                                      ? theme.textDark
                                      : theme.primary)),
                          subtitle: Text("$secilenSehir ($secilenIlce)"),
                          trailing: Icon(Icons.edit_location_alt,
                              color: theme.primary),
                          onTap: () {
                            Navigator.pop(context);
                            _sehirVeIlceSecimiDiyalog();
                          },
                        ),
                        const SizedBox(height: 20),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final scope = AppThemeScope.of(context);
    final theme = scope.themeData;
    final isDark = scope.isDark;

    String? assetImage;
    if (_secilenDuvarKagidi == "papatya") {
      assetImage = "assets/images/bg_papatya.jpg";
    }
    if (_secilenDuvarKagidi == "ebru") {
      assetImage = "assets/images/bg_ebru.jpg";
    }
    if (_secilenDuvarKagidi == "cami") {
      assetImage = "assets/images/bg_mosque.jpg";
    }

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: isDark ? theme.bgGradientDark : theme.bgGradientLight,
          ),
          image: assetImage != null
              ? DecorationImage(
                  image: AssetImage(assetImage),
                  fit: BoxFit.cover,
                  opacity: isDark ? 0.22 : 0.35,
                )
              : null,
        ),
        child: SafeArea(
          child: Column(
            children: [
              // HEADER BAR
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                decoration: BoxDecoration(
                  color: isDark
                      ? theme.cardDark.withValues(alpha: 0.9)
                      : theme.cardLight.withValues(alpha: 0.9),
                  border: Border(
                    bottom: BorderSide(
                      color: isDark
                          ? Colors.white12
                          : theme.primary.withValues(alpha: 0.2),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: InkWell(
                        onTap: () {
                          HapticFeedback.selectionClick();
                          _sehirVeIlceSecimiDiyalog();
                        },
                        child: Row(
                          children: [
                            Icon(Icons.location_on,
                                color: theme.primary, size: 20),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                "$secilenSehir ($secilenIlce)",
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  color:
                                      isDark ? theme.textDark : theme.textLight,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              DateFormat('d MMMM yyyy', 'tr_TR')
                                  .format(DateTime.now()),
                              style: TextStyle(
                                fontSize: 12,
                                color: isDark ? Colors.white60 : Colors.black54,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    IconButton(
                      icon: Icon(Icons.settings, color: theme.primary),
                      onPressed: () {
                        HapticFeedback.selectionClick();
                        _ayarlarMenusunuAc();
                      },
                    ),
                  ],
                ),
              ),

              Expanded(
                child: isLoading
                    ? Center(
                        child: CircularProgressIndicator(color: theme.primary))
                    : IndexedStack(
                        index: _aktifSayfaIndex,
                        children: [
                          AnaDashboardSayfasi(
                            kalanSure: kalanSure,
                            siradakiVakit: siradakiVakit,
                            vakitKaynagi: _vakitKaynagi,
                            ilerlemeOrani: ilerlemeOrani,
                            isDark: isDark,
                            themeData: theme,
                            bugununVakitleri: bugununVakitleri,
                          ),
                          VakitlerListeSayfasi(
                            bugununVakitleri: bugununVakitleri,
                            aktifVakit: siradakiVakit,
                            isDark: isDark,
                            themeData: theme,
                          ),
                          KuranWebView(isDark: isDark),
                          KibleWebView(isDark: isDark, themeData: theme),
                          ZikirmatikPage(isDark: isDark, themeData: theme),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          boxShadow: [
            BoxShadow(
              color: isDark
                  ? Colors.black45
                  : theme.primary.withValues(alpha: 0.12),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: _aktifSayfaIndex,
          onTap: (idx) {
            HapticFeedback.selectionClick();
            setState(() => _aktifSayfaIndex = idx);
          },
          backgroundColor: isDark ? theme.cardDark : theme.cardLight,
          selectedItemColor: theme.primary,
          unselectedItemColor: isDark ? Colors.white38 : Colors.black45,
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_rounded),
              label: 'Ana Sayfa',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.access_time_rounded),
              label: 'Vakitler',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.menu_book_rounded),
              label: 'Kur\'an',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.explore_rounded),
              label: 'Kıble',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.radio_button_checked_rounded),
              label: 'Zikirmatik',
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== ANA DASHBOARD (2x2 KARE KUTU DÜZENİ + ARAPÇA/TÜRKÇE/ANLAM DUA KARTI) ====================
class AnaDashboardSayfasi extends StatefulWidget {
  final String kalanSure, siradakiVakit;
  final String vakitKaynagi;
  final double ilerlemeOrani;
  final bool isDark;
  final AppThemeData themeData;
  final Map<String, String> bugununVakitleri;

  const AnaDashboardSayfasi({
    super.key,
    required this.kalanSure,
    required this.siradakiVakit,
    required this.vakitKaynagi,
    required this.ilerlemeOrani,
    required this.isDark,
    required this.themeData,
    required this.bugununVakitleri,
  });

  @override
  State<AnaDashboardSayfasi> createState() => _AnaDashboardSayfasiState();
}

class _AnaDashboardSayfasiState extends State<AnaDashboardSayfasi> {
  Map<String, dynamic> bugununIcerikleri = {
    "ayet": "Yükleniyor...",
    "hadis": "Yükleniyor...",
    "dua": {
      "arapca":
          "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ",
      "okunusu": "Rabbena atina fid-dunya haseneten...",
      "anlamı": "Rabbimiz! Bize dünyada da iyilik ver, ahirette de iyilik ver."
    },
    "esma": "Yükleniyor...",
  };

  @override
  void initState() {
    super.initState();
    _icerikleriGetir();
  }

  Future<void> _icerikleriGetir() async {
    final res = await OnlineIcerikServisi.getGununIcerikleri();
    if (mounted) {
      setState(() {
        bugununIcerikleri = res;
      });
    }
  }

  void _paylasIcerik(String baslik, String icerik) {
    HapticFeedback.lightImpact();
    const playStoreUrl =
        "https://play.google.com/store/apps/details?id=com.aysenuryesilova.ezanvakti";
    final mesaj =
        "🌸 Ezan Vakti - $baslik 🌸\n\n$icerik\n\n📲 Ezan Vakti uygulamasını Google Play Store'dan indirin:\n$playStoreUrl";
    Share.share(mesaj);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = widget.isDark;
    final theme = widget.themeData;

    final duaObj = bugununIcerikleri["dua"] is Map
        ? bugununIcerikleri["dua"] as Map<String, String>
        : {
            "arapca": "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً",
            "okunusu": "Rabbena atina fid-dunya...",
            "anlamı": "Rabbimiz! Bize iyilik ver."
          };

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Column(
        children: [
          const SizedBox(height: 6),

          // TIMER WIDGET
          IosGlassCard(
            isDark: isDark,
            themeData: theme,
            padding: const EdgeInsets.all(22),
            child: Column(
              children: [
                Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 190,
                      height: 190,
                      child: CircularProgressIndicator(
                        value: widget.ilerlemeOrani,
                        strokeWidth: 14,
                        valueColor: AlwaysStoppedAnimation(theme.primary),
                        backgroundColor: isDark
                            ? Colors.white10
                            : theme.secondary.withValues(alpha: 0.3),
                      ),
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          widget.kalanSure,
                          style: TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 2,
                            color: isDark ? theme.textDark : theme.textLight,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          "Sıradaki: ${widget.siradakiVakit}",
                          style: TextStyle(
                            color: theme.primary,
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          widget.vakitKaynagi,
                          style: TextStyle(
                            color: isDark ? Colors.white60 : Colors.black54,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 10),

          // 2x2 KARE KUTU DÜZENİ (AYET, HADİS, DUA, ESMA)
          Row(
            children: [
              Expanded(
                child: _kareKutuCard(
                  "Günün Ayeti 🌸",
                  bugununIcerikleri["ayet"]?.toString() ?? "",
                  isDark,
                  theme,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _kareKutuCard(
                  "Günün Hadisi 🌷",
                  bugununIcerikleri["hadis"]?.toString() ?? "",
                  isDark,
                  theme,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _kareDuaCard(
                  "Günün Duası 🌺",
                  duaObj,
                  isDark,
                  theme,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _kareKutuCard(
                  "Günün Esması 🦋",
                  bugununIcerikleri["esma"]?.toString() ?? "",
                  isDark,
                  theme,
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),
        ],
      ),
    );
  }

  // KARE KUTU WIDGET (AYET, HADİS, ESMA İÇİN)
  Widget _kareKutuCard(
    String baslik,
    String icerik,
    bool isDark,
    AppThemeData theme,
  ) {
    return IosGlassCard(
      isDark: isDark,
      themeData: theme,
      margin: EdgeInsets.zero,
      padding: const EdgeInsets.all(14),
      onTap: () => _paylasIcerik(baslik, icerik),
      child: SizedBox(
        height: 160,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    baslik,
                    style: TextStyle(
                      color: isDark ? theme.textDark : theme.textLight,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Icon(Icons.share_rounded, size: 18, color: theme.primary),
              ],
            ),
            const Divider(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: Text(
                  icerik,
                  style: TextStyle(
                    color: isDark ? Colors.white : Colors.black87,
                    fontSize: 13,
                    height: 1.35,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // DUA KUTUSU WIDGET (ARAPÇA, TÜRKÇE OKUNUŞU VE ANLAMI)
  Widget _kareDuaCard(
    String baslik,
    Map<String, String> duaMap,
    bool isDark,
    AppThemeData theme,
  ) {
    final paylasMetin =
        "${duaMap['arapca']}\n${duaMap['okunusu']}\n${duaMap['anlamı']}";

    return IosGlassCard(
      isDark: isDark,
      themeData: theme,
      margin: EdgeInsets.zero,
      padding: const EdgeInsets.all(14),
      onTap: () => _paylasIcerik(baslik, paylasMetin),
      child: SizedBox(
        height: 160,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    baslik,
                    style: TextStyle(
                      color: isDark ? theme.textDark : theme.textLight,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Icon(Icons.share_rounded, size: 18, color: theme.primary),
              ],
            ),
            const Divider(height: 10),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      duaMap['arapca'] ?? "",
                      style: TextStyle(
                        color: isDark ? theme.textDark : theme.primary,
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.right,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      "🔤 ${duaMap['okunusu'] ?? ""}",
                      style: TextStyle(
                        color: isDark ? Colors.white70 : Colors.black54,
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      "📜 ${duaMap['anlamı'] ?? ""}",
                      style: TextStyle(
                        color: isDark ? Colors.white : Colors.black87,
                        fontSize: 12,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==================== VAKİTLER LİSTESİ ====================
class VakitlerListeSayfasi extends StatelessWidget {
  final Map<String, String> bugununVakitleri;
  final String aktifVakit;
  final bool isDark;
  final AppThemeData themeData;

  const VakitlerListeSayfasi({
    super.key,
    required this.bugununVakitleri,
    required this.aktifVakit,
    required this.isDark,
    required this.themeData,
  });

  @override
  Widget build(BuildContext context) {
    List<MapEntry<String, String>> vakitler = bugununVakitleri.entries.toList();

    final Map<String, int> sirala = {
      "İmsak": 0,
      "Güneş": 1,
      "Öğle": 2,
      "İkindi": 3,
      "Akşam": 4,
      "Yatsı": 5
    };
    vakitler.sort((a, b) {
      int indexA = sirala[a.key] ?? 99;
      int indexB = sirala[b.key] ?? 99;
      return indexA.compareTo(indexB);
    });

    return ListView.builder(
      padding: const EdgeInsets.all(18),
      itemCount: vakitler.length,
      itemBuilder: (context, index) {
        final entry = vakitler[index];
        bool isCurrent = aktifVakit.startsWith(entry.key);

        return IosGlassCard(
          isDark: isDark,
          themeData: themeData,
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                entry.key,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: isCurrent
                      ? themeData.primary
                      : (isDark ? Colors.white : Colors.black87),
                ),
              ),
              Text(
                entry.value,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: isCurrent
                      ? themeData.primary
                      : (isDark ? Colors.white70 : Colors.black87),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
