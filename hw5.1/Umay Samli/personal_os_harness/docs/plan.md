# Personal OS Harness: Implementation Plan

This is the living implementation tracker for the experimental harness. Complete phases in order unless a phase explicitly says work may proceed in parallel. Update checkboxes and record important design changes as the schema and real planning behavior are tested.

The package and documentation use **Personal OS Harness**. The existing workspace directory may retain its old name locally without affecting the Python package or architecture.

## Agreed decisions

- The harness is a local, single-user MVP used to test a candidate schema before production adaptation.
- Two PostgreSQL databases are authoritative: planning and experience/lessons. Local development runs both in one Docker Compose cluster with separate database names, roles, URLs, migrations, repositories, and proposal ledgers.
- Harness schema changes use separate, sequential plain SQL streams applied manually with `psql`. The harness has no migration-framework dependency; Flyway belongs to the future core backend.
- Ollama integration uses its direct HTTP API behind a typed provider adapter.
- The CLI uses Typer.
- Planning and memory use distinct model tool namespaces, proposals, and transactions. They do not coordinate commits; optional cross-database IDs are provenance only.
- The model estimates, decomposes, and proposes plans. Deterministic code validates feasibility and database invariants.
- Every semantic planning or memory change is staged, previewed, approved against an immutable revision/hash, revalidated, and committed atomically in one target database; minimal proposal/audit control records may be stored beforehand.
- Parents store total effort budgets; descendant leaf tasks divide those budgets and receive scheduled sessions.
- Task dependencies are shared finish-to-start prerequisites; parent endpoints expand to leaves and the resulting effective leaf graph must be acyclic.
- Work is splittable by default and scheduled on a 15-minute grid.
- Planning works backward from deadlines to find latest-safe bounds, but may schedule earlier for buffers and personalized needs.
- Before scheduling, the model uses confirmed daily/recurring profiles and asks about material gaps or exceptions. Explicit sleep and personal/rest intervals replace the 12-hour fallback reserve for complete profiles.
- Structured constraints are enforced by code; free-text preferences guide the model.
- Deterministic calculation and date/time tools are part of the core MVP.
- Personalized ADHD support is based on observed and confirmed individual patterns, not universal assumptions or medical claims.
- Weather and requested news/paper research are local pre-cloud milestones using provider-neutral direct API or MCP adapters.
- Google Calendar, route planning, Spring/React production applications, and AWS/Kubernetes operational automation are later integrations.

## Phase 1 — Project foundation

- [x] Keep `pyproject.toml` and `uv.lock` authoritative; generate the runtime-only `requirements.txt` compatibility export from the lockfile.
- [x] Add application entry points and a conventional source/test package structure without coupling the domain to Ollama or the CLI.
- [x] Move the provider client out of the top-level `ollama` package and select direct HTTP behind stable application types.
- [ ] Capability-check the configured Ollama model before starting an agent session.
- [x] Add typed configuration for both PostgreSQL databases, Ollama, timezone, scheduling resolution, fallback personal reserve, daily-profile completeness, and proposal expiration.
- [x] Populate `configs/.env.example` with non-secret defaults and document local setup.
- [x] Add Docker Compose with a pinned PostgreSQL image, separate planning/memory databases and roles, a health check, and a persistent named volume.
- [ ] Add isolated test database support and disposable integration-test fixtures.
- [x] Configure separate sequential plain SQL streams for planning and memory, applied manually with `psql`.
- [x] Add formatting, linting, type-checking, and test commands.

### Completion gate

- A clean checkout can install dependencies, start both databases, run both migration streams, execute CLI help, and pass import, configuration, migration-head, and database-connectivity smoke tests.
- No secret or local database data appears in `git status`.

## Phase 2 — Candidate databases and persistence

- [x] Implement initial planning SQL for settings/daily profiles, tasks, tags, dependencies, availability, one-off/recurring blocks, sessions, work logs, planning contexts, proposals, operations, and apply attempts.
- [x] Implement independent memory SQL for experiences with temporal precision/provenance, lessons, many-to-many evidence, reviews, planning-reference tombstones, proposals, operations, and apply attempts.
- [x] Add database constraints for positive durations, 15-minute units, non-self dependencies, valid intervals, uniqueness, and allowed status values.
- [x] Add PostgreSQL exclusion protection for overlapping active task sessions.
- [x] Implement independent typed connection pools and bounded planning/memory read repositories.
- [ ] Implement database-specific write repositories and unit-of-work boundaries.
- [x] Use bootstrap-only administration plus separate owner, migrator, and least-privilege runtime roles so planning runtime code cannot write memory and memory runtime code cannot write planning.
- [x] Seed single-user defaults: `Europe/Istanbul`, 15-minute resolution, 720-minute fallback personal reserve, zero deadline buffer, proposal TTL, and reminder display limit.
- [ ] Add disposable PostgreSQL integration-test fixtures and schema upgrade/rebuild tests.

