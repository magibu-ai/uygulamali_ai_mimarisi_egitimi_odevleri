---
license: mit
language:
  - tr
task_categories:
  - question-answering
  - sentence-similarity
tags:
  - medical
  - rag
  - semantic-search
  - turkish
  - chromadb
size_categories:
  - 1K<n<10K
configs:
  - config_name: chunks
    default: true
    data_files:
      - split: train
        path: data/ehekim_chunks.parquet
  - config_name: benchmark
    data_files:
      - split: test
        path: data/benchmark_questions.parquet
---

# e-hekim — Turkish Medical Semantic Search + RAG

An end-to-end system for **semantic search** and **retrieval-augmented generation**
over a vector database built from health articles published by 14 Turkish hospitals.

Two modes are selectable from a single interface:

| Mode | API key | What it does |
|---|---|---|
| **Semantic search** | **not required** | Vectorizes the question and returns chunks ranked by cosine similarity. This mode alone is enough to evaluate the project without any credentials. |
| **RAG** | the user's own key | Passes the chunks that clear the threshold to an LLM and produces a Turkish answer with `[1]`, `[2]` citations. |

The corpus and the user interface are Turkish, because the source articles are
Turkish; this document is in English.

---

## Two independent refusal layers

Preventing hallucination needs more than a similarity cut-off, so the system refuses
in two distinct places and reports which one fired via `refusal_reason`.

**Layer 1 — retrieval gate (`below_threshold`).** If the best-matching chunk scores
below the cosine threshold, our own code emits the refusal and **the LLM is never
called at all**. No prompt can talk the system out of this, because no prompt is
ever sent.

> `Bu sorunun cevabı belgelerimde bulunmamaktadır.`
> *("The answer to this question is not found in my documents.")*

**Layer 2 — model gate (`model_insufficient_context`).** A similarity score cannot
tell whether a passage actually *answers* a question, only that it is on the same
topic. "What is Hodgkin lymphoma?" and "What is the five-year survival rate in
Hodgkin lymphoma?" retrieve the same chunk with a high score, yet only the first is
answerable from it. The model is therefore instructed — as the opening principle of
its system prompt — that it has **no knowledge of its own** for this task, and must
decline rather than fill the gap from its pretrained knowledge:

> `Bu bilgiyi bilmiyorum; bu konuda size yardımcı olamıyorum.`
> *("I do not know this information; I cannot help you with this.")*

Partial answers, hedges such as "the documents do not say, but generally…", and
adding even a single detail absent from the passages are all forbidden. Measured
behaviour on the live system:

| Question | Best similarity | Outcome |
|---|---:|---|
| "Bitcoin bugün kaç dolar?" | 0.4298 | Layer 1 — LLM never invoked |
| "Hodgkin lenfomada 5 yıllık sağkalım oranı yüzde kaç?" | 0.6153 | Layer 2 — passages passed, model declined |
| "Eritrositler nerede üretilir ve nerede yıkılır?" | 0.5931 | Answered, with citation |

---

## Technology stack

| Layer | Choice | Note |
|---|---|---|
| Vector database | **ChromaDB** 1.5 (`PersistentClient`) | Collection created with `hnsw:space=cosine`; distance = `1 − cosine`. |
| Embeddings | **`magibu/embeddingmagibu-200m`** | 768 dimensions, 8,192-token context, L2-normalized output. |
| Backend | **FastAPI** + Uvicorn | Binds to `127.0.0.1` only. |
| Frontend | Dependency-free HTML/CSS/JS | Strict CSP; no inline script or style. |
| LLM access | **OpenAI SDK** | Every provider speaks the OpenAI wire format; only `base_url` changes. |
| Data | [`umutertugrul/turkish-hospital-medical-articles`](https://huggingface.co/datasets/umutertugrul/turkish-hospital-medical-articles) | CC BY 4.0, ~25K articles, 14 hospitals. |

**Supported models** — DeepSeek (direct) and OpenRouter (multi-provider):

- `deepseek-v4-flash` (default, thinking enabled), `deepseek-v4-pro`
- Via OpenRouter: `anthropic/claude-haiku-4.5`, `openai/gpt-4.1-mini`,
  `google/gemini-2.5-flash`, `meta-llama/llama-3.3-70b-instruct`

---

## Quick start

Requirements: Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/). A GPU is optional —
everything runs on CPU, only the initial indexing is slower.

