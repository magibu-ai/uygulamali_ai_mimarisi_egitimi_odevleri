# TASKS.md

# Automotive Racing Assistant

## Phase 0 — Environment

- [x] Inspect original repository
- [x] Inspect `ollama_asistan/chat.py`
- [x] Inspect `ollama_asistan/tools.py`
- [x] Inspect `ollama_asistan/ollama_client.py`
- [x] Inspect `ollama_asistan/medical_rag.py`
- [x] Verify Python
- [x] Verify Ollama
- [x] Pull `qwen2.5:7b-instruct` (already present locally)
- [ ] Run original template
- [x] Verify existing tool-calling flow

---

## Phase 1 — Automotive Scenario

- [x] Rename assistant identity
- [x] Update system prompt
- [x] Set Qwen2.5 7B
- [x] Remove medical terminology
- [x] Create `race_data.py`
- [x] Add vehicle component data
- [x] Add racing regulation data

---

## Phase 2 — Tools

### Internet

- [x] Preserve `internet_search`
- [x] Verify search functionality
- [x] Test search failure

### Weather

- [x] Implement/verify `get_weather`
- [x] Test location handling
- [x] Test failure handling

### Vehicle

- [x] Implement `check_part_status`
- [x] Add brake pads
- [x] Add tires
- [x] Add engine oil
- [x] Add battery
- [x] Add brake discs
- [x] Handle unknown components

### Regulations

- [x] Implement `get_race_regulations`
- [x] Add brakes
- [x] Add tires
- [x] Add safety
- [x] Add electrical
- [x] Add driver
- [x] Add technical inspection
- [x] Handle unknown topics

---

## Phase 3 — System Prompt

- [x] Define assistant role
- [x] Define scenario
- [x] Define tools
- [x] Define tool-selection rules
- [x] Define when not to use tools
- [x] Define tool result handling
- [x] Add hallucination prevention
- [x] Define mock-data limitations
- [x] Define multi-tool behavior
- [ ] Add few-shot examples (evaluated and INTENTIONALLY OMITTED: call-syntax examples
      caused text-leakage on qwen2.5:7b-instruct — see docs/prompt_design.md)
- [x] Test prompt with Qwen2.5 7B
- [x] Optimize failed cases

---

## Phase 4 — Testing

Deterministic `unittest` suite (47 tests, tests/) + live scenario eval (tests/eval/run_eval.py).
See docs/testing.md.

- [x] Direct answer (loop stops on no tool call; live A)
- [x] Weather (failure paths mocked; live D)
- [x] Part status (unit tests; live B)
- [x] Regulations (unit tests; live C)
- [x] Internet search (failure/fallback mocked; live E)
- [x] Multi-tool (loop multi-call test; live F)
- [x] Unknown information (unknown component/topic; live H non-fabrication)
- [x] Invalid arguments
- [x] Tool failure (tool exception caught)
- [x] Maximum tool rounds (bounded loop test)

---

## Phase 5 — Reliability

All verified by deterministic tests (see docs/testing.md reliability matrix).

- [x] Ollama connection failure (ConnectionError -> RuntimeError, surfaced by main)
- [x] Malformed tool call (missing function/name -> graceful message)
- [x] Unknown tool
- [x] Missing arguments (tool defaults -> validation message)
- [x] Invalid arguments
- [x] Tool exception (caught in run_tool_calls)
- [x] Search failure (DDG->Wikipedia fallback, no fabrication)
- [x] Weather failure (graceful message)
- [x] Unknown component
- [x] Unknown regulation
- [x] Infinite-loop protection (MAX_TOOL_ROUNDS = 5 enforced)

---

## Phase 6 — Documentation

README.md written with actually-captured conversations and verified test results.

- [x] Project overview
- [x] Assignment goals
- [x] Architecture
- [x] Technologies
- [x] Installation
- [x] Ollama setup
- [x] Model setup
- [x] Usage
- [x] Tool documentation
- [x] System prompt strategy
- [x] Real conversation #1 (no-tool)
- [x] Real conversation #2 (part status)
- [x] Real conversation #3 (regulations)
- [x] Real conversation #4 (weather)
- [x] Multi-tool conversation (weather + part status)
- [x] Tool call logs
- [x] Testing results (47/47 deterministic; live eval)
- [x] Limitations
- [x] Future improvements
- [x] Project structure
