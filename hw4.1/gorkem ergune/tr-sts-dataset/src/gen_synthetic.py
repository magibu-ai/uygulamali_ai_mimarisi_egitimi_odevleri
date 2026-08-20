# -*- coding: utf-8 -*-
"""
Generate ~1000 synthetic Turkish news-style sentence pairs (Star / Show /
Kanal D style: magazin, spor, ekonomi, siyaset, hava, 3. sayfa, saglik,
teknoloji, dunya) and score each pair with magibu/embeddingmagibu-200m.

Pair types & target mix (see COUNTS):
  - unrelated : two sentences from DIFFERENT topics  -> score near 0
  - related   : two DIFFERENT events from SAME topic  -> low/mid score
  - paraphrase: same event, two different phrasings    -> high score

Output: synthetic.csv (sentence1, sentence2, score, pair_type, topic)
"""
import csv
import random
import numpy as np
from sentence_transformers import SentenceTransformer

random.seed(42)
np.random.seed(42)

MODEL_ID = "magibu/embeddingmagibu-200m"
OUT_CSV = "synthetic.csv"

COUNTS = {"unrelated": 450, "related": 250, "paraphrase": 300}

# ----------------------------- slot pools -----------------------------------
TEAMS = ["Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir",
         "Adana Demirspor", "Konyaspor", "Sivasspor", "Antalyaspor",
         "Kayserispor", "Alanyaspor", "Samsunspor", "Gaziantep FK", "Rizespor",
         "Kasımpaşa", "Hatayspor", "Göztepe", "Eyüpspor", "Bodrum FK"]
CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana", "Konya",
          "Gaziantep", "Muğla", "Trabzon", "Samsun", "Eskişehir", "Mersin",
          "Kayseri", "Diyarbakır", "Sakarya", "Denizli", "Aydın", "Bolu"]
CELEBS = ["ünlü şarkıcı", "ünlü oyuncu", "popüler sunucu", "genç oyuncu",
          "sevilen sanatçı", "usta oyuncu", "fenomen isim", "ünlü model",
          "ödüllü yönetmen", "sevilen komedyen", "ünlü sunucu", "pop yıldızı"]
NAMES = ["Deniz Yılmaz", "Ece Kaya", "Kerem Demir", "Selin Aksoy", "Barış Yıldız",
         "Melis Arslan", "Can Öztürk", "Naz Şahin", "Emre Doğan", "Ada Koç"]
PARTIES = ["iktidar partisi", "ana muhalefet partisi", "koalisyon ortağı",
           "mecliste grubu bulunan bir parti"]
MINISTRIES = ["Milli Eğitim Bakanlığı", "Sağlık Bakanlığı", "Hazine ve Maliye Bakanlığı",
              "Ulaştırma Bakanlığı", "İçişleri Bakanlığı", "Sanayi ve Teknoloji Bakanlığı",
              "Tarım ve Orman Bakanlığı", "Enerji Bakanlığı"]
FOODS = ["domates", "patates", "soğan", "et", "tavuk", "peynir", "ekmek", "zeytinyağı",
         "pirinç", "çay", "kuru fasulye", "muz"]
DISEASES = ["grip", "kızamık", "zatürre", "şeker hastalığı", "yüksek tansiyon",
            "migren", "alerji", "boğaz enfeksiyonu"]
TECHS = ["yapay zeka modeli", "akıllı telefon", "elektrikli otomobil", "işletim sistemi",
         "sohbet robotu", "giyilebilir cihaz", "oyun konsolu", "dizüstü bilgisayar"]
COUNTRIES = ["ABD", "Almanya", "Fransa", "İngiltere", "Rusya", "Çin", "İtalya",
             "İspanya", "Japonya", "Hollanda", "Yunanistan"]


def rnum(a, b):
    return random.randint(a, b)


def rpct():
    return f"yüzde {random.randint(1, 40)}"


def money():
    return f"{random.randint(10, 90)} bin lira"

# --------------------------- topic templates --------------------------------
# Each topic -> dict with:
#   'single': list of lambda -> sentence  (standalone, random event)
#   'para'  : list of lambda -> (s1, s2)  (same event, two phrasings)


def cap(s):
    return s[0].upper() + s[1:]


