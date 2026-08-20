# System Prompt Design & Optimization (Phase 3)

Local model: **`qwen2.5:7b-instruct`** (Ollama native tool calling, `temperature=0.1` in the app).

This document records how the `SYSTEM_PROMPT` in `ollama_asistan/chat.py` was evaluated and
optimized for reliable tool selection. It describes **observable behavior and engineering
decisions only** — not any hidden model reasoning.

---

## 1. Initial prompt strategy (V0)

The Phase‑2 prompt established, in Turkish and compact form:

- Assistant role and racing‑team scenario.
- The four tools (`get_weather`, `check_part_status`, `get_race_regulations`, `internet_search`).
- Keyword‑style selection rules (e.g. *component status → `check_part_status`*).
- "Do not call tools for greetings / directly answerable questions."
- Multi‑tool guidance with the umbrella example.
- Tool‑result grounding, DEMO‑data limits, and anti‑fabrication rules.

The native Ollama tool **schemas** (in `tools.py`) already teach the model each tool's name,
purpose, and arguments, so V0 deliberately contained **no function‑call syntax**.

---

## 2. Evaluation methodology

A small **scenario‑based** evaluation (not a statistically rigorous benchmark). 24 scenarios
across 8 categories:

| Cat | Meaning | Expected |
|-----|---------|----------|
| A | General / identity / advice | **no tool** |
| B | Vehicle component status | `check_part_status` |
| C | Racing regulations | `get_race_regulations` |
| D | Weather | `get_weather` |
| E | Internet search | `internet_search` |
| F | Multi‑tool (2 independent needs) | 2 tools |
| G | Ambiguous / boundary | case‑specific (with accepted alternatives) |
| H | Unknown information | no fabrication |

Each scenario is driven through the **real app path** (`SYSTEM_PROMPT` + `ollama_client.chat`
+ `tools.TOOL_SCHEMAS` + the same bounded loop). For every scenario we record the tool
call(s), arguments, tool result, and final answer, then score pass/fail.

**Noise control.** Single‑sample runs at `temperature=0.1` proved noisy: the same case flipped
pass/fail across runs (e.g. B2, C2). The **authoritative before/after comparison was therefore
run at `temperature=0` (greedy, near‑deterministic)** so that differences reflect the prompt,
not sampling. The deployed app keeps `temperature=0.1`; `0` is used only to make the evaluation
reproducible.

---

## 3. Observed behavior and problems discovered

Three prompt variants were tried and measured against V0. Each revealed a concrete problem:

**Experiment 1 — few‑shot examples written as call syntax**
Examples like `check_part_status(component="fren balatalari")` were added.
**Result: catastrophic regression.** Qwen2.5‑7B began emitting the tool call as **plain text
in the answer** (e.g. the final message literally read `check_part_status(component="lastikler")`
or leaked `{"name": ..., "arguments": ...}`) instead of using the native tool‑calling channel.
6 previously‑correct cases broke. **Lesson: never put function‑call syntax in the prompt of a
model that has native tool calling — it teaches the model to imitate that syntax as output.**

**Experiment 2 — prose examples + a "when unsure, ask a clarifying question" clause**
Text leakage mostly disappeared, but the clarify clause caused the model to **ask questions
instead of calling obvious tools** (e.g. "Güvenlik gereksinimleri hakkında ne biliyorsun?" →
a clarifying question instead of `get_race_regulations`). One residual leak remained.

**Experiment 3 — rules‑only, with aggressive "open‑ended → no tool / a keyword is not enough"**
No leaks, but the strong anti‑trigger framing made the model **over‑conservative on legitimate
borderline status questions** ("Lastiklerin durumu nasıl?" → clarifying question instead of
`check_part_status`). Deterministic score dropped to 16/21.

A separate methodological finding: the "over‑triggering" on open‑ended advice questions that
appeared at `temperature=0.1` (V0 sometimes calling tools for "nelere dikkat edilir?") **did not
reproduce at `temperature=0`** — it was largely sampling noise, not a stable V0 defect.

---

## 4. Prompt changes made (and why)

The final prompt keeps V0's proven structure and makes **one** substantive, non‑regressing
addition, while explicitly rejecting the harmful techniques above:

1. **Added an explicit negative rule for `internet_search`** (assignment Rule 6):
   *"Do not use `internet_search` for information a dedicated tool (weather/part/regulation)
   already provides."* Previously this lived only in the tool schema, not the policy.
2. **Made the multi‑tool rule say "independent (BAGIMSIZ) information"** to discourage cascading
   several tools for a single‑fact question.