```bash
git clone https://huggingface.co/datasets/erenyanic/e-hekim && cd e-hekim
uv venv && uv pip install -e ".[dev]"

cp .env.example .env          # add HUGGINGFACE_TOKEN (the source dataset is gated)

uv run python scripts/ingest.py       # ~5 min on GPU — 1,000 articles to 2,714 chunks
uv run python scripts/benchmark.py    # threshold analysis (optional, writes a report)
uv run python -m ehekim.api           # http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000`. **Semantic search** works immediately. For RAG, paste
your own API key into the field in the interface.

Tests: `uv run pytest -q` (104 tests).

> **Note:** `.env` is used **only by the offline scripts** (downloading the source
> data and uploading to the Hub). The web application never reads an LLM provider key
> from the environment under any circumstances.

---

## 1. Article selection and chunking

**Selection.** 24,612 raw articles, then cleaning (empty bodies, texts shorter than
400 characters, non-`http` URLs, cookie/KVKK boilerplate, **duplicate URLs and
byte-identical bodies**), leaves 20,549 eligible articles, from which **1,000 are
selected**.

Rather than mirroring the raw distribution, selection is **balanced across the 14
hospitals** (71–72 articles per source). In the raw data Acıbadem (6,071) and
Memorial (5,264) alone make up half the eligible pool; proportional sampling would
have handed half the index to two institutions' house style and topic choices. An
equal quota buys wider medical coverage for the same 1,000 documents, which is what
makes both the positive and the negative benchmark questions meaningful. Selection is
**deterministic** under `seed=42`.

**Chunking strategy: paragraph-aware, token-bounded, with overlap (hybrid).**

- **Target 512 tokens, 64-token overlap**, 32-token minimum.
- Paragraph integrity comes first: whole paragraphs are packed greedily until the
  token budget is exhausted.
- A paragraph that overflows the budget is split into **sentences** (Turkish
  abbreviations such as `Dr.`, `vb.`, `mg.` and initials such as `M. Ali` are not
  treated as sentence ends).
- If a single sentence still overflows, it is split on a **token window** as a last
  resort.

*Why this strategy?* The corpus is hospital patient-education prose: short titled
sections ("Belirtileri nelerdir?", "Nasıl tedavi edilir?"). Paragraph boundaries are
genuine semantic boundaries, and blind N-token splitting routinely severs a symptom
list from the condition it belongs to. But paragraph lengths are wildly uneven — a
one-line introduction next to a 900-token procedure description — so splitting on
`\n\n` alone yields chunks that are both too small to stand alone and too large to be
precise. The hybrid approach avoids both failure modes.

> **A corpus-specific detail:** only **35%** of the articles contain blank lines
> (`\n\n`); the rest separate paragraphs with a **single `\n`** (about 44 line breaks
> per article on average). The chunker therefore treats any run of newlines as a
> paragraph boundary. Had it looked for `\n\n` only, two thirds of the corpus would
> have been processed as one enormous paragraph.

**Result:** 1,000 articles produce **2,714 chunks** (2.71 per article).
Tokens: mean 420, median 477, p95 534, max 586.

## 2. Vector database schema

`data/ehekim_chunks.parquet` — the required delivery schema plus auxiliary metadata:

