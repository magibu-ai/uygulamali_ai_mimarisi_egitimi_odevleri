"""Embedding modellerini olcer ve karsilastirir.

Bir retriever'in iyi olup olmadigini "hissederek" anlayamazsiniz; olcmeniz gerekir.
Bu betik iki basit soru sorar:

    1. ISABET: Bilgi bankasindaki bir soruda DOGRU kaydi ilk sirada getiriyor mu?
    2. AYRIM : Bilgi bankasi ICI sorularin en dusuk skoru, bilgi bankasi DISI
               sorularin en yuksek skorundan buyuk mu?

(2) negatifse hicbir esik degeri ise yaramaz: ya alakali sorulari reddedersiniz
ya da alakasiz sorulara cevap uydurursunuz. Iyi bir retriever'da bu sayi pozitiftir.

Cikan "Onerilen esik" degerini ollama_client.EMBED_MODELS icine yazin.

Kullanim:
    python olcum_karsilastirma.py                      # indekslenmis tum modeller
    python olcum_karsilastirma.py --model magibu gemma
"""

import argparse

import config
import finance_rag
import ollama_client

# Bilgi bankasinda olmasi gereken sorular ve beklenen baslikdan bir parca.
IN_KB = [
    ("Temettu nedir?", "Temettu"),
    ("F/K orani nasil hesaplanir?", "Fiyat Kazanc"),
    ("BIST 100 endeksi neyi olcer?", "BIST 100"),
    ("Kaldirac kullanmak neden riskli?", "Kaldirac"),
    ("Bitcoin halving nedir?", "Bitcoin"),
    ("Stablecoin ne ise yarar?", "Stablecoin"),
    ("Portfoy cesitlendirmesi riski nasil azaltir?", "Cesitlendirme"),
    ("Reel getiri ile nominal getiri farki nedir?", "Enflasyon"),
    ("Aciga satista zarar neden sinirsiz?", "Aciga Satis"),
    ("Limit emir ile piyasa emri arasindaki fark nedir?", "Emir Tipleri"),
]

# Bilgi bankasinda kesinlikle olmayan sorular: asistan bunlara "Bilmiyorum" demeli.
OUT_OF_KB = [
    "Mars kolonilerinde vergi nasil hesaplanir?",
    "Lazanya tarifi nedir?",
    "Besiktas kac kupa kazandi?",
    "Kuantum bilgisayar nasil calisir?",
    "Bugun Istanbul'da hava nasil?",
    "Python'da liste nasil siralanir?",
]

parser = argparse.ArgumentParser(description="Embedding modellerini karsilastir.")
parser.add_argument(
    "--model",
    nargs="+",
    default=list(ollama_client.EMBED_MODELS),
    choices=list(ollama_client.EMBED_MODELS),
    help="Olculecek modeller",
)
args = parser.parse_args()

for embed_key in args.model:
    model = ollama_client.EMBED_MODELS[embed_key]
    collection = finance_rag.get_collection(embed_key)
    print(f"\n=== {embed_key}  ({model['name']}) ===")
    if collection.count() == 0:
        print("  Bu model icin indeks bos. Once: "
              f"python index_finance.py --model {embed_key}")
        continue

    try:
        hits = 0
        in_scores = []
        for question, expected in IN_KB:
            top = finance_rag.search(question, embed_key, k=1)[0]
            correct = expected.lower() in top["title"].lower()
            hits += correct
            in_scores.append(top["similarity"])
            print(f"  {'OK    ' if correct else 'YANLIS'} {top['similarity']:.3f}  "
                  f"{question[:40]:42} -> {top['title'][:34]}")

        out_scores = [finance_rag.search(q, embed_key, k=1)[0]["similarity"] for q in OUT_OF_KB]
    except RuntimeError as exc:
        print(f"  Olculemedi: {exc}")
        continue

    gap = min(in_scores) - max(out_scores)
    print("  ---")
    print(f"  Isabet@1        : {hits}/{len(IN_KB)}")
    print(f"  KB-ici  en dusuk: {min(in_scores):.3f}  (ortalama {sum(in_scores)/len(in_scores):.3f})")
    print(f"  KB-disi en yuks.: {max(out_scores):.3f}")
    print(f"  AYRIM           : {gap:+.3f}  ->  {'kullanilabilir' if gap > 0 else 'KULLANILAMAZ'}")
    if gap > 0:
        print(f"  Onerilen esik   : {min(in_scores) - gap / 2:.2f}  "
              f"(su anki: {model['min_similarity']})")
    else:
        print("  Bu model bu bilgi bankasinda alakali/alakasiz ayrimi yapamiyor.")
        print("  Esigi degistirmek CARE DEGIL; baska bir embedding modeli deneyin.")

print(f"\nAktif model (config.EMBED_MODEL): {config.EMBED_MODEL}")
