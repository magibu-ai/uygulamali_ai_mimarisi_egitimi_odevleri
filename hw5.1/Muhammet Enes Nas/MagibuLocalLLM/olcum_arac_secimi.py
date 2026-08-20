"""Modelin ARAC SECIM isabetini olcer.

Sistem istemini ya da arac semalarini degistirdiginizde "sanirim duzeldi" demek
yerine burayi calistirin. Prompt muhendisligi de olculebilir bir istir.

Her soru icin modelin HANGI araci sectigine bakariz — araci calistirmayiz, cunku
olcmek istedigimiz sey secim, aracin ciktisi degil. Bu sayede olcum hizli ve
internet baglantisindan bagimsizdir.

═══════════════════════════════════════════════════════════════════
NEDEN SABIT TOHUM (SEED) KULLANIYORUZ — bu betigin en onemli kismi
═══════════════════════════════════════════════════════════════════

Tohum sabitlenmeden ayni test ust uste calistirildiginda su sonuclar alindi:

    1. calistirma: %25      2. calistirma: %31      3. calistirma: %44

Hicbir sey degismeden, sadece ornekleme rastgeledigi yuzunden. Bu kadar oynaklik
varken bir prompt degisikliginin ise yarayip yaramadigi ANLASILAMAZ; %31'den
%44'e cikan bir sonuc iyilesme mi yoksa sans mi, ayirt edilemez.

Cozum iki parcali:
  1. Her tur SABIT bir tohumla calisir  -> tekrar edilebilir, dogrulanabilir.
  2. Birden fazla tur, FARKLI tohumlarla -> ortalama ve en kotu/en iyi goruluri.

Tek turluk sonuca bakip karar vermeyin. En az --repeat 3 kullanin.

Kullanim:
    python olcum_arac_secimi.py                       # 3 tur, sabit tohumlar
    python olcum_arac_secimi.py --repeat 5            # daha guvenilir ortalama
    python olcum_arac_secimi.py --chat-model qwen3:1.7b # model karsilastir
"""

import argparse
import time

import config
import ollama_client
import tools
from system_prompt import FEW_SHOT_MESSAGES, SYSTEM_PROMPT

# (soru, beklenen arac). None = hicbir arac cagrilmamali.
CASES = [
    ("Merhaba",                                                        None),
    ("Nasilsin?",                                                      None),
    ("THYAO hissesi kac TL?",                                          "get_stock_price"),
    ("Apple hissesi ne durumda?",                                      "get_stock_price"),
    ("Bitcoin kac dolar?",                                             "get_stock_price"),
    ("ASELSAN fiyati ne?",                                             "get_stock_price"),
    ("Dolar kac TL?",                                                  "get_exchange_rate"),
    ("500 euro kac lira eder?",                                        "get_exchange_rate"),
    ("100 adet hisseyi 25 TL'den alip 30 TL'den sattim, ne kazandim?", "calculate_return"),
    ("20 liradan aldigim hisse 15 lira oldu, zararim yuzde kac?",      "calculate_return"),
    ("Borsa Istanbul'da bugun ne oldu?",                               "web_search"),
    ("ASELSAN neden yukseldi?",                                        "web_search"),
    ("Piyasalarda son durum nedir?",                                   "web_search"),
    ("Temettu nedir?",                                                 "finance_concept"),
    ("F/K orani nasil hesaplanir?",                                    "finance_concept"),
    ("Kaldirac ne demek?",                                             "finance_concept"),
]

parser = argparse.ArgumentParser(description="Arac secim isabetini olc.")
parser.add_argument("--chat-model", default=config.CHAT_MODEL, help="Olculecek sohbet modeli")
parser.add_argument("--repeat", type=int, default=3, help="Kac tur (her tur farkli sabit tohum)")
parser.add_argument("--base-seed", type=int, default=1000, help="Ilk turun tohumu")
parser.add_argument("--few-shot", action="store_true",
                    help="Few-shot ornekleriyle olc (varsayilan kapali, bkz. system_prompt.py)")
