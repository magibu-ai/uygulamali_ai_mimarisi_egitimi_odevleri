# Personal OS Harness

An experimental command-line harness for a personalized operating system. Its foundation is an ADHD-aware planning assistant that turns natural-language goals into feasible long-term and daily plans, learns from recorded experiences, and regularly resurfaces useful lessons.

This repository is an MVP laboratory, not the production backend. It tests model behavior, tool boundaries, and two candidate PostgreSQL databases before successful designs are adapted into a future Spring backend and React frontend.

## What the harness should do

- Discuss goals and tasks through an interactive CLI.
- Ask clarifying questions when a task cannot be estimated or decomposed responsibly.
- Estimate effort, divide tasks into subtasks, and manage prerequisite relationships.
- Propose deadline-driven plans by working backward from the deadline.
- Respect recurring availability, fixed commitments, holidays, rest, and one-off blocked periods.
- Assign explicit durations and clock times to planned work without requiring every hour of a day to be planned.
- Adapt plans to personal ADHD-related patterns such as initiation difficulty, focus duration, switching cost, energy, and overwhelm without assuming that the same strategy works for everyone.
- Detect noteworthy experiences and candidate lessons, batch them for approval, map every lesson to its supporting, contradicting, or contextual experiences, and resurface confirmed lessons when relevant or due for review.
- Retrieve requested news and research papers with provenance, and use weather context for date- and location-sensitive plans.
- Let the model propose database changes through tools while deterministic code prevents invalid state.
- Preview every semantic planning or memory change and apply it only after explicit user approval. Proposal lifecycle and minimal audit bookkeeping may be stored before approval but cannot alter domain state.

The model is responsible for contextual judgment: estimation, decomposition, prioritization, and specialized planning decisions. Deterministic code is a safety boundary that validates whether a proposed plan is internally possible; it is not the primary plan generator.

## MVP boundary

The first working milestone is local and single-user. It includes:

- Two experimental PostgreSQL databases owned by this harness: planning and experience/lessons.
- An interactive chat-style CLI plus explicit inspection, validation, configuration, and approval commands.
- An Ollama-backed planning agent with read tools and staged write tools.
- Safe deterministic calculation and date/time tools for arithmetic used in estimates and plans.
- Model-created schedules checked for cycles, ordering errors, overlaps, capacity violations, and missed deadlines.
- Reproducible local PostgreSQL through Docker Compose, while retaining support for separate external planning and memory database URLs.

The following are later extension points, not core-MVP requirements:

- Route and travel planning.
- Google Calendar read/write integration.
- Vector search or external planning datasets.
- Authentication, multiple users, tenant isolation, a web backend, or a web frontend.
- AWS deployment, Kubernetes health checks, troubleshooting, approval-gated code execution, Git/MCP updates, and deployment automation.
- A deterministic optimization engine that generates the schedule itself.

Weather and requested research remain local pre-cloud milestones: they follow the core planning and experience/lesson workflows but do not depend on AWS or the future web applications.

## Core concepts

- **Task:** A goal or unit of work with status, priority, deadline, constraints, and an effort estimate.
- **Subtask:** A task nested under another task. A decomposed parent holds the total effort budget; its leaf descendants are the schedulable work.
- **Dependency:** A prerequisite relationship between two tasks. One task may be a prerequisite for many others. Self-dependencies and cycles are invalid.
- **Availability window:** A recurring clock interval in which work may be scheduled.
- **Blocked period:** Time unavailable for flexible work, including fixed commitments, sleep/rest, appointments, school, or holidays.
- **Scheduled session:** A concrete time interval assigned to a leaf task. Tasks are splittable across sessions by default.
- **Planning context:** Structured constraints plus free-text preferences and situation-specific information used by the model.
- **Experience:** A factual personal event, outcome, observation, or reflection with optional links to relevant planning entities.
- **Lesson:** A reusable conclusion supported or contradicted by experiences, with confidence, applicability, and review state.
- **Mutation proposal:** One or more database changes waiting for validation and explicit approval.

Before producing a schedule, the assistant checks the applicable daily or recurring profile and asks about missing sleep, personal/rest time, fixed commitments, and usable work windows. Explicit information controls the day: 8 hours of school, 8 hours of sleep, and 3 hours of rest leaves 5 hours. The 12-hour personal reserve is only a fallback for days whose personal plan is not fully specified; known recurring defaults are reused so the assistant asks only about gaps and exceptions.

