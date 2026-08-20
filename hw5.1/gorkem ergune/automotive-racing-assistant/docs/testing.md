# Testing & Reliability (Phase 4 / Phase 5)

This project separates three kinds of checks and never mixes their numbers:

1. **Deterministic unit tests** — `tests/` (Python `unittest`, HTTP mocked, no network).
2. **Live model evaluation** — `tests/eval/run_eval.py` (requires Ollama + Qwen).
3. **Manual reliability verification** — the failure scenarios below, exercised via the tests.

No extra dependencies were added: the suite uses only the standard library (`unittest`,
`unittest.mock`). `pytest` was **not** added.

---

## 1. Deterministic unit tests (`tests/`)

Run from the project root:

```bash
python -m unittest discover -s tests -t .
```

**46 tests, all passing, ~0.00s** (no network, no Ollama). The `tests/__init__.py` adds
`ollama_asistan/` to `sys.path` so tests can `import tools`, `import ollama_client`, `import chat`.

| File | Covers |
|------|--------|
| `test_tools.py` | `check_part_status` / `get_race_regulations` (known, unknown, empty, missing arg, aliases, disclaimer); `get_weather` and `internet_search` **failure paths** with `requests` mocked (network down, city not found, DDG→Wikipedia fallback, no fabrication). |
| `test_schemas.py` | Exactly 4 tools; names match the registry; schema structure (`type`, `function.name/description/parameters`, `required` ⊆ `properties`); JSON-serializable. |
| `test_dispatch.py` | `run_tool_calls`: known tool, unknown tool, tool exception, missing/invalid args, multiple calls, Windows-safe logging. |
| `test_ollama_client.py` | `chat`: correct `/api/chat` endpoint, model, `tools` only when given, temperature; connection error → `RuntimeError`; non-200 → `RuntimeError`; malformed response (no `message`) → `RuntimeError`. HTTP layer mocked. |
| `test_tool_loop.py` | `run_conversation` orchestration with a **scripted fake `chat`**: normal answer stops; single/multiple tool calls; unknown tool; tool exception; **stops at `MAX_TOOL_ROUNDS`**; custom max rounds; `RuntimeError` propagates for `main` to handle. |
| `test_prompt.py` | Prompt guards: `MAX_TOOL_ROUNDS == 5`; all four tool names present; DEMO limitation stated; **no call-syntax examples** (Phase-3 leakage guard); current-year hint present in the `internet_search` query schema. |

### Testability refactor (minimal)
To test orchestration without Qwen, the bounded loop was extracted from `main()` into
`chat.run_conversation(messages, chat=..., model=..., tool_schemas=..., max_rounds=...)`.
`main()` calls it. Behavior is unchanged; `chat` is injectable so tests use a scripted fake.

---

## 2. Live model evaluation (`tests/eval/run_eval.py`)

Requires a running Ollama and `qwen2.5:7b-instruct`. **Not** run by `unittest` (it is not a
`test_*.py` module). It reproduces the Phase-3 24-scenario set (categories A–H):

```bash
python tests/eval/run_eval.py            # temp 0 (reproducible-ish)
python tests/eval/run_eval.py --temp 0.1 # the app's real temperature
```

**Determinism caveat (measured):** even at `temperature=0` (greedy), this model/hardware is
**not perfectly deterministic** for a few borderline questions. Case **A3**
("Bir yarışa hazırlanırken genel olarak nelere dikkat edilir?") flips between *no-tool* and
*get_weather* across runs — including for the original baseline prompt. So the headline A–G
score oscillates between **18/21 and 19/21** solely because of A3. The **stable** result across
runs is: Part status 3/3, Regulations 3/3, Weather 3/3, Internet search 3/3, Multi-tool 2/2,
**0 text-leakage**, and unknown-info (H) never fabricated. Treat this as a small scenario
evaluation, not a statistical benchmark.

---

## 3. Reliability scenarios verified (Phase 4)

Each maps to an executed deterministic test unless noted:

| # | Scenario | How it fails gracefully | Verified by |
|---|----------|-------------------------|-------------|
| 1 | Ollama unavailable | `chat` raises `RuntimeError` (clear TR message); `main` catches and prints it; loop continues | `test_ollama_client.test_connection_error_becomes_runtimeerror`, `test_tool_loop.test_runtimeerror_propagates_for_caller_to_handle` |
| 2 | Unknown tool | `run_tool_calls` returns "…adinda bir arac yok."; loop continues | `test_dispatch.test_unknown_tool_is_graceful`, `test_tool_loop.test_unknown_tool_does_not_crash` |
| 3 | Missing arguments | tool defaults (`component=""`, `topic=""`) → clear validation message; no exception | `test_dispatch.test_missing_arguments_none`, `test_tools.test_missing_argument_uses_default` |
| 4 | Invalid arguments (unknown component/topic) | "…mevcut değil / bulunmuyor" + list of known values; no fabrication | `test_tools.test_unknown_component_is_graceful`, `test_unknown_topic_is_graceful` |
| 5 | Tool exception | caught in `run_tool_calls` → "Arac calistirilamadi: …"; loop continues | `test_dispatch.test_tool_exception_is_caught`, `test_tool_loop.test_tool_exception_does_not_crash` |
| 6 | Weather API failure | `requests` error caught → "Hava durumu alinamadi: …" | `test_tools.test_network_failure_is_graceful`, `test_city_not_found` |
| 7 | Internet search failure | DDG→Wikipedia fallback; both down → "Arama yapilamadi"; empty → "sonuc bulunamadi"; **no fabricated results** | `test_tools.test_ddg_down_falls_back_to_wikipedia_empty`, `test_both_down_is_graceful` |
| 8 | Maximum tool rounds | loop bounded by `MAX_TOOL_ROUNDS = 5`; terminates even if the model always calls a tool | `test_tool_loop.test_repeated_tool_calls_stop_at_max_rounds` |
| 9 | Windows console (cp1254) | `sys.stdout.reconfigure("utf-8")` at startup **plus** `_log_tool_call` falls back to ASCII on `UnicodeEncodeError` | `test_dispatch.test_log_tool_call_never_raises` |

Malformed model responses (missing `message`) are also handled → `RuntimeError`
(`test_ollama_client.test_malformed_response_missing_message`).

---

## 4. Search query year (Phase-3 follow-up)

The Phase-3 evaluation saw the model occasionally invent a stale year ("2023") for
current-information searches. Two fixes were tried:

- **System-prompt line** stating the current year → **rejected**: measured to regress the
  no-tool baseline (case A3 flipped to `get_weather` 5/5 with the line, 5/5 no-tool without it).
- **Schema-side hint** on `internet_search`'s `query` description ("use the current year for
  current/latest info; keep a user-provided year") → **adopted**: scoped to the search tool,
  keeps all 46 unit tests green, does not affect the stable no-tool cases, and in a live check
  produced `query="Formula Student 2026"`. The year is computed at runtime
  (`tools.CURRENT_YEAR`), not hardcoded.

Deterministic guard: `test_prompt.test_current_year_grounding_in_search_schema`.

---

## 5. Known limitations

- **A3 / borderline questions** are unstable at temp 0; the A–G score is 18–19/21 depending on
  the run. Ambiguous boundary cases (`G` category) remain 2/4 by design and are **not** forced
  to a particular tool (see `docs/prompt_design.md`).
- The live evaluation requires Ollama; there is no offline substitute for real tool-selection
  behavior (by design — unit tests cover orchestration, not model judgement).
- Search-query year grounding is a *hint*; a 7B model may still occasionally deviate.