def topic_spor():
    def s_match():
        a, b = random.sample(TEAMS, 2)
        g1, g2 = rnum(0, 4), rnum(0, 3)
        return f"{a}, sahasında {b}'yi {g1}-{g2} mağlup etti."

    def s_transfer():
        return f"{random.choice(TEAMS)}, yıldız futbolcuyla sözleşme yeniledi."

    def s_injury():
        return f"{random.choice(TEAMS)}'nin kaptanı sakatlığı nedeniyle kadroda yer alamadı."

    def s_coach():
        return f"{random.choice(TEAMS)} teknik direktörüyle yollarını ayırdı."

    singles = [s_match, s_transfer, s_injury, s_coach]

    def p_match():
        a, b = random.sample(TEAMS, 2)
        g1, g2 = rnum(1, 4), rnum(0, 2)
        s1 = f"{a}, {b} karşısında sahadan {g1}-{g2} galip ayrıldı."
        s2 = f"{a} evinde {b}'yi {g1}-{g2}'lik skorla yendi."
        return s1, s2

    def p_champion():
        t = random.choice(TEAMS)
        s1 = f"{t}, ligi lider tamamlayarak şampiyonluğa ulaştı."
        s2 = f"{t} sezonu zirvede bitirip şampiyon oldu."
        return s1, s2

    def p_transfer():
        t = random.choice(TEAMS)
        s1 = f"{t}, tecrübeli oyuncuyla anlaşmaya vardı."
        s2 = f"{t} deneyimli futbolcuyu kadrosuna kattı."
        return s1, s2

    return singles, [p_match, p_champion, p_transfer]


def topic_magazin():
    def s_holiday():
        return f"{random.choice(CELEBS)}, {random.choice(CITIES)}'da tatilde görüntülendi."

    def s_wedding():
        return f"{random.choice(CELEBS)} sürpriz bir törenle dünyaevine girdi."

    def s_divorce():
        return f"{random.choice(CELEBS)} eşinden boşandığını duyurdu."

    def s_project():
        return f"{random.choice(CELEBS)} yeni projesiyle ekranlara dönüyor."

    singles = [s_holiday, s_wedding, s_divorce, s_project]

    def p_holiday():
        c = random.choice(CELEBS)
        city = random.choice(CITIES)
        s1 = f"{cap(c)} eşiyle {city}'da tatil yaparken görüntülendi."
        s2 = f"{cap(c)} ve eşinin {city} tatilinden kareler paylaşıldı."
        return s1, s2

    def p_relationship():
        c = random.choice(CELEBS)
        s1 = f"{cap(c)} yeni bir aşka yelken açtı."
        s2 = f"{cap(c)} yeni sevgilisiyle ilk kez birlikte görüntülendi."
        return s1, s2

    def p_wedding():
        c = random.choice(CELEBS)
        s1 = f"{cap(c)} sevgilisiyle nişanlandı."
        s2 = f"{cap(c)} mutlu haberi nişan yüzükleriyle duyurdu."
        return s1, s2

    return singles, [p_holiday, p_relationship, p_wedding]


def topic_ekonomi():
    def s_dolar():
        return f"Dolar kuru güne {rpct()} yükselişle başladı."

    def s_borsa():
        return f"Borsa İstanbul günü {rpct()} değişimle kapattı."

    def s_zam():
        return f"{cap(random.choice(FOODS))} fiyatları son bir ayda {rpct()} arttı."

    def s_faiz():
        return "Merkez Bankası politika faizini sabit tuttu."

    singles = [s_dolar, s_borsa, s_zam, s_faiz]

    def p_enflasyon():
        p = rpct()
        s1 = f"Yıllık enflasyon {p} olarak açıklandı."
        s2 = f"TÜİK yıllık enflasyonu {p} olarak duyurdu."
        return s1, s2

    def p_faiz():
        s1 = "Merkez Bankası faiz oranlarında değişikliğe gitti."
        s2 = "TCMB politika faizini güncelledi."
        return s1, s2

    def p_borsa():
        s1 = "Borsa İstanbul rekor seviyeye ulaştı."
        s2 = "BIST 100 endeksi tarihi zirvesini yeniledi."
        return s1, s2

    return singles, [p_enflasyon, p_faiz, p_borsa]