See the [product specification](docs/product-spec.md) for intended behavior, [MVP architecture](docs/architecture.md) for the candidate data model and component boundaries, [experience and lesson specification](docs/experience-lessons.md) for the memory system, and [implementation plan](docs/plan.md) for the ordered delivery checklist.

The rewrite guides cover the [Spring Boot/React production stack](how_to_re_write/README.md)
and a [clean rewrite of this Python harness](how_to_re_write/HARNESS.md).

## Current repository status

The repository now has a tested application and PostgreSQL scaffold, but it is not yet a working planning system:

- Python 3.11 dependencies and development tools are declared in `pyproject.toml` and locked with `uv`; `requirements.txt` is a generated runtime-only compatibility export.
- The installable `src/personal_os` package provides a Typer CLI, typed configuration, non-secret `config` output, and the interactive `personal-os-chat` entry point.
- The Ollama adapter uses direct HTTP, capability-checks tool support, transports typed tool calls, and preserves complete assistant/tool history. The bounded read-only agent loop executes planning, memory, current-date, bounded web-page, and date-specific weather tools; staged-write tools remain unimplemented.
- A pinned PostgreSQL 17 Compose stack initializes independent planning and memory databases, roles, schemas, constraints, defaults, health checks, and a persistent volume.
- Planning and memory use separate plain SQL streams applied manually with `psql`; the harness has no migration-framework dependency.
- Unit tests cover configuration, CLI startup and tool-call rendering, direct-HTTP tool transport, bounded agent transcripts, query bounds, free/busy calculations, DST rejection, web-page safety limits, and normalized weather responses without requiring a running model or network. Opt-in integration tests exercise both repositories against real PostgreSQL.
- `configs/.env.example` and `db/.env.example` document non-secret local settings; `.gitignore` protects corresponding local files.
- Independent typed connection pools, bounded planning/memory read repositories and tools, deterministic free/busy calculation, provider-neutral external-context seams, read-only agent orchestration, and an interactive read-only chat command are implemented. The external tools are a narrow first slice, not the complete requested-news/paper research milestone. Write repositories, unit-of-work boundaries, proposal workflows, database inspection commands, and interactive write planning remain unimplemented.

## How to use the current harness

The current harness can initialize and inspect both databases, display validated
configuration, run tests, and run the read-only agent interactively. The agent
cannot create or modify records yet.

### Prerequisites

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/) for the locked Python environment.
- Docker with the Compose plugin.
- Ollama, with a model that advertises tool support, to run the agent example.

PostgreSQL is supplied by Compose; a host PostgreSQL installation is not needed.

### 1. Install dependencies

From `personal_planning_harness/`:

```bash
uv sync --all-groups
```

`pyproject.toml` and `uv.lock` are authoritative. `requirements.txt` is a
generated runtime compatibility export. Regenerate it rather than editing it:

```bash
uv export --locked --no-dev --no-hashes --no-emit-project -o requirements.txt
```

### 2. Configure the application and databases

On first setup:

```bash
cp configs/.env.example configs/.env
cp db/.env.example db/.env
```

The example files use local-only passwords and matching planning/memory URLs.
Change both sides together if you change a database password. Keep the two
database URLs and runtime roles separate.

Check the effective non-secret application configuration:

```bash
uv run personal-os --help
uv run personal-os config
```

The `config` command reports only whether database URLs are configured; it does
not print credentials.

### 3. Start PostgreSQL

```bash
docker compose -f db/docker-compose.yml config --quiet
docker compose -f db/docker-compose.yml up -d
docker compose -f db/docker-compose.yml ps
docker compose -f db/docker-compose.yml exec -T postgres \
  psql -U postgres -d postgres -f /opt/personal-os-db/verify.sql
```

The first startup of an empty named volume applies the bootstrap, planning, and
memory SQL streams. Restarting a container does not reapply changed initialization
files. See [the database guide](db/README.md) before applying later SQL or
recreating local data.

### 4. Start Ollama

Pull the configured model once:

```bash
ollama pull llama3.1:8b
```

Run `ollama serve` in another terminal if Ollama is not already running as a
system service. If a different model is used, update `OLLAMA_MODEL` in
`configs/.env`. The agent checks `/api/show` at startup and fails clearly if
the selected model does not advertise tool support.

### 5. Run the implemented read-only agent

Start an interactive conversation:

```bash
uv run personal-os-chat
```

Enter messages at the prompt:

```text
You> Read the planning settings and report the exact timezone.
Assistant> The planning timezone is Europe/Istanbul.
```