### Completion gate

- CRUD and transaction tests pass against real PostgreSQL.
- Invalid basic records are rejected by the closest appropriate layer.
- Both schemas can be rebuilt independently from sequential SQL scripts without ad hoc SQL.

## Phase 3 — Deterministic domain validation

- [ ] Implement hierarchy traversal and parent-cycle detection.
- [ ] Expand parent dependency endpoints to leaves; reject ancestor/descendant edges, expansion self-edges, and effective-graph cycles.
- [ ] Validate draft-only nullable estimates, direct-child budget reconciliation, leaf-only scheduling, and work-log-derived actual effort.
- [ ] Materialize normalized recurring availability and blocks as half-open intervals in local planning time; reject nonexistent DST times and resolve ambiguous offsets explicitly.
- [ ] Validate grid alignment, overlap, availability, load-classified blocks, explicit-or-fallback daily personal time, split/indivisible rules, and session-length limits.
- [ ] Validate prerequisite projected/actual completion, earliest starts, exact/date-only deadlines, legal task/session transitions, and planned-versus-estimated effort.
- [ ] Return stable validation codes, severities, entity IDs, and repair-oriented explanations.

### Completion gate

- Every acceptance scenario in `product-spec.md` that does not require an LLM or external service has an automated test.
- Validation is deterministic and produces no database writes.

## Phase 4 — Proposal and approval boundary

- [ ] Define versioned, allow-listed mutation operation schemas; never accept SQL fragments from the model.
- [ ] Compose proposed operations over a consistent snapshot and produce exact human-readable before/after previews.
- [ ] Persist immutable proposal revisions, canonical preview hashes, redacted source summaries, assumptions, validation, TTL/sensitivity, expiration, rejection, supersession, apply attempts, and outcomes.
- [ ] Require explicit approval using the displayed proposal ID and revision, internally bound to the preview hash.
- [ ] Capture affected row versions, re-read and fully revalidate immediately before apply, and apply atomically in the target transaction; add aggregate/serializable phantom protection before enabling concurrent writers.
- [ ] Ensure changed, expired, rejected, stale, or failed proposals cannot partially mutate domain data.
- [ ] Purge staged sensitive values after rejection/expiration while retaining only minimal redacted audit metadata; never store raw memory source conversation by default.
- [ ] Enforce one target database per proposal and at most one pending proposal per database; database-qualified approval in one domain never applies or rejects the other.
- [ ] Make repeated approval idempotent and avoid a durable ambiguous `approved` state.
- [ ] Report planning and memory results independently and verify either domain remains usable while the other is unavailable.

### Completion gate

- Integration tests prove that no semantic domain write occurs before approval and that stale, replayed, crashed, phantom, and concurrent proposals fail safely.
- Bulk, destructive, dependency, schedule, experience, and lesson operations use the same approval principles within their target database.

## Phase 5 — CLI and direct task management

- [x] Add a standalone read-only `personal-os-chat` entry point with persistent conversation history, one-shot execution, and clean exit/error handling.
- [ ] Implement the interactive loop and clear rendering for assistant text, questions, tool results, previews, warnings, and errors.
- [ ] Implement inspection commands for tasks, task trees, dependencies, schedules, availability, blocks, settings, validation, and proposals.
- [ ] Implement memory inspection commands for experiences, lessons, evidence, relevant lessons, and due reviews.
- [ ] Implement explicit proposal approval, rejection, and discard commands.
- [ ] Add direct structured commands for creating test data without the model so database and validation behavior can be evaluated independently.
- [ ] Handle EOF, interruption, database errors, and invalid input without applying pending work.

### Completion gate

- A user can configure availability, create a task graph, stage a schedule or memory record, inspect it, approve it, and query the correct database entirely from the CLI.

## Phase 6 — Ollama agent and core tools

- [x] Replace the partial client with typed Ollama configuration, stable response types, complete assistant/tool history, timeouts, capability checks, and actionable errors.
- [x] Implement the bounded multi-round read-tool loop with argument validation, recoverable tool errors, and configurable round limits.
- [x] Add bounded `planning.*` read tools for tasks, descendants, dependencies, schedules, availability, blocks, settings, context, and planning proposal records.
- [x] Add ancestor traversal and computed free/busy planning read tools with half-open interval, range-bound, and DST handling.
- [x] Add bounded `memory.*` read tools for experiences, lessons, evidence, confirmed relevance search, due reviews, review history, and memory proposal records.
- [ ] Add database-specific staged write tools that create typed proposal operations and never mutate domain tables directly.
- [ ] Reject mixed-database operation lists and prevent either tool namespace from borrowing the other's connection or permissions.
- [ ] Add safe deterministic tools for arithmetic, effort aggregation, units, date/time differences, timezone conversion, capacity, and 15-minute rounding.
- [x] Keep the current agent registry free of arbitrary expression evaluation, code execution, shell access, model-supplied SQL, and unrestricted filesystem/network tools.
- [x] Write read-agent system instructions covering clarification, authoritative tool use, unavailable writes, time semantics, and deterministic free/busy calculation.