def topic_siyaset():
    def s_yasa():
        return f"{random.choice(PARTIES)} yeni yasa teklifini meclise sundu."

    def s_ziyaret():
        return f"Cumhurbaşkanı {random.choice(COUNTRIES)}'e resmi ziyarette bulundu."

    def s_aciklama():
        return f"{random.choice(MINISTRIES)} yeni düzenlemeyi kamuoyuyla paylaştı."

    singles = [s_yasa, s_ziyaret, s_aciklama]

    def p_yasa():
        p = random.choice(PARTIES)
        s1 = f"{cap(p)} yeni kanun teklifine ilişkin açıklama yaptı."
        s2 = f"{cap(p)} hazırladığı yasa teklifini kamuoyuna duyurdu."
        return s1, s2

    def p_zirve():
        c = random.choice(COUNTRIES)
        s1 = f"Liderler {c}'de düzenlenen zirvede bir araya geldi."
        s2 = f"{c}'deki zirvede liderler önemli konuları görüştü."
        return s1, s2

    return singles, [p_yasa, p_zirve]


def topic_hava():
    def s_yagis():
        return f"Meteoroloji {random.choice(CITIES)} için kuvvetli yağış uyarısı yaptı."

    def s_sicak():
        return f"{random.choice(CITIES)}'da sıcaklık {rnum(30, 44)} dereceye ulaştı."

    def s_kar():
        return f"{random.choice(CITIES)}'a mevsimin ilk karı düştü."

    singles = [s_yagis, s_sicak, s_kar]

    def p_yagis():
        city = random.choice(CITIES)
        s1 = f"{city} ve çevresi için sağanak yağış bekleniyor."
        s2 = f"Meteoroloji {city} için sağanak uyarısında bulundu."
        return s1, s2

    def p_sicak():
        city = random.choice(CITIES)
        s1 = f"{city}'da hava sıcaklığı mevsim normallerinin üzerine çıktı."
        s2 = f"{city} beklenenden daha sıcak bir güne uyandı."
        return s1, s2

    return singles, [p_yagis, p_sicak]


def topic_asayis():
    def s_kaza():
        return f"{random.choice(CITIES)}'da meydana gelen trafik kazasında {rnum(1,5)} kişi yaralandı."

    def s_yangin():
        return f"{random.choice(CITIES)}'da çıkan yangın itfaiye ekiplerince söndürüldü."

    def s_operasyon():
        return f"{random.choice(CITIES)}'da düzenlenen operasyonda çok sayıda şüpheli gözaltına alındı."

    singles = [s_kaza, s_yangin, s_operasyon]

    def p_kaza():
        city = random.choice(CITIES)
        n = rnum(2, 6)
        s1 = f"{city}'da iki aracın çarpışması sonucu {n} kişi yaralandı."
        s2 = f"{city}'daki trafik kazasında {n} kişi yaralı kurtuldu."
        return s1, s2

    def p_yangin():
        city = random.choice(CITIES)
        s1 = f"{city}'da bir binada çıkan yangın kısa sürede kontrol altına alındı."
        s2 = f"{city}'daki yangın itfaiyenin müdahalesiyle söndürüldü."
        return s1, s2

    return singles, [p_kaza, p_yangin]


def topic_saglik():
    def s_uyari():
        return f"Uzmanlar {random.choice(DISEASES)} vakalarındaki artışa dikkat çekti."

    def s_asi():
        return "Sağlık Bakanlığı yeni aşılama kampanyasını başlattı."

    def s_beslenme():
        return "Uzmanlar dengeli beslenmenin önemine vurgu yaptı."

    singles = [s_uyari, s_asi, s_beslenme]

    def p_hastalik():
        d = random.choice(DISEASES)
        s1 = f"{cap(d)} vakalarında son haftalarda belirgin artış görüldü."
        s2 = f"Sağlık yetkilileri {d} vakalarının yükseldiğini bildirdi."
        return s1, s2

    return singles, [p_hastalik]


def topic_teknoloji():
    def s_lansman():
        return f"Teknoloji şirketi yeni {random.choice(TECHS)} tanıttı."

    def s_yatirim():
        return "Şirket yapay zeka alanına milyar dolarlık yatırım yapacağını açıkladı."

    def s_guncelleme():
        return f"Popüler uygulama {random.choice(TECHS)} için yeni güncelleme yayınladı."

    singles = [s_lansman, s_yatirim, s_guncelleme]

    def p_lansman():
        t = random.choice(TECHS)
        s1 = f"Teknoloji devi yeni {t} modelini duyurdu."
        s2 = f"Şirket güncellenmiş {t} sürümünü kullanıma sundu."
        return s1, s2

    def p_ai():
        s1 = "Yapay zeka destekli tanı sistemi hastanelerde kullanılmaya başlandı."
        s2 = "Hastaneler teşhis süreçlerinde yapay zekadan yararlanmaya başladı."
        return s1, s2

    return singles, [p_lansman, p_ai]


