"""Phase 4: synthesize multi-turn tool-calling examples in ayarlicazhocam's voice.

Schema (verified against Gemma 4 template):
  user -> assistant{reasoning, content:"", tool_calls:[{type:function,function:{name,arguments}}]}
       -> tool{name, content:<json>} -> assistant{content: final answer}
Rows carry `tools` (definitions) and `enable_thinking=True` (tool decisions benefit
from reasoning; preserve_thinking keeps same-turn thinking at tokenization time).
"""
import json, os, random
random.seed(7)
OUT = "data/v2/tools.jsonl"

# ----------------------------- tool definitions -----------------------------
def fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}

T_WEATHER = fn("get_weather", "Bir sehrin guncel hava durumunu getirir / Get current weather for a city.",
    {"city": {"type": "string", "description": "Sehir adi / City name"},
     "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Sicaklik birimi"}},
    ["city"])
T_CONVERT = fn("convert_units", "Bir degeri bir birimden digerine cevirir / Convert a value between units.",
    {"value": {"type": "number", "description": "Cevrilecek deger"},
     "from_unit": {"type": "string", "description": "Kaynak birim (km, mile, kg, lb, C, F...)"},
     "to_unit": {"type": "string", "description": "Hedef birim"}},
    ["value", "from_unit", "to_unit"])
T_ARXIV = fn("search_arxiv", "arXiv'de akademik makale arar / Search arXiv for papers.",
    {"query": {"type": "string", "description": "Arama sorgusu / Search query"},
     "max_results": {"type": "integer", "description": "Dondurulecek makale sayisi"}},
    ["query"])
T_COURSE = fn("get_course_info", "Yeditepe Universitesi ders bilgisini getirir / Get a university course's info.",
    {"course_code": {"type": "string", "description": "Ders kodu, orn. CSE331"}},
    ["course_code"])
T_CALC = fn("calculate", "Bir matematik ifadesini hesaplar / Evaluate a math expression.",
    {"expression": {"type": "string", "description": "orn. '18*7+4'"}},
    ["expression"])

# ----------------------------- content pools --------------------------------
CITIES = [("Istanbul", 31, "gunesli"), ("Ankara", 27, "parcali bulutlu"), ("Izmir", 34, "acik"),
          ("London", 18, "yagmurlu"), ("Berlin", 22, "bulutlu"), ("Tokyo", 29, "nemli"),
          ("Bursa", 30, "gunesli"), ("Antalya", 36, "sicak ve acik")]
CONV = [(10, "km", "mile", 6.21), (5, "mile", "km", 8.05), (72, "kg", "lb", 158.7),
        (150, "lb", "kg", 68.0), (100, "C", "F", 212.0), (37, "C", "F", 98.6),
        (26.2, "mile", "km", 42.2), (3, "km", "m", 3000.0)]
ARXIV = [("mixture of experts scaling", ["Switch Transformers", "GLaM", "ST-MoE"]),
         ("low rank adaptation LLM", ["LoRA", "QLoRA", "DoRA"]),
         ("retrieval augmented generation", ["RAG", "FiD", "RETRO"]),
         ("vision language models", ["CLIP", "Flamingo", "PaLI"])]
COURSES = [("CSE331", "Computer Organization", 3), ("CSE211", "Data Structures", 4),
           ("CSE471", "Machine Learning", 3), ("MATH241", "Linear Algebra", 4)]

# --------------------------- example generators -----------------------------
def ex(msgs, tools):
    return {"messages": msgs, "tools": tools, "enable_thinking": True, "source": "tool"}