### Completion gate

- Tool-loop tests cover multiple calls, invalid arguments, timeouts, exhausted rounds, clarification without writes, and pending-proposal preservation.
- Critical arithmetic is produced by tools and independently checked by domain validation.

## Phase 7 — Model-driven planning workflow

- [ ] Implement prompts and tools for task estimation, uncertainty, decomposition, effort-budget allocation, and specialized planning context.
- [ ] Before planning, inspect confirmed recurring/daily profiles and ask only for material missing sleep, personal/rest, commitment, availability, or exception information.
- [ ] Implement model-proposed scheduling by deriving latest-safe bounds backward from the deadline, then applying explicit buffers and personalized preferences.
- [ ] Feed validation failures back to the model for explanation or a newly staged revision; never silently repair a proposal.
- [ ] Produce clear infeasibility reports with required effort, available capacity, limiting deadline, and responsible constraints.
- [ ] Surface assumptions, confidence, tradeoffs, deadline buffer, and unmet soft preferences in previews.
- [ ] Build representative evaluation fixtures from real personal-planning scenarios and record schema/workflow findings.
- [ ] Incorporate confirmed ADHD-related preferences such as initiation support, focus duration, switching cost, energy, and recovery while avoiding diagnostic or universal assumptions.
- [ ] Bound plan complexity and reminder volume, keep missed-work replanning nonjudgmental, and ensure rejected/candidate strategies are never silently treated as confirmed.

### Completion gate

- The assistant can clarify, estimate, decompose, schedule, explain, preview, and safely apply a multi-task deadline plan.
- Plans satisfy every hard validator and do not rely on unverified model arithmetic.

## Phase 8 — Experience and lesson workflow

- [ ] Collect detected experiences and candidate lessons during an interaction and present one approval batch at interaction end or explicit daily review, without storing raw conversation by default.
- [ ] Implement candidate lesson derivation with separate factual experience and interpretive lesson records.
- [ ] Implement an explicit many-to-many lesson/experience map with support, contradiction, and contextual relationships; require mapped evidence for candidates and supporting evidence for confirmation.
- [ ] Implement candidate, confirmed, superseded, and retired lesson lifecycle validation.
- [ ] Implement pull-based relevant/due lesson surfacing at CLI start, relevant turns, and explicit daily/weekly review commands with bounded reminder volume.
- [ ] Keep reminder surfacing read-only; stage confirmation, revisions, review outcomes, and reminder-policy changes for approval.
- [ ] Start retrieval with PostgreSQL full-text search, structured applicability, tags, planning references, and recency; defer embeddings until evaluation demonstrates a need.
- [ ] Add sensitivity-aware export and erasure across domain rows, staged payloads, controlled logs/indexes/exports, and future vectors, with disclosed backup-expiry semantics.
- [ ] Verify planning degrades explicitly but remains functional during a memory-database outage.

### Completion gate

- The assistant can automatically identify and batch experiences/candidate lessons, map them many-to-many, obtain one memory approval, surface confirmed lessons later, and preserve contradictory history.
- Planning and memory writes use separate tools, roles, proposals, migrations, and transactions.

## Phase 9 — Weather and requested research

- [x] Define a provider-neutral weather request/result interface with location resolution, timezone, forecast window, retrieval time, provenance, alerts, and uncertainty where available.
- [x] Implement one read-only provider using either a direct API or MCP adapter, with timeouts, size limits, schema validation, and normalized errors.
- [ ] Invoke weather only for location/date-sensitive activities and label forecast freshness and uncertainty.
- [ ] Allow weather to inform a proposed indoor alternative, time change, or recheck reminder, never a direct mutation.
- [x] Add tests using recorded/fake provider responses; keep automated tests independent of live network availability.
- [ ] Add provider-neutral requested news and paper research with provenance, direct citations, publication/retrieval dates, deduplication, freshness, and prompt-injection boundaries.
- [ ] Distinguish source claims from model inference and require planning or memory approval before researched information creates persisted state.

### Completion gate

- A weather-sensitive plan can receive a sourced, time-stamped recommendation and any schedule change still requires normal approval.
- Scheduling/domain code has no dependency on a specific weather provider or MCP transport.
- Requested research returns auditable sources without granting source content authority over tools or system instructions.