def topic_dunya():
    def s_secim():
        return f"{random.choice(COUNTRIES)}'de yapılan seçimleri muhalefet kazandı."

    def s_dogal():
        return f"{random.choice(COUNTRIES)}'de meydana gelen depremde maddi hasar oluştu."

    def s_zirve():
        return f"{random.choice(COUNTRIES)} iklim zirvesine ev sahipliği yapıyor."

    singles = [s_secim, s_dogal, s_zirve]

    def p_secim():
        c = random.choice(COUNTRIES)
        s1 = f"{c}'de düzenlenen genel seçimlerde sonuçlar belli oldu."
        s2 = f"{c} halkı sandık başına giderek yeni yönetimini seçti."
        return s1, s2

    return singles, [p_secim]


TOPICS = {
    "spor": topic_spor(),
    "magazin": topic_magazin(),
    "ekonomi": topic_ekonomi(),
    "siyaset": topic_siyaset(),
    "hava": topic_hava(),
    "asayis": topic_asayis(),
    "saglik": topic_saglik(),
    "teknoloji": topic_teknoloji(),
    "dunya": topic_dunya(),
}
TOPIC_NAMES = list(TOPICS.keys())


def gen_single(topic):
    singles, _ = TOPICS[topic]
    return random.choice(singles)()


def gen_para(topic):
    _, paras = TOPICS[topic]
    return random.choice(paras)()


def build_pairs():
    rows = []  # (s1, s2, pair_type, topic)
    seen = set()

    def add(s1, s2, ptype, topic):
        key = (s1.lower(), s2.lower())
        if s1 == s2 or key in seen or (s2.lower(), s1.lower()) in seen:
            return False
        seen.add(key)
        rows.append((s1, s2, ptype, topic))
        return True

    # unrelated: two different topics
    tries = 0
    while sum(1 for r in rows if r[2] == "unrelated") < COUNTS["unrelated"] and tries < 20000:
        tries += 1
        t1, t2 = random.sample(TOPIC_NAMES, 2)
        add(gen_single(t1), gen_single(t2), "unrelated", f"{t1}|{t2}")

    # related: same topic, two different single events
    tries = 0
    while sum(1 for r in rows if r[2] == "related") < COUNTS["related"] and tries < 30000:
        tries += 1
        t = random.choice(TOPIC_NAMES)
        s1, s2 = gen_single(t), gen_single(t)
        add(s1, s2, "related", t)

    # paraphrase: same event, two phrasings
    tries = 0
    while sum(1 for r in rows if r[2] == "paraphrase") < COUNTS["paraphrase"] and tries < 40000:
        tries += 1
        t = random.choice(TOPIC_NAMES)
        s1, s2 = gen_para(t)
        add(s1, s2, "paraphrase", t)

    random.shuffle(rows)
    return rows


def main():
    rows = build_pairs()
    print(f"{len(rows)} sentetik cift uretildi. Model yukleniyor...", flush=True)
    model = SentenceTransformer(MODEL_ID)

    # batch-encode unique sentences for speed
    uniq = sorted({s for r in rows for s in (r[0], r[1])})
    print(f"{len(uniq)} benzersiz cumle encode ediliyor...", flush=True)
    embs = model.encode(uniq, normalize_embeddings=True, convert_to_numpy=True,
                        batch_size=64, show_progress_bar=True)
    emap = {s: e for s, e in zip(uniq, embs)}

    def cos(a, b):
        d = np.linalg.norm(a) * np.linalg.norm(b)
        return 0.0 if d == 0 else float(np.dot(a, b) / d)

    out = []
    for s1, s2, ptype, topic in rows:
        sc = cos(emap[s1], emap[s2])
        out.append((s1, s2, round(sc, 6), ptype, topic))

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sentence1", "sentence2", "score", "pair_type", "topic"])
        w.writerows(out)

    # quick distribution report
    import statistics
    for pt in ["unrelated", "related", "paraphrase"]:
        vals = [r[2] for r in out if r[3] == pt]
        if vals:
            print(f"{pt:>10}: n={len(vals):>4}  ort={statistics.mean(vals):.3f}  "
                  f"min={min(vals):.3f}  max={max(vals):.3f}", flush=True)
    near0 = sum(1 for r in out if r[2] < 0.2)
    print(f"\n0.2 alti (0'a yakin): {near0} cift", flush=True)
    print(f"Toplam {len(out)} -> {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
