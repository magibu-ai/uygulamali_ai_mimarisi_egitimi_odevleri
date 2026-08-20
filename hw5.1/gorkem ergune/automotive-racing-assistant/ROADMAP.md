# ROADMAP.md

# Automotive Racing Assistant

## Phase 0 — Template & Environment

- Inspect original `ollama_asistan`
- Understand existing architecture
- Verify Python
- Verify Ollama
- Pull `qwen2.5:7b-instruct`
- Run original template
- Verify existing tool-calling flow

### Exit Criteria

The original project works locally and the architecture is understood.

---

# Phase 1 — Automotive MVP

Transform the medical assistant template into the Automotive Racing Assistant.

### Tasks

- Update assistant identity
- Update system prompt
- Set Qwen2.5 7B
- Remove medical terminology
- Create `race_data.py`
- Create vehicle component data
- Create racing regulation data

### Required Tools

- `internet_search`
- `get_weather`
- `check_part_status`
- `get_race_regulations`

### Exit Criteria

The assistant starts and can answer automotive scenario questions.

---

# Phase 2 — Tool Calling

Implement and verify reliable tool selection.

### Test Scenarios

1. Direct question → no tool
2. Weather → `get_weather`
3. Component status → `check_part_status`
4. Regulations → `get_race_regulations`
5. Current information → `internet_search`
6. Complex question → multiple tools

### Exit Criteria

The correct tool is selected for each scenario.

---

# Phase 3 — System Prompt Optimization

**Status: Completed (2026-08-13).** Scenario-based evaluation (24 cases, temp 0)
gives 19/21 tool-selection accuracy on categories A–G with 0 text-leakage; all core
single-tool categories 3/3 and multi-tool 2/2. Few-shot examples were evaluated and
intentionally omitted (they caused text-leakage on qwen2.5:7b-instruct). Remaining
weakness: inherently ambiguous boundary cases (2/4). Details: docs/prompt_design.md.

Optimize the system prompt for Qwen2.5 7B.

### Focus

- Role definition
- Tool-selection rules
- Tool boundaries
- Hallucination prevention
- Mock-data limitations
- Few-shot examples
- Multi-tool behavior
- Final response formatting

### Evaluation

Measure:

- Correct tool calls
- Missing tool calls
- Unnecessary tool calls
- Incorrect tool selection
- Hallucinated information

### Exit Criteria

The model consistently selects the correct tool for the defined scenarios.

---

# Phase 4 — Reliability

**Status: Completed (2026-08-13).** All failure modes below verified via a deterministic
`unittest` suite (47 tests, mocked HTTP — no live APIs). Reliability matrix + how-to-run:
docs/testing.md. Hardening added: default tool args, malformed-tool-call guard, malformed
Ollama-response handling, Windows-safe (`cp1254`) tool logging with ASCII fallback.

Handle:

- Ollama errors
- Tool errors
- Invalid arguments
- Unknown tools
- Missing arguments
- API failures
- Unknown data
- Tool-loop limits

### Exit Criteria

Expected failures do not crash the application.

---

# Phase 5 — Testing

**Status: Completed (2026-08-13).** `tests/` holds 47 deterministic `unittest` tests
(stdlib only; HTTP mocked) — all passing. The Phase-3 24-scenario evaluation was moved to
`tests/eval/run_eval.py` (live; requires Ollama). Deterministic unit tests, integration
(tool-loop) tests, and the live model evaluation are kept separate. See docs/testing.md.

Create reproducible tests.

Required:

- direct response
- weather
- component status
- regulations
- internet search
- multi-tool
- unknown information
- tool failure

Record actual outputs.

### Exit Criteria

All core scenarios pass.

---

# Phase 6 — Documentation

**Status: Completed (2026-08-13).** Root README.md written for academic submission: overview,
assignment mapping, scenario, architecture (+ Mermaid), setup, usage, tools, prompt strategy,
actually-captured real conversations & tool-call logs, verified test results, limitations,
future work, project structure. Supporting docs: docs/prompt_design.md, docs/testing.md.

Complete:

- README
- architecture documentation
- tool documentation
- system prompt explanation
- real conversations
- tool-call logs
- testing results
- limitations

### Exit Criteria

A new user can run the project using only the README.

---

# Phase 7 — Optional RAG

Only after all required assignment components work.

Potential implementation:

```text
User
 ↓
Qwen
 ↓
get_race_regulations
 ↓
ChromaDB
 ↓
Relevant regulation chunks
 ↓
Qwen
 ↓
Answer
```

Possible data:

- racing regulations
- technical inspection documents
- safety documents

RAG is optional and must not delay the core assignment.

---

# Phase 8 — Submission

## GitHub

`gorkemergune/automotive-racing-assistant`

## Hugging Face

`gorkemergune/automotive-racing-assistant`

### Final Checklist

- [ ] Local model works
- [ ] Ollama works
- [ ] Internet search works
- [ ] Weather works
- [ ] Part status works
- [ ] Regulations work
- [ ] Tool calling works
- [ ] Multi-tool works
- [ ] Error handling works
- [ ] README complete
- [ ] Real conversations documented
- [ ] GitHub repository ready
- [ ] Hugging Face repository ready
