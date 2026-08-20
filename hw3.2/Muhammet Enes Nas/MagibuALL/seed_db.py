
"""
Eczane Sipariş Asistanı — Veritabanı Başlangıç Verileri
"""

from db import init_db, insert_drug, find_drug


SEED_DRUGS = [
    {
        "name": "parol",
        "display_name": "Parol",
        "stock": 120,
        "price": 32.50,
        "prospektus_summary": (
            "Parol (Parasetamol 500 mg): Hafif-orta şiddetli ağrı ve ateşte kullanılır. "
            "Yetişkinler günde en fazla 4 g (8 tablet) alabilir. Karaciğer hastalığı "
            "olanlarda dikkatli kullanılmalıdır. Yaygın yan etki nadirdir."
        ),
    },
    {
        "name": "majezik",
        "display_name": "Majezik",
        "stock": 85,
        "price": 48.00,
        "prospektus_summary": (
            "Majezik (Flurbiprofen 100 mg): Non-steroid antiinflamatuar ilaçtır. "
            "Diş ağrısı, kas-iskelet ağrıları ve eklem iltihabında kullanılır. "
            "Tok karnına alınmalıdır. Mide hassasiyeti olanlarda dikkat edilmelidir."
        ),
    },
    {
        "name": "augmentin",
        "display_name": "Augmentin",
        "stock": 40,
        "price": 95.00,
        "prospektus_summary": (
            "Augmentin (Amoksisilin/Klavulanat): Geniş spektrumlu antibiyotiktir. "
            "Üst ve alt solunum yolu, idrar yolu, deri enfeksiyonlarında kullanılır. "
            "Reçetesiz kullanılmamalıdır. Tedavi süresi doktor tarafından belirlenir."
        ),
    },
    {
        "name": "aferin",
        "display_name": "Aferin",
        "stock": 200,
        "price": 28.00,
        "prospektus_summary": (
            "Aferin Fort: Parasetamol, klorfeniramin ve pseudoefedrin içerir. "
            "Grip ve soğuk algınlığı belirtilerini (ateş, burun akıntısı, tıkanıklık) "
            "hafifletir. Uyku yapabilir; araç kullanırken dikkatli olunmalıdır."
        ),
    },
    {
        "name": "ventolin",
        "display_name": "Ventolin",
        "stock": 60,
        "price": 42.50,
        "prospektus_summary": (
            "Ventolin (Salbutamol) İnhaler: Bronş genişleticidir. Astım ve KOAH'ta "
            "nefes darlığı ataklarında kullanılır. Günde en fazla 8 puf önerilir. "
            "Çarpıntı ve titreme yan etkisi görülebilir."
        ),
    },
    {
        "name": "nurofen",
        "display_name": "Nurofen",
        "stock": 150,
        "price": 55.00,
        "prospektus_summary": (
            "Nurofen (İbuprofen 400 mg): Ağrı kesici ve ateş düşürücüdür. "
            "Baş ağrısı, diş ağrısı, adet sancısı ve kas ağrılarında kullanılır. "
            "Tok karnına alınmalıdır. Mide ülseri olanlarda kontrendikedir."
        ),
    },
    {
        "name": "calpol",
        "display_name": "Calpol",
        "stock": 90,
        "price": 38.00,
        "prospektus_summary": (
            "Calpol (Parasetamol 120 mg/5 ml şurup): Çocuklarda ateş ve ağrıda "
            "kullanılır. Doz çocuğun kilosuna göre ayarlanır. 2 ayın altındaki "
            "bebeklerde doktor kontrolünde kullanılmalıdır."
        ),
    },
    {
        "name": "cipro",
        "display_name": "Cipro",
        "stock": 30,
        "price": 72.00,
        "prospektus_summary": (
            "Cipro (Siprofloksasin 500 mg): Florokinolon grubu antibiyotiktir. "
            "İdrar yolu, solunum yolu ve gastrointestinal enfeksiyonlarda kullanılır. "
            "Tendon rüptürü riski nedeniyle yaşlılarda dikkatli kullanılmalıdır."
        ),
    },
    {
        "name": "voltaren",
        "display_name": "Voltaren",
        "stock": 110,
        "price": 65.00,
        "prospektus_summary": (
            "Voltaren (Diklofenak 75 mg): Non-steroid antiinflamatuar ilaçtır. "
            "Romatizmal ağrılar, bel ağrısı, travma sonrası şişlik ve ağrıda "
            "kullanılır. Uzun süreli kullanımda mide koruyucu ile birlikte alınmalıdır."
        ),
    },
    {
        "name": "a-ferin",
        "display_name": "A-Ferin",
        "stock": 75,
        "price": 35.00,
        "prospektus_summary": (
            "A-Ferin Plus: Parasetamol ve kafein kombinasyonudur. Baş ağrısı ve "
            "grip belirtilerinde kullanılır. Kafein hassasiyeti olanlarda dikkatli "
            "olunmalıdır. Günde 3-4 tabletten fazla alınmamalıdır."
        ),
    },
    {
        "name": "betaserc",
        "display_name": "Betaserc",
        "stock": 50,
        "price": 68.00,
        "prospektus_summary": (
            "Betaserc (Betahistin dihydrochloride 24 mg): Baş dönmesi (vertigo), "
            "kulak çınlaması ve işitme kaybı ile seyreden Meniere hastalığında kullanılır. "
            "Yemeklerle birlikte alınmalıdır. Astım veya mide ülseri olanlarda dikkatli kullanılmalıdır."
        ),
    },
    {
        "name": "rennie",
        "display_name": "Rennie",
        "stock": 130,
        "price": 34.00,
        "prospektus_summary": (
            "Rennie (Kalsiyum karbonat / Magnezyum karbonat): Mide yanması, "
            "mide ekşimesi, hazımsızlık ve mide bulantısı şikayetlerinde antasit olarak kullanılır. "
            "Çiğneme tableti olarak alınır. Günde 10 tabletten fazla tüketilmemelidir."
        ),
    },
]


def seed():
    init_db()
    added = 0
    skipped = 0
    for drug in SEED_DRUGS:
        existing = find_drug(drug["name"])
        if existing:
            skipped += 1
            print(f"  [SKIP] '{drug['display_name']}' zaten mevcut, atlaniyor.")
            continue
        insert_drug(
            name=drug["name"],
            display_name=drug["display_name"],
            stock=drug["stock"],
            price=drug["price"],
            prospektus_summary=drug["prospektus_summary"],
            source="seed",
        )
        added += 1
        print(f"  [OK] '{drug['display_name']}' eklendi.")

    print(f"\nToplam: {added} eklendi, {skipped} atlandi.")


if __name__ == "__main__":
    print("Eczane veritabani baslangic verileri yukleniyor...\n")
    seed()
    print("\n[OK] Tamamlendi!")
