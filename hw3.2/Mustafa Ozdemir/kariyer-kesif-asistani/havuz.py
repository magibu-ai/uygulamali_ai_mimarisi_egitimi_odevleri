# Kariyer kesif meslek havuzu.
# Her kayit: Turkce ad, Adzuna arama obegi (what_phrase), RIASEC kodu,
# Adzuna kategorisi ve O*NET SOC kodu.
# - riasec: O*NET resmi ilgi kodunun ilk 1-2 harfi (baskin + destekleyici).
# - kategori None ise Adzuna aramasi kategori suzgeci olmadan yapilir.
# - onet: O*NET-SOC kodu; canli O*NET sorgulari (ne is yapar, nasil baslanir,
#   buyume gorunumu) bu kodla yapilir.
# Bolum basliklari kabaca temaya goredir; kesin RIASEC her kayitta.

MESLEK_HAVUZU = [
    # Yapici / elle is
    {"ad": "Elektrik Teknisyeni", "adzuna": "electrician", "riasec": "RC", "kategori": "trade-construction-jobs", "onet": "47-2111.00"},
    {"ad": "Oto Tamircisi", "adzuna": "car mechanic", "riasec": "RC", "kategori": None, "onet": "49-3023.00"},
    {"ad": "Tesisatçı", "adzuna": "plumber", "riasec": "RC", "kategori": "trade-construction-jobs", "onet": "47-2152.00"},
    {"ad": "Kaynakçı", "adzuna": "welder", "riasec": "RC", "kategori": "trade-construction-jobs", "onet": "51-4121.00"},
    {"ad": "Marangoz", "adzuna": "carpenter", "riasec": "RC", "kategori": "trade-construction-jobs", "onet": "47-2031.00"},
    {"ad": "Makine Teknikeri", "adzuna": "mechanical technician", "riasec": "RI", "kategori": "engineering-jobs", "onet": "17-3027.00"},

    # Arastirmaci / analitik
    {"ad": "Yazılım Geliştirici", "adzuna": "software developer", "riasec": "IC", "kategori": "it-jobs", "onet": "15-1252.00"},
    {"ad": "Veri Analisti", "adzuna": "data analyst", "riasec": "IC", "kategori": "it-jobs", "onet": "15-2051.00"},
    {"ad": "Laboratuvar Teknisyeni", "adzuna": "laboratory technician", "riasec": "RI", "kategori": "scientific-qa-jobs", "onet": "29-2012.00"},
    {"ad": "Elektronik Mühendisi", "adzuna": "electronics engineer", "riasec": "RI", "kategori": "engineering-jobs", "onet": "17-2072.00"},
    {"ad": "Siber Güvenlik Uzmanı", "adzuna": "cyber security engineer", "riasec": "CI", "kategori": "it-jobs", "onet": "15-1212.00"},
    {"ad": "Kimyager", "adzuna": "chemist", "riasec": "IR", "kategori": "scientific-qa-jobs", "onet": "19-2031.00"},
    {"ad": "İnşaat Mühendisi", "adzuna": "civil engineer", "riasec": "RI", "kategori": "engineering-jobs", "onet": "17-2051.00"},
    {"ad": "Makine Mühendisi", "adzuna": "mechanical engineer", "riasec": "RI", "kategori": "engineering-jobs", "onet": "17-2141.00"},

    # Sanat ve tasarim
    {"ad": "Grafik Tasarımcı", "adzuna": "graphic designer", "riasec": "AC", "kategori": "creative-design-jobs", "onet": "27-1024.00"},
    {"ad": "UI/UX Tasarımcı", "adzuna": "ux designer", "riasec": "IA", "kategori": "creative-design-jobs", "onet": "15-1255.00"},
    {"ad": "İçerik Yazarı", "adzuna": "content writer", "riasec": "AE", "kategori": None, "onet": "27-3043.00"},
    {"ad": "Fotoğrafçı", "adzuna": "photographer", "riasec": "RA", "kategori": "creative-design-jobs", "onet": "27-4021.00"},
    {"ad": "Video Editörü", "adzuna": "video editor", "riasec": "AC", "kategori": "creative-design-jobs", "onet": "27-4032.00"},
    {"ad": "Mimar", "adzuna": "architect", "riasec": "RC", "kategori": "trade-construction-jobs", "onet": "17-1011.00"},
    {"ad": "Gazeteci", "adzuna": "journalist", "riasec": "AI", "kategori": "creative-design-jobs", "onet": "27-3023.00"},
    {"ad": "Çevirmen", "adzuna": "translator", "riasec": "CA", "kategori": "admin-jobs", "onet": "27-3091.00"},

    # Sosyal / yardim
    {"ad": "Hemşire", "adzuna": "registered nurse", "riasec": "SC", "kategori": "healthcare-nursing-jobs", "onet": "29-1141.00"},
    {"ad": "Öğretmen", "adzuna": "primary teacher", "riasec": "S", "kategori": "teaching-jobs", "onet": "25-2021.00"},
    {"ad": "Fizyoterapist", "adzuna": "physiotherapist", "riasec": "SI", "kategori": "healthcare-nursing-jobs", "onet": "29-1123.00"},
    {"ad": "Sosyal Hizmet Uzmanı", "adzuna": "social worker", "riasec": "S", "kategori": "social-work-jobs", "onet": "21-1021.00"},
    {"ad": "Diyetisyen", "adzuna": "dietitian", "riasec": "SI", "kategori": "healthcare-nursing-jobs", "onet": "29-1031.00"},
    {"ad": "Psikolog", "adzuna": "psychologist", "riasec": "SI", "kategori": "healthcare-nursing-jobs", "onet": "19-3033.00"},
    {"ad": "Doktor", "adzuna": "doctor", "riasec": "IS", "kategori": "healthcare-nursing-jobs", "onet": "29-1216.00"},
    {"ad": "Diş Hekimi", "adzuna": "dentist", "riasec": "IR", "kategori": "healthcare-nursing-jobs", "onet": "29-1021.00"},
    {"ad": "Eczacı", "adzuna": "pharmacist", "riasec": "IS", "kategori": "healthcare-nursing-jobs", "onet": "29-1051.00"},
    {"ad": "Veteriner", "adzuna": "veterinarian", "riasec": "IR", "kategori": "healthcare-nursing-jobs", "onet": "29-1131.00"},
    {"ad": "Paramedik", "adzuna": "paramedic", "riasec": "SR", "kategori": "healthcare-nursing-jobs", "onet": "29-2043.00"},

    # Girisimci / ikna
    {"ad": "Satış Temsilcisi", "adzuna": "sales representative", "riasec": "EC", "kategori": "sales-jobs", "onet": "41-4011.00"},
    {"ad": "Pazarlama Uzmanı", "adzuna": "marketing executive", "riasec": "EC", "kategori": "pr-advertising-marketing-jobs", "onet": "11-2021.00"},
    {"ad": "Dijital Pazarlama Uzmanı", "adzuna": "digital marketing executive", "riasec": "EC", "kategori": "pr-advertising-marketing-jobs", "onet": "13-1161.01"},
    {"ad": "İnsan Kaynakları Uzmanı", "adzuna": "human resources", "riasec": "EC", "kategori": "hr-jobs", "onet": "13-1071.00"},
    {"ad": "Emlak Danışmanı", "adzuna": "estate agent", "riasec": "EC", "kategori": "property-jobs", "onet": "41-9022.00"},
    {"ad": "Proje Yöneticisi", "adzuna": "project manager", "riasec": "EC", "kategori": None, "onet": "15-1299.09"},
    {"ad": "Avukat", "adzuna": "solicitor", "riasec": "EC", "kategori": "legal-jobs", "onet": "23-1011.00"},

    # Duzenli / sistemli
    {"ad": "Muhasebeci", "adzuna": "accountant", "riasec": "CE", "kategori": "accounting-finance-jobs", "onet": "13-2011.00"},
    {"ad": "Finans Analisti", "adzuna": "financial analyst", "riasec": "CE", "kategori": "accounting-finance-jobs", "onet": "13-2051.00"},
    {"ad": "Yönetici Asistanı", "adzuna": "office administrator", "riasec": "CE", "kategori": "admin-jobs", "onet": "43-6011.00"},
    {"ad": "Lojistik Sorumlusu", "adzuna": "logistics coordinator", "riasec": "CE", "kategori": "logistics-warehouse-jobs", "onet": "13-1081.00"},
    {"ad": "Banka Yetkilisi", "adzuna": "banking officer", "riasec": "EC", "kategori": "accounting-finance-jobs", "onet": "11-3031.00"},
    {"ad": "Satın Alma Uzmanı", "adzuna": "procurement specialist", "riasec": "CE", "kategori": None, "onet": "43-3061.00"},

    # Hizmet
    {"ad": "Aşçı", "adzuna": "chef", "riasec": "ER", "kategori": "hospitality-catering-jobs", "onet": "35-1011.00"},
    {"ad": "Kuaför", "adzuna": "hairdresser", "riasec": "RC", "kategori": None, "onet": "39-5012.00"},
    {"ad": "Pilot", "adzuna": "airline pilot", "riasec": "RC", "kategori": None, "onet": "53-2011.00"},
]
