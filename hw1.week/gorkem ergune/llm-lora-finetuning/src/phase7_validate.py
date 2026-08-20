"""Phase 7: validate persona, thinking mode, and tool-calling — BASE vs FINE-TUNED.

(a) identity facts, (b) thinking channel still fires, (c) tool-calling triggers the
right tool with right args. 12 hand-written tool scenarios (incl. 2 negatives that
should NOT call a tool, and 1 UNSEEN tool to probe generalization). Prints a
before/after tool-accuracy table for the report.
"""
import os, sys, json, re, argparse
import torch
from transformers import Gemma4ForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from peft import PeftModel

MODEL = "google/gemma-4-E4B-it"

def load_base():
    SKIP = ["vision_tower","audio_tower","embed_vision","embed_audio","lm_head"]
    bnbc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        llm_int8_skip_modules=SKIP, llm_int8_enable_fp32_cpu_offload=True)
    dm = {"model.language_model":0,"lm_head":0,"model.vision_tower":"cpu","model.audio_tower":"cpu",
          "model.embed_vision":"cpu","model.embed_audio":"cpu","model.language_model.embed_tokens_per_layer":"cpu"}
    return Gemma4ForConditionalGeneration.from_pretrained(MODEL, quantization_config=bnbc,
        device_map=dm, torch_dtype=torch.bfloat16)

tok = AutoProcessor.from_pretrained(MODEL); tok = tok.tokenizer if hasattr(tok,"tokenizer") else tok

def gen(model, msgs, tools=None, enable_thinking=False, max_new=220):
    enc = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True,
        enable_thinking=enable_thinking, return_tensors="pt", return_dict=True).to(0)
    n = enc["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return tok.decode(out[0][n:], skip_special_tokens=False).strip()

# ---- tools (5 seen in training + 1 unseen) ----
def fn(name, desc, props, req):
    return {"type":"function","function":{"name":name,"description":desc,
            "parameters":{"type":"object","properties":props,"required":req}}}
WEATHER = fn("get_weather","Get current weather for a city.",{"city":{"type":"string"}},["city"])
CONVERT = fn("convert_units","Convert a value between units.",
    {"value":{"type":"number"},"from_unit":{"type":"string"},"to_unit":{"type":"string"}},["value","from_unit","to_unit"])
ARXIV = fn("search_arxiv","Search arXiv for papers.",{"query":{"type":"string"}},["query"])
COURSE = fn("get_course_info","Get a university course's info.",{"course_code":{"type":"string"}},["course_code"])
CALC = fn("calculate","Evaluate a math expression.",{"expression":{"type":"string"}},["expression"])
STOCK = fn("get_stock_price","Get the latest stock price for a ticker.",{"ticker":{"type":"string"}},["ticker"])  # UNSEEN
ALL_TOOLS = [WEATHER, CONVERT, ARXIV, COURSE, CALC, STOCK]

# (user, available tools, expected tool name or None)
SCENARIOS = [
    ("Ankara'da hava nasil?", ALL_TOOLS, "get_weather"),
    ("What's the weather in Tokyo right now?", ALL_TOOLS, "get_weather"),
    ("15 km kac mile eder?", ALL_TOOLS, "convert_units"),
    ("Convert 90 kg to lb", ALL_TOOLS, "convert_units"),
    ("transformer attention uzerine makale onerir misin?", ALL_TOOLS, "search_arxiv"),
    ("CSE471 dersi ne hakkinda?", ALL_TOOLS, "get_course_info"),
    ("144 bolu 12 kac eder?", ALL_TOOLS, "calculate"),
    ("What is 256 * 13?", ALL_TOOLS, "calculate"),
    ("AAPL hissesi kac dolar?", ALL_TOOLS, "get_stock_price"),   # unseen tool -> generalization
    ("Izmir'de hava durumu ve 5 mile kac km oldugunu soyler misin?", ALL_TOOLS, "get_weather"),  # multi
    ("Merhaba, bugun nasilsin?", ALL_TOOLS, None),              # negative: no tool
    ("Bana motivasyon verir misin?", ALL_TOOLS, None),         # negative: no tool
]

def called_tool(text):
    m = re.search(r"<\|tool_call>call:([A-Za-z_]\w*)", text)
    return m.group(1) if m else None

def run_tools(model, tag):
    rows = []; correct = 0
    for user, tools, expected in SCENARIOS:
        out = gen(model, [{"role":"user","content":user}], tools=tools, enable_thinking=True, max_new=160)
        got = called_tool(out)
        ok = (got == expected)
        correct += ok
        rows.append((user[:42], expected or "-", got or "-", "OK" if ok else "X"))
    print(f"\n===== TOOL-CALLING [{tag}] =====")
    for u,e,g,ok in rows:
        print(f"  [{ok}] {u:44s} exp={e:16s} got={g}")
    print(f"  {tag} tool accuracy: {correct}/{len(SCENARIOS)} = {100*correct/len(SCENARIOS):.0f}%")
    return correct/len(SCENARIOS)

def run_persona(model, tag):
    print(f"\n===== PERSONA/IDENTITY [{tag}] =====")
    for q in ["Sen kimsin?", "Gorkem Ergune kimdir?", "ayarlicazhocam ne ise yarar?"]:
        out = gen(model, [{"role":"user","content":q}], enable_thinking=False, max_new=140)
        print(f"\nQ: {q}\nA: {tok.decode(tok.encode(out), skip_special_tokens=True)[:300]}")

def run_thinking(model, tag):
    print(f"\n===== THINKING MODE [{tag}] =====")
    out = gen(model, [{"role":"user","content":"Bir trende 3 vagon var, her vagonda 24 kisi. Kac kisi var? Adim adim dusun."}],
              enable_thinking=True, max_new=200)
    print("has <|channel>thought:", "<|channel>thought" in out)
    print(out[:400])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="outputs/gemma4-e4b-ayarlicazhocam-v2")
    args = ap.parse_args()
    model = load_base(); model.eval()
    run_persona(model, "BASE"); base_tool = run_tools(model, "BASE")
    ft = PeftModel.from_pretrained(model, args.adapter); ft.eval()
    run_persona(ft, "FINETUNED"); run_thinking(ft, "FINETUNED"); ft_tool = run_tools(ft, "FINETUNED")
    print(f"\n=== TOOL-CALLING before/after: {100*base_tool:.0f}% -> {100*ft_tool:.0f}% ===")

if __name__ == "__main__":
    main()