## Phase 10 — Evaluation gate and optional retrieval upgrades

- [ ] Evaluate estimate accuracy against append-only observed work logs and calibrate future estimates.
- [ ] Measure plan acceptance, missed/replanned sessions, validation failures, reminder usefulness/fatigue, lesson confirmation/contradiction, retrieval relevance, and model/tool failures.
- [ ] Evaluate deadline placement, buffers, ADHD-related usability, cognitive load, and nonjudgmental recovery using representative fixtures and real harness use.
- [ ] Define explicit go/no-go criteria for schema adaptation; unresolved correctness, privacy, or usability failures block production work.
- [ ] Reassess whether vector retrieval is justified by measured PostgreSQL retrieval gaps before adding ChromaDB.

### Completion gate

- Planning and memory behavior meet documented acceptance thresholds, privacy/erasure tests pass, and schema lessons are recorded before any production adaptation begins.

## Phase 11 — Calendar and route integrations

- [ ] Add Google Calendar import/reconciliation as external fixed blocks.
- [ ] Add approval-gated Google Calendar booking with idempotency, conflict rechecks, and external-write recovery.
- [ ] Add provider-neutral route/travel-time planning with origin/destination privacy controls, departure-time context, uncertainty, and stale-data handling.
- [ ] Revalidate schedule feasibility when calendar or travel context changes; never silently move approved work.

## Phase 12 — Production application evolution

- [ ] Adapt validated domain contracts to a Spring backend and React frontend through explicit APIs rather than exposing harness databases directly.
- [ ] Design multi-user ownership, authentication, authorization, encryption, retention, export/deletion, and tenant isolation before production data migration.
- [ ] Define explicit migration/reconciliation from experimental schemas and preserve rollback to the harness during validation.

## Phase 13 — Separately authorized operational control

- [ ] Complete and approve a dedicated threat model before granting any infrastructure mutation capability.
- [ ] Deploy to AWS/Kubernetes with read-only health and diagnostic tools first.
- [ ] Run operational control as a separate process/service with out-of-band authorization, isolated credentials, immutable audit, and no planning/memory access.
- [ ] Use static action schemas, signed artifact/commit selection, ephemeral sandboxes, redaction, timeouts, and complete audit trails; model-authored arbitrary shell remains prohibited.
- [ ] Require exact preview and authorization before Git/MCP mutations, configuration changes, rollouts, or rollbacks.
- [ ] Add idempotency, preflight checks, progressive rollout, post-deploy health verification, and tested rollback.
- [ ] Keep infrastructure tools isolated from planning/memory database credentials and ordinary conversational tool selection.

## Cross-cutting concerns to preserve

- **Security:** Treat model and external-tool output as untrusted data. Keep secrets out of prompts/logs and grant every tool the minimum capability required.
- **Privacy:** Define what conversation and external context are persisted; support redaction and eventual data export/deletion before production adaptation.
- **Observability:** Use structured logs and correlation IDs for a user turn, model/tool calls, proposal, validation, and transaction without storing hidden reasoning or secrets.
- **Reliability:** Use timeouts, bounded retries for safe read operations, idempotency for external writes, and clear recovery from partial external failures.
- **Explainability:** Preserve user-visible assumptions, estimates, validation reasons, and proposal diffs so a plan can be audited without model internals.
- **Evaluation:** Instrument from the foundation onward and require satisfactory planning/memory evaluation before production adaptation or retrieval expansion.
- **Schema evolution:** Record migration and modeling lessons. Do not expose either experimental database directly as a production backend schema.
- **ADHD safety:** Personalize from observed patterns, reduce shame and cognitive burden, preserve user choice, and avoid diagnosis or medical claims.
- **Operational safety:** Keep infrastructure access unauthorized until a separately approved threat model and control system provide out-of-band authorization, least privilege, isolation, audit, and rollback.

## Definition of core MVP complete

The core local Personal OS MVP comprises Phases 1–8. It is complete when a clean local environment can run both PostgreSQL databases and the CLI; a user can describe a realistic goal; the Ollama agent can clarify, estimate, decompose, and propose a personalized backward deadline plan using deterministic calculations; the validator can prove or reject feasibility; the agent can propose and later resurface evidence-backed experiences and lessons; and no semantic database change occurs without preview, proposal-ID approval, revalidation, and atomic apply in its target database.

Weather and requested research are the next local milestone. Formal evaluation then gates Calendar/routes and Spring/React adaptation. AWS/Kubernetes diagnostics and any Git/MCP deployment controls belong to a separately authorized operational system; arbitrary model-authored shell execution is not planned.
