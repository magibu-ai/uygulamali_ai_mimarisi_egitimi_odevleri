---
title: melomani
emoji: 💿
colorFrom: purple
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: A CD shop assistant that can only speak from its database
---

# melomani

A CD shop assistant that knows nothing about what the shop sells.

Everything it can truthfully say — which records are in stock, what they cost,
what is on them, what you have ordered — comes back from a real SQLite database
through tool calls. The model supplies language and judgement. The database
supplies every fact.

**Live demo:** https://huggingface.co/spaces/Erenyanic/melomani

You will need your own Hugging Face token; the page explains why below.

## The scenario

A small shop selling CDs. A customer can browse the catalogue, describe a taste
and get recommendations, fill a cart, place an order and ask after it. Six tools
cover that, split across reads and writes:

| Tool | | What it does |
| --- | --- | --- |
| `search_albums` | read | Filtered search over title, artist, genre, year, price, stock |
| `get_album_details` | read | Tracklist, label, country, tags, price, live stock |
| `recommend_albums` | read | Scores the catalogue against a stated taste |
| `add_to_cart` | **write** | Adds copies, returns the full cart and running total |
| `checkout` | **write** | Deducts stock in one transaction, creates the order |
| `check_order_status` | read | Reads an order back out and derives its fulfilment stage |

The catalogue is a curated fixture of 90 albums with 879 tracks, across 29
genres — trip-hop, post-punk, shoegaze and jazz through the metal family
(thrash, death, black, progressive, heavy, doom, groove) and the rock family
(classic, prog, hard, psych, grunge, alt), plus hip-hop, soul, ambient and
anadolu-rock. Artist, label and year metadata is real; prices and stock levels
are invented.

### Recommendation, without the model making it up

`recommend_albums` is the reason this scenario is more than a shopping cart, and
it is also the easiest place for an assistant to start inventing. So the model
does not do the recommending. It only relays what the customer said — artists,
albums, genres, moods — and the score is computed in SQL over stored columns:

```
tag_hits × 3  +  genre_hit × 6  +  artist_hit × 2  +  era_hit × 2
```

Each result comes back with a `why` assembled from the columns that actually
scored:

```json
{
  "album_id": 3, "title": "Maxinquaye", "artist": "Tricky", "score": 20,
  "why": "same genre (trip-hop); shares debut, nocturnal, sampling; released 1995, close to the era you like"
}
```

That sentence is derived data, not model prose. The assistant quotes it.

## How hallucination is actually prevented

Prompt instructions are in `agent/prompts.js` and they help. They are not what
holds, because they were observed not to. These do:

- **Write tools take `album_id`, never a title.** `add_to_cart` declares
  `album_id: integer` and no name field at all. A title the model invented has
  no id, so it cannot become a cart line or an order. There is a test asserting
  the schema keeps it that way.
- **Empty results carry an instruction, not an empty list.** A bare `[]` is what
  a model papers over with a plausible-sounding record. `search_albums` returns
  `"No album in the catalogue matches these filters. Do not suggest titles that
  are not in the catalogue…"`.
- **Every total is computed in SQL.** Prices are stored in kuruş as integers and
  formatted once, in the repository (`"369,00 ₺"`). The model is told to quote
  that string and do no arithmetic. An order's total is summed from its own rows
  after insertion, never passed in.
- **Prices are frozen at checkout.** `order_items` captures `unit_price_kurus`,
  so repricing the catalogue cannot change what an old order was worth.
- **Unknown ids, tools and arguments return structured errors** that name what
  was wrong, so the model corrects itself instead of guessing again.
- **Session scoping.** `session_id` is injected by the router from trusted
  context and is not in any tool schema, so the model cannot read or modify
  another visitor's cart or orders even if it tries.

## Two things the model got wrong

Both were found by running the loop against a live model, not by reasoning about
it. Both are in `docs/live-model-trace.txt` as raw terminal output.

**It described the wrong record.** Asked about *Mezzanine* — which the
recommender had not returned — Qwen2.5-7B called `get_album_details(album_id: 3)`,
the nearest id it happened to have, and presented *Maxinquaye*'s tracklist under
the name Mezzanine. Two causes, both fixed: genre was underweighted against
incidental tag overlap so Mezzanine never surfaced, and there was no rule about
resolving a named title to an id. Genre now scores 6 against 3 per shared tag,
and the prompt requires searching for a title before assuming an id.

**It bought something nobody asked for.** Asked only *what songs are on it*, the
model called `add_to_cart` and then `checkout` in the same turn, and stock was
deducted for an order the customer never placed. The prompt already forbade it.

Wording was not going to fix that, so `checkout` is gated on the customer-turn
boundary. The first call in a turn returns `CONFIRMATION_REQUIRED` with a preview
and commits nothing; only a call in a *later* turn places the order. Because a
turn ends only when the model stops calling tools and replies, this guarantees
the preview reached the customer and they answered. On the next run the gate
caught the unrequested checkout, an invented customer name, an invented order id
and a call to a tool that does not exist — all four in a single turn.

## Architecture

```
index.html            the page
web/app.js            DOM only — chat, token entry, live trace panel
web/styles.css
web/vendor/           sql.js (SQLite compiled to WebAssembly)

agent/schemas.js      the six tool definitions, JSON Schema
agent/prompts.js      system prompt
agent/router.js       validation, type coercion, dispatch
agent/loop.js         the tool-calling loop

tools/catalog.js      search_albums, get_album_details, recommend_albums
tools/cart.js         add_to_cart, checkout (gated), check_order_status

db/schema.sql         8 tables
db/seed.sql           90 albums, 879 tracks, 445 tags
db/repository.js      every SQL statement in the project
db/vocab.js           mood/genre normalisation
db/adapter.node.js    node:sqlite   — local, file-backed
db/adapter.browser.js sql.js        — in the page, persisted to IndexedDB

scripts/demo.mjs      terminal runner
tests/                66 tests
```