3. **Reinforced the anti‑leak rule** in "tool‑result handling": do not print call syntax / JSON
   to the user. (Kept as policy text, never as an example.)
4. **Did NOT add few‑shot examples** — the evaluation showed they cause text leakage on this 7B.
5. **Did NOT add a clarify‑when‑unsure clause** — it suppressed legitimate tool calls.

---

## 5. Before / after results (deterministic, `temperature=0`)

Tool‑selection accuracy over categories A–G (24 scenarios; H judged separately by
non‑fabrication):

| Metric                          | Before (V0) | After (final) |
| ------------------------------- | ----------: | ------------: |
| Overall tool‑selection (A–G)    |       19/21 |         19/21 |
| No‑tool                         |         3/3 |           3/3 |
| Part status                     |         3/3 |           3/3 |
| Regulations                     |         3/3 |           3/3 |
| Weather                         |         3/3 |           3/3 |
| Internet search                 |         3/3 |           3/3 |
| Multi‑tool                      |         2/2 |           2/2 |
| Ambiguous / boundary            |         2/4 |           2/4 |
| Text‑leak cases                 |           0 |             0 |

**Unknown information (Category H):** both prompts avoid fabrication. The final prompt declines
more cleanly — e.g. "Aracımızın motor beygir gücü kaç?" is answered with **no tool call** and a
plain "this value is not in the demo dataset," whereas V0 fetched motor‑oil status for a
horsepower question before noting the value was unavailable.

**Honest conclusion:** the optimization did **not** raise the headline A–G number (it was
already 19/21). Its value is: (a) explicitly encoding all required selection rules — including
the previously‑implicit `internet_search` boundary; (b) **empirically ruling out** two tempting
but damaging techniques (call‑syntax few‑shot, clarify‑clause) that each regressed the model;
(c) slightly better unknown‑information handling; and (d) verifying zero text‑leakage. We do not
claim an accuracy gain that the measurements do not support.

**Remaining weakness:** the ambiguous/boundary category (2/4). Questions such as "Frenler
hakkında ne düşünüyorsun?" and "Fren sistemiyle ilgili güncel bilgi verir misin?" are genuinely
under‑specified; the model sometimes picks a plausible but non‑target tool. These are inherently
ambiguous rather than clear prompt failures.

---

## 6. Final prompt design principles

For a 7B local model with **native** tool calling:

1. **Policy, not syntax.** The system prompt should state *when* to use each tool. It must never
   contain function‑call syntax, JSON, or tool names written as calls — the schema already
   defines the tools, and examples of call syntax induce text‑leakage.
2. **Don't over‑suppress.** "Never call a tool unless certain" and "ask a clarifying question
   when unsure" both suppress legitimate calls. Prefer a light "don't call tools for general
   chat/advice" rule.
3. **One explicit negative boundary** (`internet_search` vs the dedicated tools) is worth more
   than many positive examples.
4. **Ground and label.** Answer only from real tool results; never present DEMO data as real
   telemetry or official regulations; if a tool reports "not available," say so plainly.
5. **Measure at `temperature=0`** for reproducible prompt comparisons; treat single‑sample
   `0.1` runs as noisy.

The full final prompt lives in `ollama_asistan/chat.py` (`SYSTEM_PROMPT`).

---

## 7. Phase 4 / 5 follow-up (reliability & formal tests)

Phase 4/5 kept the Phase-3 prompt as the baseline and added a deterministic `unittest`
suite plus reliability hardening. Two prompt-adjacent findings:

- **Search-year grounding.** Adding a "current year is {year}" line to the *system prompt*
  was measured to **regress** the no-tool baseline: case A3 flipped to `get_weather` 5/5 with
  the line vs 5/5 no-tool without it. It was **reverted**. The hint was instead placed on the
  `internet_search` **query schema** (scoped to search-query construction), which fixed the
  year (live: `query="… 2026"`) without touching the stable no-tool cases.

- **Temp-0 is not fully deterministic here.** Re-running the same V0 prompt at `temperature=0`
  produced both 19/21 and 18/21 across runs — the difference is entirely case A3 (an
  open-ended advice question) flipping. The stable core (part/regulation/weather/search 3/3,
  multi-tool 2/2, 0 leaks) holds across runs. The "19/21" baseline should be read as
  "18–19/21, A3-dependent," not a fixed number.

Full test architecture, the reliability scenario matrix, and how to run everything are in
`docs/testing.md`.