| Column | Type | Description |
|---|---|---|
| `url` | string | Source link of the article the chunk belongs to |
| `chunk_text` | string | The chunked text |
| `chunk_vector` | list\<float32\>[768] | Embedding vector (L2-normalized) |
| `chunk_id` | string | `{parent_id}-{index}` |
| `parent_id` | string | Article identifier (first 16 hex of the URL's SHA-1), the parent-child link |
| `title` | string | Article title |
| `__source` | string | Source hospital (one of 14) |
| `chunk_index` | int | Position within the article |
| `token_count` | int | Token count of the chunk |

The same data is stored in ChromaDB in the `ehekim_chunks` collection in cosine space.

## 3. Embedding model

**`magibu/embeddingmagibu-200m` — 768 dimensions, 8,192-token context, ~200M parameters.**

Why it was chosen:

- **Turkish-focused.** Adapted from a multilingual teacher through *tokenizer surgery*
  and *offline distillation*; its TR-MTEB average of 69.5 and STSbTR Spearman of 0.798
  put it close to `ytu-ce-cosmos/turkish-e5-large` at a substantially smaller size.
- **Long context.** 8,192 tokens is far more than 512-token chunks need, so moving to
  larger chunks later would not force a change of model.
- **Size/quality balance.** 768 dimensions give 2,714 × 768 float32 ≈ 8 MB, and the
  whole corpus vectorizes in about 4.5 minutes on a laptop GPU (GTX 1650).
- **L2-normalized output.** The dot product equals cosine similarity directly, so
  Chroma's cosine distance is exactly `1 − similarity`.

> ⚠️ **The model is asymmetric.** Queries and documents must be encoded with different
> prefixes: `task: search result | query: ` and `title: <title> | text: `. The wrong
> prefix silently depresses similarities and invalidates the threshold calibration.
> All encoding therefore goes through a single class (`ehekim.embedding.Embedder`),
> and a test asserts that the string we build is **byte-identical** to the model's own
> registered prompts. The article title is written into the document prefix with its
> real value.

## 4. Evaluation set (30 questions)

The repository ships two viewable tables, selectable in the dataset viewer:

| Config | Split | Rows | Contents |
|---|---|---:|---|
| `chunks` (default) | `train` | 2,714 | The vector database: `url`, `chunk_text`, `chunk_vector` + metadata |
| `benchmark` | `test` | 30 | The evaluation set with its measured outcomes |

```python
from datasets import load_dataset

chunks = load_dataset("erenyanic/e-hekim", "chunks",    split="train")
tests  = load_dataset("erenyanic/e-hekim", "benchmark", split="test")
```

The benchmark table holds **20 positive** questions, each written by reading an actual
indexed chunk and paired with the URL of the article that answers it, and **10
negative** questions whose answers are certainly absent from the corpus (software,
sport, finance, history, space, automotive, veterinary medicine). Columns:

| Column | Description |
|---|---|
| `id`, `label` | `P01`–`P20` / `N01`–`N10`; `positive` or `negative` |
| `question` | The question put to the system |
| `topic`, `expected_answer`, `expected_url` | Ground truth for positives |
| `rationale` | Why a negative is out of scope |
| `best_similarity` | Highest cosine similarity actually retrieved |
| `expected_source_rank` | Rank at which the expected article was retrieved |
| `top_match_title`, `top_match_url` | What the retriever returned first |
| `system_decision`, `expected_decision`, `correct` | Answer/refuse outcome at the 0.53 threshold |

**Result: 30/30 correct** — all 20 positives answered, all 10 negatives refused.

## 5. Threshold analysis

`scripts/benchmark.py` runs that 30-question set through the real retrieval path and
sweeps the threshold from 0.20 to 0.90, regenerating both the report and the benchmark
table above. Full report: [`data/threshold_report.md`](data/threshold_report.md).

**Separation is decisive:**

| Group | Mean | Min | Max |
|---|---:|---:|---:|
| Positive (20) | 0.7376 | **0.5819** | 0.8784 |
| Negative (10) | 0.2749 | 0.1615 | **0.4777** |

There is a **0.1042** gap between the lowest positive and the highest negative, so
**every** threshold in `[0.50, 0.58]` separates the two sets perfectly (F1 = 1.000,
accuracy = 1.000, zero false answers on negatives).

**Chosen threshold: `0.53`** — the midpoint of that plateau. Picking either edge would
leave the system on a cliff: at 0.50 the highest negative (the Bitcoin question,
0.4777) is only 0.02 away, and at 0.58 the lowest positive (pharyngeal cancer, 0.5819)
is a mere 0.002 away. The midpoint maximizes the margin against both failure modes.

| Threshold | Positives answered | False answers on negatives | F1 |
|---:|---:|---:|---:|
| 0.30 | 20/20 | 2/10 | 0.952 |
| 0.45 | 20/20 | 1/10 | 0.976 |
| **0.53** | **20/20** | **0/10** | **1.000** |
| 0.65 | 17/20 | 0/10 | 0.919 |
| 0.80 | 5/20 | 0/10 | 0.333 |

**Source recall:** the expected article appears in the top 5 for 20/20 questions, and
ranks first for 15/20.

**An honest caveat.** This measurement is at the *article (URL)* level. Retrieving the
right article does not guarantee retrieving the *chunk* that carries the answer, and
the distinction bites in practice, which is what motivated the next section.

## 6. Parent-context expansion

Chunking necessarily cuts articles at arbitrary points, and the highest-scoring chunk
is not always the one holding the answer sentence. Observed case: for "Eritrositler
nerede üretilir ve nerede yıkılır?", chunk 1 of the RBC article scores 0.5931 (it
discusses low counts) while chunk 0 — which states verbatim that erythrocytes are
produced in red bone marrow and broken down in the spleen — scores 0.5176 and falls
**below** the threshold. Given only the passing chunk, the model correctly refused a
question the corpus genuinely answers.

So once the threshold gate has decided the query *is* in scope, each passing chunk
brings its immediate siblings (`chunk_index ± 1`, via `parent_id`) along as context.

