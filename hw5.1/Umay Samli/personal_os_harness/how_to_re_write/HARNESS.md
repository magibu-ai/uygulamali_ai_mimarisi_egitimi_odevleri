# How I Would Rewrite the Python Harness

This guide describes a clean rewrite of `personal_planning_harness` as a local
Python laboratory. It is different from the [production rewrite](README.md):
there is no Spring backend or React frontend here.

The rewrite should preserve validated behavior, not copy the current files line
by line. Keep the current repository available as the executable reference until
the replacement passes the same tests and agent transcripts.

## Goals

The rewritten harness should:

- Remain local, single-user, and easy to run.
- Use direct HTTP for Ollama.
- Use PostgreSQL through Psycopg 3.
- Keep planning and memory in independent databases.
- Keep plain, ordered SQL applied manually with `psql`; do not add Flyway.
- Provide a real interactive CLI for read, proposal, preview, approve, reject,
  and conversation workflows.
- Make deterministic behavior testable without PostgreSQL or Ollama.
- Make provider and persistence adapters replaceable at explicit seams.
- Never let model-authored text bypass validation or approval.

## Chosen stack

I would make these choices up front:

| Concern | Choice | Reason |
| --- | --- | --- |
| Python | 3.12+ for a clean rewrite | Modern typing while staying widely supported |
| Dependencies | `uv`, `pyproject.toml`, and `uv.lock` | One authoritative locked environment |
| CLI | Typer | Already sufficient for commands, help, prompts, and testing |
| PostgreSQL | Psycopg 3 and `psycopg_pool` | Explicit SQL and real PostgreSQL behavior |
| Ollama | Direct HTTP with one typed client | No SDK coupling and easy fake-session tests |
| External DTO validation | Pydantic v2 | Generate JSON Schema and strictly validate model/provider input |
| Internal domain values | Frozen dataclasses and enums | Keep domain logic independent of Pydantic and providers |
| Tests | pytest plus real PostgreSQL integration tests | Fast domain tests and accurate persistence tests |
| Quality | Ruff and strict Pyright | Automated formatting and typed module interfaces |
| Local database | Docker Compose with a pinned PostgreSQL image | Reproducible setup without production orchestration |

Python 3.11 can remain the minimum if compatibility matters. The important
decision is to pick one minimum version and enforce it consistently in package,
type-checker, CI, and documentation configuration.

## Target module shape

```text
src/personal_os/
  cli/
    app.py
    commands/
    renderers/
  agent/
    loop.py
    instructions.py
    output_verification.py
  tools/
    registry.py
    planning_reads.py
    planning_writes.py
    memory_reads.py
    memory_writes.py
    calculations.py
  application/
    planning_queries.py
    planning_proposals.py
    memory_queries.py
    memory_proposals.py
    approval.py
    interfaces.py
  domain/
    common/
      identifiers.py
      intervals.py
      validation.py
    planning/
      tasks.py
      dependencies.py
      effort.py
      availability.py
      scheduling.py
    memory/
      experiences.py
      lessons.py
      evidence.py
    proposals/
      model.py
      preview.py
      state_machine.py
  adapters/
    postgres/
      pool.py
      planning_reads.py
      planning_writes.py
      planning_unit_of_work.py
      memory_reads.py
      memory_writes.py
      memory_unit_of_work.py
    ollama_http/
      client.py
      messages.py
      parsing.py
    external_context/
      web.py
      weather.py
  config.py
```

The dependency direction should be:

```text
CLI -------> agent -------> tools -------> application -------> domain
 |                                                   ^
 +---------------------------------------------------+

Ollama HTTP adapter ---- implements the agent's provider interface
PostgreSQL adapters ---- implement the application's persistence interfaces
```

The CLI may call application queries directly for explicit inspection commands;
conversation requests take the longer path through the agent and tools.

The domain must not import Typer, Psycopg, Pydantic, requests/httpx, or Ollama
payload types. Tools should call application modules rather than assembling
repository results and domain calculations themselves.

