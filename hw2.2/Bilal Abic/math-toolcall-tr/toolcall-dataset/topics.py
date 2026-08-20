"""Matematik taksonomisi: alt alan -> konu, ve arac cagirma senaryolari.

Veri seti SADECE matematik uzerine kuruludur. Yeni konu eklemek icin
sadece asagidaki DOMAINS sozlugune satir ekle.
"""

DOMAINS: dict[str, list[str]] = {
    "aritmetik": [
        "dort islem ve islem onceligi",
        "yuzde, indirim ve kdv hesabi",
        "oran-oranti ve olcek",
        "kesir ve ondalik donusumleri",
        "us ve kok islemleri",
        "ortalama hiz - yol - zaman",
    ],
    "cebir": [
        "birinci dereceden denklem cozme",
        "ikinci dereceden denklem ve diskriminant",
        "denklem sistemleri (2-3 bilinmeyen)",
        "esitsizlik cozumu ve aralik gosterimi",
        "polinom carpanlara ayirma",
        "rasyonel ifade sadelestirme",
        "logaritma ve ustel denklemler",
        "diziler ve seriler (aritmetik/geometrik)",
    ],
    "geometri": [
        "ucgen alan, cevre ve benzerlik",
        "pisagor ve dik ucgen bagintilari",
        "cember, yay ve daire dilimi",
        "cokgen ic-dis aci hesabi",
        "prizma ve silindir hacim-yuzey alani",
        "koni ve kure hacim-yuzey alani",
        "analitik geometri (dogru, egim, uzaklik)",
    ],
    "trigonometri": [
        "temel trigonometrik oranlar",
        "birim cember ve aci donusumleri",
        "sinus ve kosinus teoremi",
        "trigonometrik denklem cozme",
        "periyot, genlik ve grafik yorumu",
    ],
    "analiz": [
        "limit hesabi ve belirsizlikler",
        "turev alma kurallari (carpim, bolum, zincir)",
        "turev uygulamasi: maksimum-minimum",
        "belirsiz integral",
        "belirli integral ve alan hesabi",
        "donel cisim hacmi",
        "diferansiyel denklem (basit)",
    ],
    "olasilik_kombinatorik": [
        "permutasyon ve kombinasyon",
        "basit ve bilesik olasilik",
        "kosullu olasilik ve bayes",
        "binom ve normal dagilim",
        "beklenen deger hesabi",
    ],
    "istatistik": [
        "merkezi egilim (ortalama, medyan, mod)",
        "yayilim (varyans, standart sapma, ceyrekler)",
        "korelasyon ve regresyon",
        "hipotez testi ve p-degeri",
        "guven araligi hesabi",
        "veri kumesi ozetleme ve aykiri deger",
    ],
    "sayi_teorisi": [
        "ebob-ekok hesabi",
        "asal sayilar ve carpanlara ayirma",
        "bolunebilme kurallari",
        "mod aritmetigi ve kalan bulma",
        "taban donusumleri (2, 8, 10, 16)",
    ],
    "lineer_cebir": [
        "matris toplama ve carpma",
        "determinant ve ters matris",
        "lineer denklem sistemi (gauss)",
        "vektor islemleri (nokta, capraz carpim)",
        "ozdeger ve ozvektor",
    ],
    "finansal_matematik": [
        "basit ve bilesik faiz",
        "kredi taksit ve amortisman tablosu",
        "bugunku deger - gelecek deger",
        "yillik getiri ve enflasyon duzeltmesi",
        "kar-zarar ve maliyet analizi",
    ],
    "birim_olcu": [
        "uzunluk, alan, hacim donusumleri",
        "kutle, sicaklik ve basinc donusumleri",
        "hiz ve zaman birimleri",
        "bilimsel gosterim ve anlamli rakam",
    ],
    "ayrik_matematik": [
        "kume islemleri ve venn semasi",
        "mantik onermeleri ve dogruluk tablosu",
        "graf temelleri (derece, en kisa yol)",
        "ozyineleme ve tumevarim",
    ],
    "optimizasyon": [
        "dogrusal programlama (basit)",
        "kisitli maksimum-minimum problemi",
        "en kucuk kareler uydurma",
    ],
}

# Modelin ogrenmesi gereken arac cagirma davranislari.
SCENARIOS: dict[str, str] = {
    "tek_cagri": "Tek bir matematik araci, dogru parametrelerle bir kez cagrilir.",
    "zincirli_cagri": "Ikinci cagrinin parametresi birinci cagrinin sonucundan gelir; sirali calisir.",
    "paralel_cagri": "Birbirinden bagimsiz 2-3 hesap ayni anda yapilir, sonra karsilastirilir.",
    "eksik_parametre": "Hesap icin zorunlu bir deger mesajda yok; arac CAGRILMAZ, netlestirme sorusu sorulur.",
    "arac_gereksiz": "Cevap kafadan/tanimdan verilebilir (orn. 'turev ne demek'); hicbir arac cagrilmaz.",
    "yanlis_arac_tuzagi": "Benzer isimli araclar vardir (orn. solve_equation vs evaluate_expression); dogru olan secilir.",
    "hata_yonetimi": "Arac hata dondurur (tanimsiz, negatif diskriminant, sifira bolme); model bunu aciklar.",
    "cok_adimli_gorev": "Kullanici tek cumlede birden fazla hesap ister; 3+ cagri ile tamamlanir.",
}

DIFFICULTIES = ["kolay", "orta", "zor"]


def all_combos() -> list[tuple[str, str]]:
    """(alt_alan, konu) ciftlerinin tamami."""
    return [(d, t) for d, topics in DOMAINS.items() for t in topics]