### One repository, two databases

`db/repository.js` takes a handle exposing `all`, `run` and `transaction`, and
cannot tell which adapter it has. Locally that is `node:sqlite`, built into
Node 22, writing an ordinary `melomani.db` file. In the browser it is sql.js —
the same SQLite engine compiled to WebAssembly, running the same `schema.sql`
and `seed.sql`, persisted to IndexedDB.

So the tests exercise real SQL against a real file-backed database with no
browser involved, and `scripts/demo.mjs` runs the identical code path the Space
runs. `tests/browser-adapter.test.mjs` then runs the whole repository a second
time through sql.js under Node, because a divergence between the two engines —
`getRowsModified()` after the stock guard, say — would let the Space oversell
while every other test stayed green.

### Why the loop is plain

Native tool calling only: schemas go up in `tools`, the provider returns
`message.tool_calls`, the router executes them, results go back as `role: "tool"`
messages. No prompt-injected call protocol and no text parsing, because every
model offered in the UI was checked to return real `tool_calls` first. No agent
framework, because the whole point is that the routing is visible.

## Running it locally

Node 22.5 or newer. There is nothing to install — `node:sqlite` is built in and
sql.js is vendored.

```bash
git clone https://github.com/Erenyanic/melomani.git
cd melomani

# the tool layer end to end: no token, no network, no model
node scripts/demo.mjs --db-only

# tests (real SQLite, both adapters)
npm test

# with a model — get a token at https://huggingface.co/settings/tokens
export HF_TOKEN=hf_...
node scripts/demo.mjs                       # interactive
node scripts/demo.mjs --script              # scripted end-to-end run
node scripts/demo.mjs "Ne tür caz var?"     # one-shot
node scripts/demo.mjs --model=meta-llama/Llama-3.3-70B-Instruct:groq

# the web interface
python3 -m http.server 8000                 # then open http://localhost:8000
```

The database is created at `melomani.db` on first run and rebuilt from
`schema.sql` + `seed.sql` if deleted. `MELOMANI_DB=:memory:` keeps it in memory.

## Model

Hugging Face Inference Providers, over the OpenAI-compatible endpoint at
`router.huggingface.co/v1/chat/completions`. Four models, each pinned to a
provider that was verified to return real `tool_calls`:

| Model | Provider |
| --- | --- |
| `Qwen/Qwen2.5-7B-Instruct` (default) | featherless-ai |
| `meta-llama/Llama-3.3-70B-Instruct` | groq |
| `Qwen/Qwen2.5-72B-Instruct` | novita |
| `Qwen/Qwen3-32B` | featherless-ai |

The `:provider` suffix is not decoration. A bare model id resolves against
whichever providers the caller's account has enabled, and returns
`model_not_supported` for most tokens. Pinning removes that dependency.

`meta-llama/Llama-3.1-8B-Instruct` was tested and dropped — novita returns
`model features function calling not support` for it.

### Why you have to bring your own token

A static Space has no server, so it has no secret of its own to spend. Inference
runs from your browser on your token, which is kept in that browser's local
storage and sent only to `router.huggingface.co`. Nothing is proxied and there
is no backend to log it.

This is also the honest arrangement: the account that built this ran out of
monthly inference credit partway through development — visible as the `HTTP 402`
at the end of `docs/live-model-trace.txt`. A shared token would have made the
demo dead for everyone.

## Terminal output

The assignment asks for a log showing a user input and the tool calls it
triggered. Two are checked in:

- **`docs/live-model-trace.txt`** — captured runs against the live model,
  including both defects above and the gate catching four invented values in one
  turn.
- **`docs/tool-layer-trace.txt`** — the tool layer end to end with no model.
  Regenerate any time with `node scripts/demo.mjs --db-only`; needs no token.

In the browser the same trace is the right-hand panel: every call, its arguments
and the exact JSON the database returned, clickable to expand.

## Known limits

- **The catalogue is a fixture.** 90 albums, chosen so the recommender has real
  tag and genre overlap to score. Adding one means reusing existing tags, or it
  will not be reachable by taste — there is a test asserting every tag is shared
  by at least three albums, because a tag on one record scores nothing.
- **Fulfilment is simulated.** `check_order_status` derives a stage from elapsed
  time on a compressed scale (preparing → packed → shipped → delivered over ten
  minutes) so the progression is observable in a demo.
- **The database is per-browser.** Your cart and orders are yours; nothing is
  shared between visitors and nothing leaves your machine. "Reset shop" rebuilds
  it from the SQL. The snapshot in IndexedDB is stamped with a seed version, so
  when the catalogue changes a returning visitor is rebuilt automatically rather
  than left browsing last month's stock — at the cost of their cart.
- **Small models stay literal.** Qwen2.5-7B sometimes lists results verbatim
  rather than summarising them. The 70B options handle the conversation better
  at a higher cost per call.

## Note on the model

This project uses a stock open-source model. My fine-tuned
[Qwen3.5-4B cooking LoRA](https://huggingface.co/Erenyanic/qwen3.5-4b-seasoned-advice-lora)
is unrelated and is not used here: it is adapter-only, needs a GPU to run at
usable speed, and a static Space has neither. Assignment brief permits stock
open-source models, so nothing is lost.

## License

MIT.