Do not split every class into a separate file merely to match this tree. A module
should expose a small interface and hide meaningful behavior. Merge shallow files
when their separation gives callers no leverage.

## What I would change from the current harness

### 1. Introduce a real application layer

Current read tools use narrow reader protocols, which is a good seam, but they
still coordinate several repository reads themselves. Move orchestration such as
free/busy input gathering into application query modules:

```python
result = planning_queries.get_free_busy(request)
```

The tool should validate its external DTO, call one application interface, and
serialize one result. The same application query can then serve the CLI, tests,
and future interfaces.

### 2. Separate database records from domain values

Database row records should stay in the PostgreSQL adapter. Domain modules should
receive domain values with validated invariants. This prevents column layout and
nullable migration details from becoming the interface every caller learns.

### 3. Generate tool schemas from DTOs

Handwritten JSON Schema and runtime parsing can drift apart. Define a strict
Pydantic request model for each tool, forbid extra fields, and generate the
Ollama function schema from that model. Convert the validated DTO to domain
values before calling application logic.

Result DTOs should also be versioned. They must retain source labels, bounds, and
stable error codes.

### 4. Design proposals before write repositories

Do not begin with generic CRUD. Implement the proposal state machine, canonical
preview serialization, validation issue format, hash binding, drift detection,
expiry, idempotency, and purge rules first. Write repositories should exist only
to support those use cases.

Planning and memory need separate proposal interfaces and units of work. Shared
domain code may describe lifecycle rules, but no transaction may span both
databases.

### 5. Add one composition root

Create settings, pools, repositories, application modules, tools, provider, and
agent in one composition function called by the CLI. Constructors elsewhere
should receive dependencies rather than reading environment variables or opening
connections.

This makes independent database outage tests and fake adapters straightforward.

### 6. Treat final model text as untrusted output

Provider payload validation and safe tool execution are not enough. A model can
read the correct tool result and state a different timezone, duration, ID, or
proposal status.

For critical facts:

- Render structured confirmations in deterministic code.
- Check identifiers, times, durations, and proposal state against tool results.
- Reject claims of applied writes unless the apply result exists.
- Preserve the full assistant/tool transcript for diagnostics without logging
  sensitive payloads by default.

### 7. Make the CLI an implemented interface, not a future note

Add commands in this order:

```text
personal-os config
personal-os db check
personal-os planning tasks
personal-os planning schedule
personal-os memory lessons
personal-os proposal show
personal-os proposal approve
personal-os proposal reject
personal-os chat
```

The CLI renders results but does not contain business rules. Approval commands
must require the proposal ID, revision, and preview hash shown to the user.

## Clean rewrite order

### 0. Preserve a reference baseline

1. Make the current suite green.
2. Save fake-Ollama transcripts for success, invalid arguments, unknown tools,
   database outages, and tool-round exhaustion.
3. Create golden free/busy and DST fixtures.
4. Capture planning and memory schema verification output.
5. List behavior that is intentionally unfinished.

Exit gate: the rewrite has a stable comparison suite and does not accidentally
treat planned behavior as implemented behavior.

### 1. Build package and configuration foundations

1. Create the `src/` package and CLI entry point.
2. Configure `uv`, Ruff, strict Pyright, and pytest.
3. Implement typed settings and non-secret public rendering.
4. Validate URLs, timezones, positive limits, and optional database URLs.
5. Add fake settings builders for tests.

Exit gate: install, help, version, config, lint, format, types, and unit tests pass
without databases or Ollama.

### 2. Build domain primitives

Implement UUID wrappers only if they prevent real mix-ups; otherwise retain UUID
with clear type aliases. Then implement:

1. Aware instants and local wall-time inputs.
2. Half-open intervals, clipping, union, and subtraction.
3. DST gap and fold handling.
4. Validation issue codes and aggregation.
5. Task and lesson lifecycle enums.

Exit gate: pure tests cover interval boundaries, adjacency, invalid timezones,
DST gaps, DST folds, and stable issue serialization.

