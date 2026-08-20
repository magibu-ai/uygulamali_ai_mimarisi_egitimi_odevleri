"""CANLI (live) tool-selection degerlendirmesi — Ollama + qwen2.5:7b-instruct GEREKTIRIR.

Bu betik DETERMINISTIK BIRIM TESTI DEGILDIR ve `python -m unittest` ile CALISMAZ.
Faz 3'teki 24 senaryoluk kucuk senaryo-tabanli degerlendirmeyi tekrarlanabilir kilar.

Calistirma (proje kokunden, Ollama acikken):
    python tests/eval/run_eval.py            # varsayilan temp 0 (tekrarlanabilir)
    python tests/eval/run_eval.py --temp 0.1 # uygulamanin gercek sicakligi

Not: temp 0 (greedy) bile bu donanimda tam deterministik degildir; "acik uclu
tavsiye" gibi sinir sorulari ( or. A3) kosular arasinda degisebilir. Sonuclari
kucuk bir senaryo degerlendirmesi olarak yorumlayin, istatistiksel bir kiyaslama
olarak degil. Ayrintilar: docs/prompt_design.md.
"""

import argparse
import os
import sys

_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ollama_asistan")
sys.path.insert(0, _APP)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import ollama_client
import tools
import chat

# (id, category, question, expected_toolset, acceptable_alternatives, judge_by_answer)
CASES = [
    ("A1", "A", "Sen kimsin?", set(), [], False),
    ("A2", "A", "Bana hangi konularda yardımcı olabilirsin?", set(), [], False),
    ("A3", "A", "Bir yarışa hazırlanırken genel olarak nelere dikkat edilir?", set(), [], False),
    ("B1", "B", "Fren balatalarının durumu nedir?", {"check_part_status"}, [], False),
    ("B2", "B", "Lastiklerin durumu nasıl?", {"check_part_status"}, [], False),
    ("B3", "B", "Akünün kontrol durumu nedir?", {"check_part_status"}, [], False),
    ("C1", "C", "Fren sistemiyle ilgili yarış kuralları neler?", {"get_race_regulations"}, [], False),
    ("C2", "C", "Elektrik sistemiyle ilgili teknik kurallar neler?", {"get_race_regulations"}, [], False),
    ("C3", "C", "Güvenlik gereksinimleri hakkında ne biliyorsun?", {"get_race_regulations"}, [], False),
    ("D1", "D", "Yarın İstanbul'da hava nasıl?", {"get_weather"}, [], False),
    ("D2", "D", "Yarış günü İstanbul'da yağmur bekleniyor mu?", {"get_weather"}, [], False),
    ("D3", "D", "İstanbul'daki hava sıcaklığı nedir?", {"get_weather"}, [], False),
    ("E1", "E", "2026 Formula Student hakkında güncel haberleri ara.", {"internet_search"}, [], False),
    ("E2", "E", "Formula Student'ın bu yılki güncel gelişmelerini internetten araştır.", {"internet_search"}, [], False),
    ("E3", "E", "Bu konuda internette güncel bilgi bulabilir misin? Konu: elektrikli yarış araçları.", {"internet_search"}, [], False),
    ("F1", "F", "Yarın İstanbul'da yağmur yağacaksa fren balatalarımızı kontrol etmeli miyiz?", {"get_weather", "check_part_status"}, [], False),
    ("F2", "F", "İstanbul'daki yarış günü hava durumunu öğren, bir de güvenlik kurallarını özetle.", {"get_weather", "get_race_regulations"}, [], False),
    ("G1", "G", "Frenler hakkında ne düşünüyorsun?", set(), [{"get_race_regulations"}], False),
    ("G2", "G", "Lastikler yarış için uygun mu?", {"check_part_status"}, [], False),
    ("G3", "G", "Yarışa hazırlanıyoruz, ne yapmalıyız?", set(), [], False),
    ("G4", "G", "Fren sistemiyle ilgili güncel bilgi verir misin?", {"internet_search"}, [{"get_race_regulations"}, set()], False),
    ("H1", "H", "Turbo şarj sisteminin durumu nedir?", {"check_part_status"}, [], True),
    ("H2", "H", "Aerodinamik kanat kuralları neler?", {"get_race_regulations"}, [], True),
    ("H3", "H", "Aracımızın motor beygir gücü kaç?", set(), [{"check_part_status"}], True),
]


def run_turn(question, temperature):
    calls = []
    messages = [{"role": "system", "content": chat.SYSTEM_PROMPT},
                {"role": "user", "content": question}]
    message = {}
    for _ in range(chat.MAX_TOOL_ROUNDS):
        message = ollama_client.chat(messages, tools=tools.TOOL_SCHEMAS, temperature=temperature)
        messages.append(message)
        tc = message.get("tool_calls")
        if not tc:
            break
        calls += [c["function"]["name"] for c in tc]
        messages.extend(chat.run_tool_calls(tc))
    return calls, (message.get("content") or "").strip()


def score(expected, acceptable, names):
    s = set(names)
    return (s == expected) or any(s == a for a in acceptable)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()

    try:
        ollama_client._post("/api/tags", {}, timeout=5) if False else None
    except Exception:
        pass

    per_cat, h_notes = {}, []
    for cid, cat, q, expected, acceptable, judge in CASES:
        try:
            names, answer = run_turn(q, args.temp)
        except RuntimeError as exc:
            print(f"[{cid}] CALISTIRILAMADI: {exc}")
            print("Ollama calisiyor mu? 'ollama serve' ve 'ollama pull qwen2.5:7b-instruct'")
            return
        ok = score(expected, acceptable, names)
        per_cat.setdefault(cat, []).append(ok)
        print(f"[{cid}/{cat}] {'PASS' if ok else 'FAIL'} got={sorted(set(names)) or 'NO-TOOL'}  | {q}")
        if judge:
            h_notes.append((cid, names, answer))

    print("\n=== CATEGORY (auto tool-selection) ===")
    for cat in sorted(per_cat):
        v = per_cat[cat]
        print(f"  {cat}: {sum(v)}/{len(v)}")
    ag = [ok for c, v in per_cat.items() if c != "H" for ok in v]
    print(f"  OVERALL (A-G): {sum(ag)}/{len(ag)}")
    print("\n=== H (unknown info; judge by non-fabrication) ===")
    for cid, names, ans in h_notes:
        print(f"  {cid} calls={sorted(set(names)) or 'NO-TOOL'}: {ans[:140]}")


if __name__ == "__main__":
    main()
