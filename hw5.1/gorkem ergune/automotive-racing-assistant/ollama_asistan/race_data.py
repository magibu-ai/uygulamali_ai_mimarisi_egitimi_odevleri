"""Otomotiv/yaris senaryosu icin GOSTERIM (DEMO) verileri.

UYARI — BU VERILER GERCEK DEGILDIR:
    * Arac bilesen verileri gercek telemetri, sensor ya da takim veritabani DEGILDIR;
      akademik gosterim amaciyla elle yazilmis ORNEK degerlerdir.
    * Yaris yonetmelik verileri resmi Formula Student / FIA / SCCA kurallari DEGILDIR;
      arac cagirmayi (tool calling) gostermek icin uydurulmus KISALTILMIS ozetlerdir.

Gercek bir kararda bu verilere guvenmeyin. Resmi kaynak her zaman onceliklidir.
"""

# Bu bayrak, araclarin dondurdugu metne "demo veri" uyarisini eklemek icin kullanilir.
DATA_DISCLAIMER = "(Not: Bu bir akademik projeye ait GOSTERIM/DEMO verisidir, gercek degildir.)"


# --- Arac bilesen durumu (DEMO) --------------------------------------------
# Anahtarlar Turkce ve Ingilizce takma adlariyla eslesir; kullanici hangisini
# yazarsa yazsin bulabilsin diye ALIASES sozlugu asagida tanimlanmistir.
COMPONENTS: dict[str, dict] = {
    "brake_pads": {
        "name": "Fren balatalari",
        "status": "iyi",
        "last_inspection": "2026-07-28",
        "remaining": "kalan kalinlik ~6.5 mm (yeni: 10 mm)",
        "warning": None,
    },
    "brake_discs": {
        "name": "Fren diskleri",
        "status": "izlemede",
        "last_inspection": "2026-07-28",
        "remaining": "kalinlik 22.0 mm (asgari servis limiti 21.0 mm)",
        "warning": "Asgari limite yaklasiyor; sonraki yaris oncesi tekrar olcun.",
    },
    "tires": {
        "name": "Lastikler",
        "status": "dikkat",
        "last_inspection": "2026-08-05",
        "remaining": "diş derinligi ~3.2 mm; tahmini omur 1-2 yaris",
        "warning": "On sol lastikte duzensiz asinma var; kamber/basinc kontrolu onerilir.",
    },
    "engine_oil": {
        "name": "Motor yagi",
        "status": "iyi",
        "last_inspection": "2026-08-01",
        "remaining": "son degisimden bu yana ~1 yaris; sonraki degisim 2 yaris sonra",
        "warning": None,
    },
    "battery": {
        "name": "Aku",
        "status": "iyi",
        "last_inspection": "2026-08-10",
        "remaining": "dinlenme gerilimi 12.7 V; sarj ~%95",
        "warning": None,
    },
}

# Kullanicinin yazabilecegi serbest metni COMPONENTS anahtarina cevirir.
COMPONENT_ALIASES: dict[str, str] = {
    "brake pads": "brake_pads",
    "brake pad": "brake_pads",
    "fren balatasi": "brake_pads",
    "fren balatalari": "brake_pads",
    "balata": "brake_pads",
    "brake discs": "brake_discs",
    "brake disc": "brake_discs",
    "fren diski": "brake_discs",
    "fren diskleri": "brake_discs",
    "disk": "brake_discs",
    "tires": "tires",
    "tire": "tires",
    "tyres": "tires",
    "tyre": "tires",
    "lastik": "tires",
    "lastikler": "tires",
    "engine oil": "engine_oil",
    "oil": "engine_oil",
    "motor yagi": "engine_oil",
    "yag": "engine_oil",
    "battery": "battery",
    "aku": "battery",
    "akü": "battery",
    "batarya": "battery",
}


# --- Yaris yonetmeligi (DEMO) ----------------------------------------------
REGULATIONS: dict[str, dict] = {
    "brakes": {
        "topic": "Frenler",
        "summary": (
            "Arac, dort tekerlege de etki eden ve iki bagimsiz hidrolik devreye sahip "
            "bir fren sistemine sahip olmalidir. Tek devre arizalansa bile arac "
            "guvenli sekilde durabilmelidir. Fren testi teknik muayenenin bir parcasidir."
        ),
    },
    "tires": {
        "topic": "Lastikler",
        "summary": (
            "Yarista yalnizca beyan edilen lastik setleri kullanilabilir. Islak ve kuru "
            "hava lastikleri ayri beyan edilir. Diş derinligi asgari sinirin altina "
            "duserse lastik yaris disi birakilir."
        ),
    },
    "safety": {
        "topic": "Guvenlik",
        "summary": (
            "Surucu; kask, yanmaz tulum, HANS/boyun korumasi ve dort/bes noktali emniyet "
            "kemeri kullanmak zorundadir. Aracta ana elektrik kesme anahtari ve erisilebilir "
            "yangin sondurucu bulunmalidir. Devrilme korumasi (roll bar) zorunludur."
        ),
    },
    "electrical": {
        "topic": "Elektrik",
        "summary": (
            "Yuksek gerilim hatlari isaretlenmeli ve yalitilmali; ana kesici hem surucu hem "
            "de dis mudahale ekibi tarafindan erisilebilir olmalidir. Aku guvenli sekilde "
            "sabitlenmeli, kisa devreye karsi korunmalidir."
        ),
    },
    "driver": {
        "topic": "Surucu",
        "summary": (
            "Surucu gecerli bir yaris lisansina sahip olmali ve asgari yas sartini "
            "karsilamalidir. Surucu, araci 5 saniye icinde yardimsiz terk edebilmelidir. "
            "Kokpitte gorus ve pedal erisimi kurallara uygun olmalidir."
        ),
    },
    "technical_inspection": {
        "topic": "Teknik muayene",
        "summary": (
            "Arac yarismadan once teknik muayeneden gecmelidir: fren testi, gurultu testi, "
            "devrilme koruma kontrolu, emniyet kemeri ve elektrik kesici kontrolu. Muayeneyi "
            "gecemeyen arac piste cikamaz."
        ),
    },
}

REGULATION_ALIASES: dict[str, str] = {
    "brakes": "brakes",
    "brake": "brakes",
    "fren": "brakes",
    "frenler": "brakes",
    "tires": "tires",
    "tire": "tires",
    "tyres": "tires",
    "lastik": "tires",
    "lastikler": "tires",
    "safety": "safety",
    "guvenlik": "safety",
    "güvenlik": "safety",
    "electrical": "electrical",
    "electric": "electrical",
    "elektrik": "electrical",
    "driver": "driver",
    "surucu": "driver",
    "sürücü": "driver",
    "technical inspection": "technical_inspection",
    "technical": "technical_inspection",
    "inspection": "technical_inspection",
    "teknik muayene": "technical_inspection",
    "muayene": "technical_inspection",
    "scrutineering": "technical_inspection",
}