### 3. Build the local databases

1. Pin PostgreSQL in Compose.
2. Create separate owner, migrator, and runtime roles.
3. Create separate planning and memory databases.
4. Keep independent ordered SQL directories.
5. Add verification SQL for roles, schemas, grants, and required objects.
6. Document that initialization runs only for an empty volume.

Use manual `psql` for this harness. Flyway starts only when the future backend
owns the schemas.

Exit gate: a fresh volume initializes, verification passes, and each runtime role
is rejected by the other database.

### 4. Implement bounded read adapters

1. Build independent pools with explicit lifecycle.
2. Add row-decoding helpers inside the adapter.
3. Implement small, ordered, bounded planning reads.
4. Implement small, ordered, bounded memory reads.
5. Test recursive CTEs, JSONB, full-text search, timestamps, and outage mapping
   against PostgreSQL.

Exit gate: either repository can fail independently and no query accepts an
unbounded model-controlled limit.

### 5. Implement application queries

1. Task tree and ancestor queries.
2. Dependency views.
3. Schedule and planning context queries.
4. Free/busy input gathering and deterministic calculation.
5. Experience search.
6. Confirmed relevant lessons and due reviews.

Application interfaces should return domain/application results, not Psycopg
rows.

Exit gate: application queries pass with both PostgreSQL adapters and in-memory
fakes.

### 6. Implement read tools

1. Create strict request and result DTOs.
2. Generate provider-neutral tool declarations.
3. Namespace tools as `planning.*`, `memory.*`, `calc.*`, `time.*`, `web.*`,
   and `weather.*`.
4. Label all database results with their source.
5. Enforce result bounds again at the tool seam.
6. Surface only confirmed lessons as established planning input.

Exit gate: schema tests prove declarations and runtime validation agree, and
tools contain no SQL.

### 7. Implement the direct-HTTP agent

1. Define provider-neutral message and tool-call records.
2. Validate all Ollama response shapes at the provider seam.
3. Check model tool support through `/api/show`.
4. Preserve complete assistant and tool history.
5. Enforce a positive maximum tool-round count.
6. Return expected argument and dependency failures as tool results.
7. Add output verification for critical facts.

Exit gate: fake transcripts cover all branches and a separate live smoke test
works with the configured Ollama model.

### 8. Implement proposal foundations

1. Define immutable proposal revisions.
2. Define canonical preview JSON and hashing.
3. Define stable validation issues.
4. Define pending, applied, rejected, superseded, and expired transitions.
5. Define drift and replay behavior.
6. Define sensitive payload purge behavior.

Exit gate: pure state-machine tests cover stale, changed, replayed, rejected,
expired, failed, and successful paths.

### 9. Implement planning staged writes

1. Parse operations into typed commands.
2. Read authoritative state inside one planning transaction.
3. Validate the complete proposed graph and schedule.
4. Store proposal and exact preview without changing domain state.
5. On approval, lock, revalidate, verify revision/hash, and apply atomically.
6. Record a minimal apply attempt.

Exit gate: PostgreSQL tests prove every failed path changes no planning domain
state and repeated approval is idempotent.

### 10. Implement memory staged writes

Repeat the planning proposal pattern with memory-specific privacy rules:

1. Experiences remain separate from lessons.
2. Candidate lessons require mapped experience evidence.
3. Confirmation requires supporting evidence.
4. Contradictory evidence remains visible.
5. Rejected or expired sensitive proposal content is purged.
6. Export, correction, retirement, and erasure remain possible.

Exit gate: privacy and lifecycle acceptance tests pass without accessing the
planning connection.

### 11. Compose the CLI

1. Add read commands.
2. Add deterministic proposal preview rendering.
3. Add approve and reject commands.
4. Add interactive chat using the same application modules and tools.
5. Render each requested tool name and its validated arguments before the final
   assistant answer, while excluding tool results that may contain sensitive data.
6. Make Ctrl-C, EOF, outage, timeout, and validation failure behavior clear.

