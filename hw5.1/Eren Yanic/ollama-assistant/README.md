# Local Assistant

A terminal assistant that runs entirely on your own machine through [Ollama](https://ollama.com),
with eight tools it can call: web search, weather, world clock, currency and crypto conversion,
a calculator, sandboxed Python execution, Turkish and US market data over MCP, and a private
portfolio ledger.

It is built for a 4 GB graphics card. Every decision below — one model, eight tools, an 8k
context window — follows from that constraint, and the interesting engineering is in making a
4-billion-parameter model call the right tool with the right arguments, reliably, in two languages.

**The scenario: a personal finance and daily-life assistant for Turkey.** It knows what you own,
what it is worth today, what the lira is doing, and it can still tell you whether to take an
umbrella. Your holdings live in a SQLite file on your machine and are never sent anywhere.

---

## Sample conversations

All three sessions below were recorded on the hardware described in *Performance*, exactly as
printed. The `🔧` lines are the tool calls the assistant made; `↳` is what the tool returned.

### Daily life and the portfolio

```
you Merhaba! İstanbul'da hava nasıl ve şu an saat kaç?
  🔧 get_weather(location=İstanbul)
  ↳ Istanbul, Republic of Türkiye: partly cloudy, 27.3°C (feels like 27.3°C), humidity 70%, wind 32.4 km/h. Today …
  🔧 get_datetime(location=İstanbul)
  ↳ İstanbul (Europe/Istanbul): 2026-08-13 15:38 (Thursday, UTC+0300)

assistant İstanbul'da hava kısmen bulutlu ve sıcaklık 27,3°C (hava hissi 27,3°C) ile 70% nem,
          32,4 km/saat hızla rüzgarla birlikte. Bugün sıcaklık 23,6–28,5°C arasında, yağış
          olasılığı %0'dır. Şu an saat 15:38'dir.

you Portföyüme 10 adet THYAO ekle, tanesi 285 liradan aldım
  🔧 portfolio(action=add, symbol=THYAO, quantity=10, cost=285)
  ↳ Added. You now hold 10 THYAO (bist), average cost 285.00 per unit.

assistant Portföyünüzde 10 adet THYAO eklendi. Her birinin ortalama maliyeti 285 TL'dir.

you Bir de 0.05 BTC ekle
  🔧 portfolio(action=add, symbol=BTC, quantity=0.05, cost=0)
  ↳ Added. You now hold 0.05 BTCTRY (crypto).

assistant Portföyünüzde 0.05 BTC eklendi. (Maliyet bilgisi belirtilmedi, bu yüzden fiyatı
          kayıtlı değildir.)

you Portföyüm şu an ne durumda?
  🔧 portfolio(action=value)
  ↳ - BTCTRY: 0.05 x 3,033,421.00 = 151,671.05 TRY - THYAO: 10 x 307.50 = 3,075.00 TRY | cost 2,850.00, P/L +225.0…

assistant Portföyünüz şu an şu durumda:
          - 0.05 BTC: 151.671 TL
          - 10 adet THYAO: 3.075 TL (maliyeti 2.850 TL, kâr: +225 TL, %7.9)
          Toplam değer: 154.746 TL.

you Bu toplamın euro karşılığı ne kadar?
  🔧 convert_currency(amount=154746.05, from_currency=TRY, to_currency=EUR)
  ↳ 154746 TRY = 2,807.0933 EUR (1 TRY = 0.01814 EUR). Reference rate published 2026-08-12 (daily, not intraday).

assistant Portföyünüzün toplam değeri şu an 2.807 euro (EUR) karşılık gelmektedir.
          (Dönem: 2026-08-12, günlük kuru).
```

Note what happens in the third turn: no purchase price was given, so none was recorded, and the
valuation reports the bitcoin without a profit figure rather than inventing one. Note also that
`BTC` was stored as `BTCTRY` — a bare coin name has no price, a traded pair does.

### Markets, arithmetic and search

```
you Apple hissesi kaç dolar, kaç lira eder?
  🔧 borsa(action=quote, symbol=AAPL)
  ↳ ## metadata market: us symbols: AAPL timestamp: 2026-08-13T12:40:32 source: yfinance successful_count: …

assistant Apple hissesi şu an 302.25 dolar ediyor ve 14.434,55 lira (1 dolar = 47,7570 lira)
          karşılığına gelir. Fiyat, 2026-08-13 saat 12:40'ta ölçüldü.

you 18500 liranın yüzde 18 KDV'si ne kadar?
  🔧 calculate(expression=18500 * 0.18)
  ↳ 18500 * 0.18 = 3330

assistant 18.500 liranın %18'si 3.330 TL'dir.

you Bugün Türkiye ekonomisinde öne çıkan haber ne?
  🔧 web_search(query=Türkiye ekonomisinde bugün öne çıkan haberler)
  ↳ Summary: Türkiye'de öne çıkan ekonomi haberleri arasında Türkiye Sigorta'nın SGK iş birliğiyle emeklilik güven…

assistant Bugün Türkiye ekonomisinde öne çıkan haber, Türkiye Sigorta'nın SGK ile birlikte
          emeklilik güvencesini güçlendirmesi ve tarımda üretici enflasyonun Temmuz'da
          yeniden yükseldiğine dair haberlerdir.
```

The symbol was asked for in Turkish, the ticker resolved on the US market, and the lira figure is
exact — the assistant did not multiply anything itself. Why that matters is explained under
*Guard rails*.

### Code execution, and refusing it

```
you How many days are there between today and 1 January 2027?
  🔧 run_python(code=from datetime import datetime, timedelta  today = datetime(2…)

The assistant wants to run this Python:
  │ from datetime import datetime, timedelta
  │ today = datetime(2026, 8, 13)
  │ new_year = datetime(2027, 1, 1)
  │ days_diff = (new_year - today).days
  │ print(days_diff)
Run it? [y/N] n
  ↳ The user declined to run this code. Do NOT work the answer out yourself - say plainly that you cannot answer w…

assistant I cannot calculate the number of days between today and 1 January 2027 without
          running the code. Please allow me to execute the computation for you.

you Go ahead and run it
  🔧 run_python(code=from datetime import datetime, timedelta  today = datetime(2…)
  │ ... same code ...
Run it? [y/N] y
  ↳ 141

assistant Between today, 13 August 2026, and 1 January 2027, there are 141 days.
```

Refusing the run is a real answer, not a dead end: the assistant says it cannot know rather than
guessing. An earlier version guessed "262 days" here, which is why the refusal message is worded
the way it is.

---

## Requirements

| | |
|---|---|
| Ollama | running locally (`ollama serve`) |
| Python | 3.11 or newer |
| GPU | 4 GB is enough; it also runs on the CPU, more slowly |
| Disk | about 2.5 GB for the model |

## Setup

```bash
git clone <your-repository-url> ollama-assistant
cd ollama-assistant

python -m venv .venv
.venv/bin/pip install -r requirements.txt

ollama pull qwen3:4b-instruct

cp .env.example .env      # then paste your Tavily key into it (optional)

.venv/bin/python chat.py
```

Web search works without a key by falling back to DuckDuckGo; a free
[Tavily](https://app.tavily.com) key gives noticeably better results. Everything else — weather,
time, currency, markets, the calculator, Python, the portfolio — needs no key at all.

```bash
.venv/bin/python chat.py                     # interactive
.venv/bin/python chat.py --ask "dolar kaç TL?"   # one question, then exit
.venv/bin/python chat.py --model qwen3:1.7b  # a smaller, faster, less accurate model
.venv/bin/python test_tools.py               # exercise every tool, no model involved
```

In a session, `/tools` lists the tools, `/reset` clears the conversation, `/log` prints the path
of the current log file, and `exit` leaves.

---

## The eight tools

| Tool | What it does | Where the data comes from |
|---|---|---|
| `web_search` | news and facts | Tavily, falling back to DuckDuckGo |
| `get_weather` | current conditions and today's range | Open-Meteo (no key) |
| `get_datetime` | the time here or in any city | `zoneinfo`, geocoded when unknown |
| `convert_currency` | fiat and crypto conversion | Frankfurter → open.er-api, CoinGecko |
| `calculate` | one exact arithmetic expression | local, no `eval` |
| `run_python` | short programs, sandboxed | local subprocess |
| `borsa` | BIST and US shares, indices, funds, gold, oil, crypto, KAP news | [Borsa MCP](https://github.com/saidsurucu/borsa-mcp) by Said Sürücü |
| `portfolio` | your own holdings and their live value | local SQLite + the tools above |

## How it works

```
chat.py          the conversation loop, system prompt, logging, confirmations
  ├── ollama_client.py   POST /api/chat, with the context and keep-alive settings
  ├── tools.py           the eight tools, their schemas, and argument handling
  │     ├── mcp_client.py   Model Context Protocol over streamable HTTP
  │     └── portfolio.py    the SQLite ledger
  └── config.py     every setting, read from .env, plus secret redaction
```

The loop is small: your message goes to the model with the tool schemas attached; the model either
answers or asks for a tool; the tool runs and its output goes back as another message; repeat until
the model answers, up to six rounds. What makes it work on a small model is everything around that
loop.

### Fitting into the context window

A 4 GB card leaves room for a 4B model at 8192 tokens. The system prompt and eight tool schemas
already cost about 1,200 of those, so the remaining budget is defended in three places:

* **Twenty-three MCP tools are exposed as one.** The Borsa MCP server offers 23 tools; declaring
  them all would spend roughly 3,000 tokens of schema and leave the model choosing between
  near-identical options. Instead one `borsa` tool takes an `action` enum — `search`, `quote`,
  `history`, `technical`, `index`, `fund`, `news` — and `tools.py` maps each onto the real remote
  call with the right argument names. About 200 tokens, and a far easier choice to get right.
* **Every tool result is clipped** to `MAX_TOOL_CHARS` (2,600). A year of daily price bars would
  otherwise evict the conversation it was meant to inform.
* **`num_ctx` is set explicitly.** Ollama's default of 4,096 would silently truncate the tool
  definitions themselves, and nothing would report it.

### Guard rails

Each of these was written in response to something the model actually did during testing.

* **A currency code is never read as a share.** `USD` is also a real US ETF ticker, so asking the
  US market for it returns about $28 — a number that reads exactly like an exchange rate. Currency
  codes are forced to the FX market. Asked for the pair `USDTRY`, the tool refuses and names the
  tool that does answer, and the model then calls it correctly.
* **Foreign quotes carry their lira value.** Asked "what is Apple in lira", the model fetched the
  dollar price and then multiplied by a rate it invented — 3.10 in one run, 4.52 in another. So
  `borsa` converts non-lira quotes itself, exactly, and appends the result. Three prompt rewordings
  had not fixed this; moving the arithmetic out of the model did, immediately.
* **A cost is never invented.** Told "add 0.05 BTC" with no price, the model once recorded a
  purchase price of ₺1,000,000, which the next valuation reported as a 202% profit. The schema now
  states that a cost is only ever passed when the user said one.
* **Bare coin names become traded pairs.** `BTC` cannot be priced; `BTCTRY` can.
* **Broken indentation is repaired.** Small models emit `import x\n y = 1` — one stray space that
  will not compile. The compiler decides: code that already parses is never touched, and the repair
  is kept only if it makes the code parse.
* **Arguments are coerced and filtered.** `"10"` becomes `10`, invented parameters are dropped, and
  a missing required argument comes back to the model as a sentence it can act on rather than an
  exception.

### The system prompt

It states the role, lists which tool answers which kind of question, and gives ten rules. Two
lessons from tuning it:

**Where the model's language changes, its instruction-following changes with it.** Asked in English
to work out a percentage, it called the calculator; asked the same thing in Turkish, it did the sum
in its head, because its grip on an English system prompt loosens once it answers in Turkish. Three
rewordings of the rule changed nothing.

**A demonstration beats a rule.** What fixed it was replaying one short worked exchange at the head
of every conversation — a Turkish question, the `calculate` call it should produce, the result, and
the answer. Around a hundred tokens, and arithmetic routing went from missed to 4 out of 4. It is
the cheapest reliability in the project. It is also a sharp instrument: a second demonstration
involving a share price taught the model to reuse the *price* from the example, which is why the
lira conversion is handled in code instead.

### Talking to the MCP server

Market data comes from [Borsa MCP](https://github.com/saidsurucu/borsa-mcp), an open-source
Model Context Protocol server by Said Sürücü covering BIST, US markets, TEFAS funds, crypto and
TCMB data. This project connects to the hosted instance; `BORSA_MCP_URL` points it at your own.

`mcp_client.py` speaks JSON-RPC over streamable HTTP in about 190 lines: initialize, capture the
session id, send `notifications/initialized`, then call tools. Responses arrive as Server-Sent
Events, and messages are matched by JSON-RPC id, because the server may interleave notifications
before the result.

The hosted server sleeps when idle. Measured behaviour, and what the client does about it:

| Observation | Response |
|---|---|
| 503 for a few seconds while waking | retry with backoff — 2, 4, 8, 16 s |
| 20 calls half a second apart all succeeded; the same calls back to back drew 503s | a 0.5 s minimum interval between requests |
| a restarted server forgets the session (404) | reconnect once and replay the request |
| the first question of a session paid the wake-up cost | a handshake in a background thread at start-up |
| valuing a portfolio asks for the same quotes repeatedly | a 60-second result cache |
| responses decoded as ISO-8859-1, mangling Turkish names | UTF-8 forced on the stream |

---

## Security and privacy

* **Keys never leave `.env`**, which is git-ignored. The Tavily key travels in an HTTP header, not
  in a request body that might be logged, and never enters a prompt, a log line, or the terminal.
  `config.redact()` strips secret-shaped values from every log record.
* **Generated code is shown before it runs**, and does not run until you type `y`. It executes in a
  temporary directory that is deleted afterwards, under limits on memory (512 MB), CPU time,
  file size and open files, with a hard timeout.
* **The sandbox gets a bare environment** — `PATH`, `HOME` and `LANG` only. Code the model wrote
  cannot read your API keys, because they are not there. There is a test for exactly this.
* **The calculator cannot execute anything.** Expressions are parsed and walked node by node against
  an allow-list; `__import__('os').system('id')` is rejected as a matter of structure, not filtering.
* **Your portfolio stays local.** It is a SQLite file in `data/`, git-ignored. Valuing it sends
  ticker symbols to the market server, never quantities, prices paid, or totals.
* **Session logs stay local** in `logs/`, one JSONL file per session, git-ignored.

What leaves your machine, and only when the matching tool runs: your search text (Tavily), a city
name (Open-Meteo), currency codes (Frankfurter, CoinGecko), ticker symbols (the Borsa MCP server).
Nothing else — the model itself never touches the network.

If you publish your own copy of this repository, rotate your Tavily key afterwards as a matter of
routine.

## Performance

Measured on a GeForce GTX 1650 (4 GB), 16 GB of RAM, 8 cores, with `qwen3:4b-instruct` (Q4_K_M):

| | |
|---|---|
| Routing accuracy | 12 of 12 questions to the right tool |
| Typical turn | 10.6 s including the tool call |
| Simple turns (time, calculator, greeting) | 3–7 s |
| Web search turns | 20–28 s, most of it the search itself |
| Memory | 3.8 GB, about 70% on the GPU |
| Tool tests | 65 checks, all passing |

At 8192 tokens the model does not fit entirely in 4 GB and Ollama places some layers on the CPU.
That is a speed cost, not a failure. `NUM_CTX=4096` shifts the balance a little further onto the
GPU; the context is then tight enough that long market results start crowding the conversation, so
the default stays at 8192.

`qwen3:4b-instruct` was chosen because it is the largest model that fits with tool-calling support
and usable Turkish. `--model qwen3:1.7b` is faster and fits entirely in VRAM, at a real cost in
routing accuracy.

## Configuration

Everything has a working default; set these in `.env` only to change something.

| Variable | Default | Purpose |
|---|---|---|
| `TAVILY_KEY` | — | web search; falls back to DuckDuckGo without it |
| `CHAT_MODEL` | `qwen3:4b-instruct` | any Ollama model with tool support |
| `NUM_CTX` | `8192` | context window |
| `TEMPERATURE` | `0.3` | low, so tool arguments are reproducible |
| `KEEP_ALIVE` | `10m` | how long the model stays loaded between questions |
| `CONFIRM_PYTHON` | `true` | ask before running generated code |
| `PYTHON_TIMEOUT` | `15` | seconds before generated code is stopped |
| `MAX_TOOL_CHARS` | `2600` | ceiling on tool output entering the context |
| `BORSA_MCP_URL` | the hosted server | point this at your own instance to keep queries off it |
| `MCP_WARMUP` | `true` | shake hands at start-up; set false to contact the server only on demand |

## Testing

`test_tools.py` exercises all eight tools against the live APIs — the point is to prove the network
paths work, not that a mock does. It never loads the model, so it is quick and free to run.

```bash
.venv/bin/python test_tools.py            # 65 checks
.venv/bin/python test_tools.py --offline  # 37 checks, no network
```

Alongside the ordinary paths it covers the sandbox rejecting hostile input, the environment holding
no keys, secret redaction, argument coercion, and each of the guard rails described above.

## Known limitations

* **A 4B model is a 4B model.** Routing is reliable, but its prose occasionally repeats a figure
  awkwardly or mislabels a timestamp. It is a competent tool-caller, not a careful writer.
* **Programs it writes can be wrong.** `run_python` runs the code faithfully; the code came from
  the model. One benchmark run summed the primes to 1061 instead of 1060 by counting 1 as prime.
  Read the code in the confirmation prompt — that is what it is for.
* **Exchange rates are daily reference rates**, not intraday quotes. Crypto is spot.
* **The hosted market server is occasionally unavailable** for a few seconds. The client retries,
  and says plainly when it cannot get data instead of inventing a price.
* **No retrieval database.** An embedding model alongside the chat model would force Ollama to
  evict and reload the 2.5 GB of weights on every query, on this card. If you want one, run the
  embedding model on the CPU by passing `"num_gpu": 0` in its options, and keep the chat model on
  the GPU.
* **Not investment advice.** It reports data, and is told to decline recommendations.