args = parser.parse_args()

PREFACE = [{"role": "system", "content": SYSTEM_PROMPT}]
if args.few_shot:
    PREFACE += list(FEW_SHOT_MESSAGES)

print(f"Model: {args.chat_model}   |   tur: {args.repeat}   |   sicaklik: {config.TEMPERATURE}")
print(f"Tohumlar: {[args.base_seed + i for i in range(args.repeat)]}  (tekrar edilebilir)\n")

# arac adi -> [dogru, toplam]
per_tool: dict[str, list[int]] = {}
# soru -> secilen araclarin listesi (hangi sorular kararsiz, sonda gorunsun)
per_question: dict[str, list] = {}
round_scores: list[float] = []
no_call_total = wrong_total = 0
started = time.time()

for turn in range(args.repeat):
    seed = args.base_seed + turn
    correct = 0
    print(f"── Tur {turn + 1}/{args.repeat}  (seed={seed}) " + "─" * 30)

    for question, expected in CASES:
        message = ollama_client.chat(
            # main.py ile AYNI kurulum (few-shot bayragi dahil).
            # Ikisi ayrisirsa olcum gercek davranisi olcmez.
            PREFACE + [{"role": "user", "content": question}],
            model=args.chat_model,
            tools=tools.TOOL_SCHEMAS,
            seed=seed,
        )
        calls = message.get("tool_calls") or []
        picked = calls[0]["function"]["name"] if calls else None
        per_question.setdefault(question, []).append(picked)

        key = expected or "(arac yok)"
        stats = per_tool.setdefault(key, [0, 0])
        stats[1] += 1
        if picked == expected:
            correct += 1
            stats[0] += 1
            mark = "OK    "
        elif expected is not None and picked is None:
            no_call_total += 1
            mark = "YANLIS"
        else:
            wrong_total += 1
            mark = "YANLIS"

        # Her soru bitince ANINDA yaz: 16 soru x 2.7 sn boyunca ekran bos kalmasin.
        print(f"  {mark} {question[:48]:50} bekl={str(expected):18} ald={picked}", flush=True)

    score = 100 * correct / len(CASES)
    round_scores.append(score)
    print(f"  → Tur {turn + 1} sonucu: {correct}/{len(CASES)}  ({score:.0f}%)\n")

elapsed = time.time() - started
total = len(CASES) * args.repeat
average = sum(round_scores) / len(round_scores)

if args.repeat > 1:
    print("  ── KARARSIZ SORULAR ───────────────────────")
    print("  (ayni soru, farkli tohum -> farkli arac. Model burada esikte demektir.)")
    unstable = 0
    for question, picks in per_question.items():
        if len(set(picks)) > 1:
            unstable += 1
            print(f"  {question[:46]:48} {picks}")
    if not unstable:
        print("  Yok — model tum sorularda tutarli davrandi.")
    print()

print(f"  ── ARAC BAZINDA ───────────────────────────")
for name, (hit, seen) in sorted(per_tool.items(), key=lambda kv: -kv[1][0] / kv[1][1]):
    bar = "█" * round(10 * hit / seen)
    print(f"  {name:20} {hit:2}/{seen:2}  {100 * hit / seen:3.0f}%  {bar}")

print(f"\n  ── OZET ───────────────────────────────────")
print(f"  ORTALAMA ISABET   : {average:.0f}%   (en dusuk {min(round_scores):.0f}%, en yuksek {max(round_scores):.0f}%)")
print(f"  Arac cagirmadi    : {no_call_total}/{total}   (en kotu hata tipi — uydurma riski)")
print(f"  Yanlis arac       : {wrong_total}/{total}")
print(f"  Sure              : {elapsed:.0f} sn")

spread = max(round_scores) - min(round_scores)
if spread > 10:
    print(f"\n  ⚠ Turlar arasi fark {spread:.0f} puan. Model bu gorevde KARARSIZ;")
    print(f"    ortalamaya bakin, tek turluk sonuca gore karar vermeyin.")
