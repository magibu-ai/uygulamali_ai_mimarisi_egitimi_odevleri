"""Format-rules gate: how does Gemma 4's OWN chat template render thinking and
tool_calls? Run BEFORE any large-scale data gen. CPU/tokenizer only."""
from transformers import AutoProcessor
import json

proc = AutoProcessor.from_pretrained("google/gemma-4-E4B-it")
tok = proc.tokenizer if hasattr(proc, "tokenizer") else proc

def show(title, msgs, tools=None, agp=False):
    print("\n" + "="*70 + f"\n{title}\n" + "="*70)
    try:
        txt = tok.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=agp)
        print(txt)
        # round-trip: encode then decode, confirm special tokens survive
        ids = tok.apply_chat_template(msgs, tools=tools, tokenize=True, add_generation_prompt=agp)
        back = tok.decode(ids, skip_special_tokens=False)
        print("--- round-trip byte-identical:", back == txt)
    except Exception as e:
        import traceback; traceback.print_exc()
        print("TEMPLATE ERROR:", type(e).__name__, str(e)[:200])

# 1) plain single turn (matches v1 data shape)
show("[1] plain user+assistant",
     [{"role":"user","content":"Sen kimsin?"},
      {"role":"assistant","content":"Ben ayarlicazhocam'in asistaniyim."}])

# 2) assistant with a 'thinking' field (does the template emit a thought channel?)
show("[2] assistant WITH thinking field",
     [{"role":"user","content":"2+2 kac?"},
      {"role":"assistant","thinking":"Basit toplama: 2+2=4.","content":"4 eder."}])

# 3) tool definition + assistant tool_call + tool response
weather = {"type":"function","function":{
    "name":"get_weather",
    "description":"Bir sehrin guncel hava durumunu getirir.",
    "parameters":{"type":"object","properties":{
        "city":{"type":"string","description":"Sehir adi"}},"required":["city"]}}}
show("[3] tool call + tool response",
     [{"role":"user","content":"Istanbul'da hava nasil?"},
      {"role":"assistant","content":"","tool_calls":[
          {"type":"function","function":{"name":"get_weather","arguments":{"city":"Istanbul"}}}]},
      {"role":"tool","name":"get_weather","content":"{\"temp_c\": 31, \"cond\": \"gunesli\"}"},
      {"role":"assistant","content":"Istanbul 31 derece ve gunesli."}],
     tools=[weather])

# 4) generation prompt (what the model sees before it must answer)
show("[4] add_generation_prompt=True",
     [{"role":"user","content":"Merhaba"}], agp=True)