def gen_weather():
    city, temp, cond = random.choice(CITIES)
    unit = random.choice(["celsius", "fahrenheit"])
    t = temp if unit == "celsius" else round(temp*9/5+32)
    us, lang = random.choice([
        (f"{city}'da hava nasil?", "tr"), (f"{city} bugun hava durumu ne?", "tr"),
        (f"What's the weather like in {city}?", "en"), (f"Is it hot in {city} right now?", "en")])
    args = {"city": city}
    if unit == "fahrenheit" or random.random() < 0.3: args["unit"] = unit
    resp = json.dumps({"city": city, "temp": t, "unit": unit, "condition": cond}, ensure_ascii=False)
    reason = (f"Kullanici {city} icin guncel hava durumu istiyor; get_weather cagirmaliyim."
              if lang == "tr" else f"User wants current weather for {city}; I should call get_weather.")
    ud = "derece" if unit == "celsius" else "F"
    final = (f"{city}'da su an {t} {ud} ve hava {cond}. Disari cikacaksan ona gore giyin! "
             if lang == "tr" else f"It's currently {t}{'°C' if unit=='celsius' else '°F'} and {cond} in {city}.")
    return ex([{"role": "user", "content": us},
               {"role": "assistant", "reasoning": reason, "content": "",
                "tool_calls": [{"type": "function", "function": {"name": "get_weather", "arguments": args}}]},
               {"role": "tool", "name": "get_weather", "content": resp},
               {"role": "assistant", "content": final}], [T_WEATHER])

def gen_convert():
    val, fu, tu, res = random.choice(CONV)
    us, lang = random.choice([
        (f"{val} {fu} kac {tu} eder?", "tr"), (f"{val} {fu} to {tu} please", "en"),
        (f"Convert {val} {fu} into {tu}", "en"), (f"{val} {fu}'yi {tu}'ye cevirir misin?", "tr")])
    resp = json.dumps({"value": val, "from": fu, "to": tu, "result": res}, ensure_ascii=False)
    reason = (f"Birim cevrimi lazim: {val} {fu} -> {tu}. convert_units kullanayim."
              if lang == "tr" else f"Need a unit conversion {val} {fu} -> {tu}; use convert_units.")
    final = (f"{val} {fu} = {res} {tu}." if lang == "en" else f"{val} {fu}, {res} {tu} ediyor.")
    return ex([{"role": "user", "content": us},
               {"role": "assistant", "reasoning": reason, "content": "",
                "tool_calls": [{"type": "function", "function": {"name": "convert_units",
                    "arguments": {"value": val, "from_unit": fu, "to_unit": tu}}}]},
               {"role": "tool", "name": "convert_units", "content": resp},
               {"role": "assistant", "content": final}], [T_CONVERT])

def gen_arxiv():
    q, papers = random.choice(ARXIV)
    n = random.choice([2, 3])
    us, lang = random.choice([
        (f"{q} hakkinda makale onerir misin?", "tr"), (f"Find me papers on {q}", "en"),
        (f"{q} konusunda son calismalar neler?", "tr")])
    resp = json.dumps({"query": q, "results": papers[:n]}, ensure_ascii=False)
    reason = (f"Kullanici '{q}' uzerine makale ariyor; search_arxiv cagirmaliyim."
              if lang == "tr" else f"User wants papers on '{q}'; call search_arxiv.")
    lst = ", ".join(papers[:n])
    final = (f"'{q}' icin bakabilecegin calismalar: {lst}. Baslamak icin ilki genelde en iyisi. "
             if lang == "tr" else f"Here are solid papers on '{q}': {lst}. Start with the first one.")
    args = {"query": q}
    if random.random() < 0.5: args["max_results"] = n
    return ex([{"role": "user", "content": us},
               {"role": "assistant", "reasoning": reason, "content": "",
                "tool_calls": [{"type": "function", "function": {"name": "search_arxiv", "arguments": args}}]},
               {"role": "tool", "name": "search_arxiv", "content": resp},
               {"role": "assistant", "content": final}], [T_ARXIV])

