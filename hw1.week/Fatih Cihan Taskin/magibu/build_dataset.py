"""
Giresun kültürü veri setini oluşturur.

Adımlar:
1. qa_pairs'ten temel (soru, cevap) çiftlerini alır.
2. Her soruyu doğal Türkçe/İngilizce ön eklerle çoğaltarak (paraphrase)
   örnek sayısını artırır. Cevap sabit kalır; kaynağa bağlılık korunur.
3. Her çifti hedef formata sarar:
   {"messages": [ {user...}, {assistant...} ]}
   Alan sırası ve isimleri referans dataset ile aynı:
   content, images, role, thinking, tool_calls
4. turkish / english split'lerini içeren bir DatasetDict kurar.
5. Parquet olarak diske yazar ve isteğe bağlı olarak Hub'a push eder.
"""

import argparse
from datasets import Dataset, DatasetDict

from qa_pairs import qa_tr, qa_en

# Aynı soruyu farklı biçimlerde sormak için ön ekler (çoğaltma / augmentation).
# Cevabı değiştirmezler; yalnızca kullanıcı sorusunu doğallaştırırlar.
TR_PREFIXES = [
    "{q}",
    "Merhaba, {ql}",
    "Acaba {ql}",
    "Sana bir sorum var: {ql}",
    "Kısaca söyler misin, {ql}",
    "Bana {ql}",
]

EN_PREFIXES = [
    "{q}",
    "Hi, {ql}",
    "I have a question: {ql}",
    "Could you tell me, {ql}",
    "Briefly, {ql}",
]


def _lower_first(s: str) -> str:
    # Özel isimlerle başlayan sorularda küçültme yapma (dilbilgisi korunur).
    # Aksi halde "giresun'un..." gibi hatalı formlar oluşur.
    if not s:
        return s
    # İlk kelimeyi al; Türkçe ekler apostrofla ayrıldığı için ('Giresun'da)
    # apostrof öncesi kök kısmına bakarız.
    raw_first = s.split(" ", 1)[0]
    first_word = raw_first.split("'")[0].split("’")[0].strip(",.:?")
    proper_nouns = {
        # Türkçe / ortak özel isimler
        "Giresun", "Aksu", "Görele", "Katip", "Hamza", "Islık",
        "Peştamal", "Karadeniz", "Amazon", "Türkiye", "Mart", "UNESCO",
        # İngilizce özel isimler ve zamir
        "Görele's", "Aynalıdır", "I",
    }
    if first_word in proper_nouns:
        return s
    return s[0].lower() + s[1:]


def expand(pairs, prefixes):
    """Her (soru, cevap) için prefix varyasyonları üretir."""
    rows = []
    seen = set()
    for q, a in pairs:
        ql = _lower_first(q)
        for p in prefixes:
            question = p.format(q=q, ql=ql)
            key = (question, a)
            if key in seen:
                continue
            seen.add(key)
            rows.append((question, a))
    return rows


def to_messages(pairs):
    """Çiftleri referans formattaki messages yapısına sarar."""
    records = []
    for q, a in pairs:
        messages = [
            {"content": q, "images": None, "role": "user",
             "thinking": None, "tool_calls": None},
            {"content": a, "images": None, "role": "assistant",
             "thinking": None, "tool_calls": None},
        ]
        records.append({"messages": messages})
    return records


def build():
    tr_rows = to_messages(expand(qa_tr, TR_PREFIXES))
    en_rows = to_messages(expand(qa_en, EN_PREFIXES))

    ds = DatasetDict({
        "turkish": Dataset.from_list(tr_rows),
        "english": Dataset.from_list(en_rows),
    })
    return ds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data", help="Parquet çıktı dizini")
    ap.add_argument("--push", metavar="REPO_ID",
                    help="Hub repo id (ör. kullanici/giresun_kultur). "
                         "Verilirse push_to_hub çağrılır.")
    ap.add_argument("--private", action="store_true",
                    help="Hub reposu private olsun.")
    args = ap.parse_args()

    ds = build()
    print("turkish:", ds["turkish"].num_rows, "örnek")
    print("english:", ds["english"].num_rows, "örnek")
    print("örnek kayıt:", ds["turkish"][0])

    import os
    os.makedirs(args.out, exist_ok=True)
    ds["turkish"].to_parquet(f"{args.out}/turkish.parquet")
    ds["english"].to_parquet(f"{args.out}/english.parquet")
    print(f"Parquet dosyaları '{args.out}/' altına yazıldı.")

    if args.push:
        ds.push_to_hub(args.push, private=args.private)
        print(f"Hub'a push edildi: {args.push}")


if __name__ == "__main__":
    main()