Use `/help` to list session commands and `/exit` or `/quit` to leave. Ctrl-C
and EOF also close the database pools and end the session. Conversation history
is preserved until the command exits.

For one message without an interactive prompt:

```bash
uv run personal-os-chat --message "What is my scheduling resolution?"
```

The command opens independent planning and memory pools, checks that the Ollama
model supports tools, and then exposes bounded `planning.*`, `memory.*`,
`time.get_current_date`, `web.scrape_page`, and `weather.get_for_date` read
tools. It cannot write and must not claim that a task, schedule, experience,
lesson, or proposal was changed. The CLI prints every model-requested function
call before the final answer, for example:

```text
You> What is today's date in Istanbul?
Tool> time.get_current_date({"timezone":"Europe/Istanbul"})
Assistant> Today is 2026-08-14 in Europe/Istanbul.
```

Example prompts for the new read tools:

```text
You> Fetch https://example.com and summarize only what the page says.
You> What is the weather forecast for Istanbul on 2026-08-16?
```

Web retrieval accepts only public HTTP(S) pages on ports 80/443, rechecks each
redirect, accepts HTML/plain text, and enforces configured byte, character,
redirect, and timeout limits. Weather uses the
[Open-Meteo forecast API](https://open-meteo.com/en/docs) through a
provider-neutral interface and returns explicit provenance, retrieval time,
resolved location, uncertainty, and `forecast_unavailable` when the provider has
no requested date or it is outside the supported 16-day forecast window.
Both sources are untrusted read-only context and cannot authorize writes.

The databases start without personal tasks or experiences. Add disposable
fixtures through integration tests or reviewed SQL while the write/proposal
interface is unfinished; direct SQL is not the future user workflow.

### 6. Run verification

Routine checks do not require PostgreSQL or Ollama:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Repository integration tests use the real local PostgreSQL databases and are
opt-in:

```bash
RUN_DATABASE_INTEGRATION=1 uv run pytest -m integration
```

Live Ollama is intentionally excluded from the routine suite; provider and agent
behavior is tested with fake HTTP responses and transcripts.

### 7. Stop local services

```bash
docker compose -f db/docker-compose.yml down
```

This preserves the named database volume. Do not add `--volumes` unless deleting
all local harness data is intentional.

### Common problems

- **Database connection refused:** wait for `docker compose ... ps` to report the
  PostgreSQL service as healthy, then run `db/verify.sql`.
- **Password authentication failed:** make the runtime passwords in `db/.env`
  match the URLs in `configs/.env`. Existing volumes retain the credentials used
  when they were initialized.
- **Ollama request failed:** confirm Ollama is running at the configured
  `OLLAMA_URL` and that the URL ends in `/api/chat`.
- **Model does not advertise tool support:** use a tool-capable Ollama model and
  update `OLLAMA_MODEL`.
- **External lookup fails:** check network access and the `EXTERNAL_*` limits.
  Private/local web destinations and non-HTML/text content are intentionally
  rejected; weather dates outside the provider horizon are reported as unavailable.
- **SQL edits appear to do nothing:** initialization scripts run only for an empty
  volume. Apply a new ordered SQL script manually; do not rely on a restart.

## Intended runtime flow

1. The user describes a goal or requests a change in the interactive CLI.
2. The model reads relevant tasks, availability, blocks, planning context, experiences, and lessons through database-specific read tools.
3. The model asks questions if essential information is missing.
4. The model proposes planning or memory mutations through the appropriate tool namespace.
5. The harness validates the proposal and presents an exact preview.
6. The user approves or rejects it.
7. An approved proposal is revalidated and committed in one transaction in its target database. Planning and memory proposals remain independent even when they arise during the same conversation.

## Roadmap

1. **Documentation:** Establish the MVP behavior, candidate schema, safety boundary, and acceptance scenarios.
2. **Foundation:** Normalize packaging, protect configuration, add Docker Compose, migrations, repositories, and CLI structure.
3. **Domain storage:** Implement planning plus experience/lesson persistence with separate migrations and tool boundaries.
4. **Agent tools:** Add database-specific read/staged-write tools, safe calculations, previews, approvals, and a complete Ollama tool-call loop.
5. **Personal OS workflows:** Add ADHD-aware planning, backward schedules, experience capture, lesson derivation, reminders, and evaluation.
6. **External context:** Add provider-neutral weather and requested news/paper research, followed later by calendar and route adapters.
7. **Production evolution:** Adapt validated designs to Spring/React, then add AWS/Kubernetes observability and tightly approval-gated operational automation.