def gen_course():
    code, name, cr = random.choice(COURSES)
    us, lang = random.choice([
        (f"{code} dersi kac kredi?", "tr"), (f"What is {code} about?", "en"),
        (f"{code} hakkinda bilgi verir misin?", "tr")])
    resp = json.dumps({"code": code, "name": name, "credits": cr}, ensure_ascii=False)
    reason = (f"{code} ders bilgisi isteniyor; get_course_info cagirayim."
              if lang == "tr" else f"Course info for {code} requested; call get_course_info.")
    final = (f"{code} - {name}, {cr} kredilik bir ders. " if lang == "tr"
             else f"{code} is {name}, a {cr}-credit course.")
    return ex([{"role": "user", "content": us},
               {"role": "assistant", "reasoning": reason, "content": "",
                "tool_calls": [{"type": "function", "function": {"name": "get_course_info",
                    "arguments": {"course_code": code}}}]},
               {"role": "tool", "name": "get_course_info", "content": resp},
               {"role": "assistant", "content": final}], [T_COURSE])

def gen_multi_two_cities():
    (c1, t1, cond1), (c2, t2, cond2) = random.sample(CITIES, 2)
    us = random.choice([f"{c1} ve {c2}'da hava nasil?", f"Compare the weather in {c1} and {c2}"])
    def call(c): return {"type": "function", "function": {"name": "get_weather", "arguments": {"city": c}}}
    def r(c, t, cond): return {"role": "tool", "name": "get_weather",
        "content": json.dumps({"city": c, "temp": t, "unit": "celsius", "condition": cond}, ensure_ascii=False)}
    msgs = [{"role": "user", "content": us},
            {"role": "assistant", "reasoning": f"Iki sehir icin de hava lazim: {c1} ve {c2}. Ikisini de sorgulayayim.",
             "content": "", "tool_calls": [call(c1), call(c2)]},
            r(c1, t1, cond1), r(c2, t2, cond2),
            {"role": "assistant", "content": f"{c1} {t1} derece ({cond1}), {c2} ise {t2} derece ({cond2}). "
             f"{'Ilki' if t1>t2 else 'Ikincisi'} daha sicak."}]
    return ex(msgs, [T_WEATHER])

def gen_multi_convert_then_calc():
    val, fu, tu, res = random.choice([c for c in CONV if c[1] in ("km", "mile")])
    us = f"{val} {fu} kac {tu}, ve bunun 3 kati ne eder?"
    total = round(res*3, 2)
    msgs = [{"role": "user", "content": us},
            {"role": "assistant", "reasoning": f"Once {val} {fu}'yi {tu}'ye cevirmeliyim, sonra sonucu 3 ile carpacagim. convert_units ile baslayayim.",
             "content": "", "tool_calls": [{"type": "function", "function": {"name": "convert_units",
                "arguments": {"value": val, "from_unit": fu, "to_unit": tu}}}]},
            {"role": "tool", "name": "convert_units",
             "content": json.dumps({"result": res, "to": tu}, ensure_ascii=False)},
            {"role": "assistant", "reasoning": f"{res} {tu} cikti; simdi 3 katini hesaplatayim.",
             "content": "", "tool_calls": [{"type": "function", "function": {"name": "calculate",
                "arguments": {"expression": f"{res}*3"}}}]},
            {"role": "tool", "name": "calculate", "content": json.dumps({"result": total}, ensure_ascii=False)},
            {"role": "assistant", "content": f"{val} {fu} = {res} {tu}, uc kati ise {total} {tu} eder."}]
    return ex(msgs, [T_CONVERT, T_CALC])

# ------------------------------- build set ----------------------------------
gens = [(gen_weather, 55), (gen_convert, 45), (gen_arxiv, 30), (gen_course, 30),
        (gen_multi_two_cities, 25), (gen_multi_convert_then_calc, 20)]
rows, seen = [], set()
for g, count in gens:
    tries = 0
    made = 0
    while made < count and tries < count*20:
        tries += 1
        r = g()
        key = json.dumps([m.get("content") for m in r["messages"]], ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key); rows.append(r); made += 1

random.shuffle(rows)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} tool examples -> {OUT}")
from collections import Counter
print("by first tool:", Counter(r["messages"][1]["tool_calls"][0]["function"]["name"] for r in rows))