Exit gate: an end-to-end local test can inspect, discuss, preview, approve, and
read back one planning change and one independent memory change.

### 12. Add higher-level workflows and external adapters

Only after the safety loop works:

1. Backward deadline planning and replanning.
2. Experience capture and lesson-review batches.
3. Safe arithmetic/calculation tools.
4. A timezone-aware current-date tool backed by an injectable clock.
5. Weather through a provider-neutral request/result interface.
6. Requested web/news/research retrieval through provider-neutral interfaces.
7. Calendar and route adapters later.

External input is bounded and provenance-labelled. Public web fetching must
restrict schemes and ports, reject credentials and non-public resolved addresses,
revalidate redirects, allow-list content types, and cap bytes, extracted text,
redirects, and time. Weather results include resolved location/timezone,
retrieval time, provider URL, uncertainty, alert availability, and an explicit
out-of-horizon state. External content may inform a proposal but cannot mutate
state or supply trusted instructions.

## Current-to-rewrite mapping

| Current location | Rewritten responsibility |
| --- | --- |
| `config.py` | Typed configuration at the package root |
| `db/models.py` | Split into adapter row types and domain/application result types |
| `db/planning.py` | Planning PostgreSQL read/write adapters |
| `db/memory.py` | Memory PostgreSQL read/write adapters |
| `planning/free_busy.py` | Common interval and planning availability domain modules |
| `tools/_arguments.py` | Strict Pydantic request DTOs |
| `tools/core.py` | Registry plus provider-neutral tool contracts |
| `tools/planning.py` | Thin planning tool adapters over application queries/commands |
| `tools/memory.py` | Thin memory tool adapters over application queries/commands |
| `tools/external.py` | Thin time, web, and weather tool adapters over provider-neutral interfaces |
| `providers/ollama_http.py` | Ollama message, parsing, and client adapter package |
| `providers/web.py`, `providers/weather.py` | Bounded external-context adapters |
| `agent.py` | Agent loop, instructions, and output verification package |
| `cli.py` | Composition root plus small command/rendering modules |
| `db/migrations/` | Preserve as independent manual SQL streams |

## Suggested implementation slices

1. Packaging, settings, CLI shell, and quality checks.
2. Interval/DST domain module and golden tests.
3. Compose, roles, schemas, and verification.
4. Planning bounded reads and integration tests.
5. Memory bounded reads and integration tests.
6. Application queries and in-memory fakes.
7. Generated read-tool schemas and adapters.
8. Direct Ollama HTTP client and bounded agent.
9. Proposal state machine and canonical preview.
10. Planning proposal transaction.
11. Memory proposal transaction and privacy cleanup.
12. Interactive CLI and end-to-end acceptance test.

Each slice should leave the repository runnable and keep routine tests independent
of Ollama and PostgreSQL.

## Do not add during the harness rewrite

- Flyway or a second migration framework.
- A web backend or React frontend.
- Cross-database transactions or foreign keys.
- A generic CRUD or SQL tool.
- An ORM that hides the PostgreSQL behavior being evaluated.
- Vector storage before evaluation proves full-text search is insufficient.
- Microservices, message brokers, cloud deployment, or Kubernetes.
- Automatic semantic writes without immutable preview and explicit approval.
- Raw conversation or hidden-reasoning storage by default.

## Rewrite completion gate

The rewritten harness is ready to replace the current one only when:

- All preserved unit, integration, schema, and transcript fixtures pass.
- Planning and memory can each operate while the other database is unavailable.
- The CLI exposes the implemented read and proposal workflows.
- No semantic write occurs before approval.
- Every approval is revision/hash bound, revalidated, atomic, and idempotent.
- Critical final model claims match authoritative structured results.
- Routine tests require neither Ollama nor PostgreSQL.
- Real PostgreSQL and live Ollama checks are available as explicit opt-in suites.
- The README describes only commands that exist.
- A rollback consists of selecting the old harness with the same untouched
  databases or restoring independently verified backups.