- The gate is not weakened: expansion happens strictly **after** it and only around
  chunks that already cleared it, so it can never turn an out-of-scope question into
  an answered one.
- The cosine values shown in the interface remain the **real, unexpanded** scores.
- The numbering given to the model and the list rendered in the interface are
  identical, and siblings added purely for context are marked `—` ("komşu bölüm"), so
  a `[1]` citation always points at the `[1]` the user can see.

## 7. Security

Because the user types an API key into the browser, credential handling is the central
design constraint of the project:

- **The server never stores a key.** It arrives in the `X-Provider-Key` **header**
  (not the URL — Uvicorn's access log records paths, so a key in a query string would
  leak into our own logs), is used for exactly one call, and then goes out of scope.
- **No persistence in the browser.** No `localStorage`, `sessionStorage`, cookie or
  URL is used; the key lives only in the input value and for the duration of a single
  `fetch`. Reloading the page discards it.
- **Structural validation.** Before a key is placed in an `Authorization` header it is
  checked to be a single line of printable ASCII, which stops CRLF header injection at
  the door.
- **Log and error sanitization.** Providers echo the submitted key back in 401 bodies
  (DeepSeek does). Every log record passes through a scrubbing filter, and every error
  relayed to the client passes through the same scrubber, which replaces
  credential-shaped substrings with `[REDACTED]`.
- **Response models cannot carry a key.** No Pydantic model has such a field, and
  tests assert the key never appears in a response body.
- **No CORS, bound to `127.0.0.1`, strict CSP** (`default-src 'self'`, no inline script
  or style), `nosniff`, `frame-ancestors 'none'`, `Cache-Control: no-store` on API
  responses, and a 64 KB request-body cap.
- **Prompt injection.** Retrieved text is fenced inside a `<belgeler>` element and
  declared untrusted in the system prompt; the model is told to execute no instruction
  found inside it.
- **Upload protection.** `scripts/push_to_hub.py` works from an explicit allow-list,
  then applies a deny-list and a secret scan; on any finding it aborts **before sending
  a single byte**, and after uploading it re-lists the remote repository to verify both
  that nothing sensitive leaked and that every expected file arrived.

## 8. LLM configuration

```python
client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=...,
    reasoning_effort="medium",                     # as specified in the brief
    extra_body={"thinking": {"type": "enabled"}},  # thinking enabled
)
```

> DeepSeek's documentation defines `low | high | max` for `reasoning_effort` and, for
> compatibility, **maps `medium` onto `high`**. The requested value (`medium`) is sent
> verbatim; this provider-side mapping is recorded here rather than silently worked
> around.

OpenRouter models are called with plain completions (no thinking parameters).

## 9. Project structure

```
src/ehekim/
  config.py       Settings, prompts, threshold and refusal constants (holds no secrets)
  chunking.py     Paragraph-aware, token-bounded, overlapping chunker
  corpus.py       Article cleaning, balanced selection, chunk records
  embedding.py    SentenceTransformer wrapper with the asymmetric prompts
  vectorstore.py  ChromaDB (cosine) plus sibling-chunk access
  retrieval.py    Threshold gate, context expansion, RAG prompt, refusal detection
  llm.py          Provider catalogue, OpenAI SDK call, error normalization
  security.py     Key validation and credential scrubbing
  api.py          FastAPI application, security headers, endpoints
scripts/          ingest.py, benchmark.py, push_to_hub.py
frontend/         index.html, app.js, styles.css  (no dependencies)
tests/            104 tests — security, chunking, selection, retrieval, HTTP
data/             benchmark_questions.json, threshold_report.md,
                  benchmark_results.json, ingest_manifest.json, *.parquet
```

## 10. API

| Endpoint | Key | Description |
|---|---|---|
| `GET /api/health` | — | Readiness and chunk count |
| `GET /api/config` | — | Threshold/top-k defaults, provider catalogue, refusal messages |
| `POST /api/search` | **no** | Semantic search; chunks with their cosine values |
| `POST /api/ask` | `X-Provider-Key` | RAG; refuses below the threshold without calling the model |
| `GET /api/docs` | — | OpenAPI interface |

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hodgkin lenfomayı ayıran hücre tipi nedir?","top_k":3,"threshold":0.53}'
```

## Licence and disclaimer

The code is MIT. The source data is CC BY 4.0
([umutertugrul/turkish-hospital-medical-articles](https://huggingface.co/datasets/umutertugrul/turkish-hospital-medical-articles)).
This system is **for information only**; it is not medical diagnosis, treatment or
prescribing advice.
