# Personal OS Harness: MVP Architecture

## 1. Architectural boundary

The harness is a local Python application with a command-line interface, an Ollama agent, a controlled tool layer, deterministic validation, and two PostgreSQL databases. The planning database owns tasks and time. The memory database owns experiences and lessons.

```text
User
  │
  ▼
Interactive CLI ─────────────── explicit inspect/approve commands
  │
  ▼
Conversation orchestrator
  ├── Ollama model (judgment and proposals)
  ├── Calculation/external-context read tools
  ├── planning.* tools ───── validator/proposals ─── Planning DB
  └── memory.* tools ─────── validator/proposals ─── Memory DB
                                  ▲
                                  └── explicit approval before apply
```

The model never receives unrestricted SQL access. Every database capability is exposed as a narrow, typed tool in either a `planning.*` or `memory.*` namespace. Read tools can execute immediately. Write tools create proposal operations rather than mutating domain tables.

Both databases may run in one PostgreSQL cluster locally, but they have separate database names, connection settings, roles, migrations, repositories, and proposal ledgers. No runtime application role can write to both. A short-lived bootstrap administrator creates separate owner, migrator, and least-privilege runtime roles. PostgreSQL has no ordinary cross-database foreign keys or transactions: each proposal targets exactly one database, and neither database coordinates its commit with the other. Optional references are opaque provenance values with immutable display labels, not relational dependencies.

This architecture deliberately separates the model's plan from the validator's verdict. Validation reports failures; it does not silently rearrange the schedule. The model may use those failures to propose a revised plan in another tool round.

## 2. Candidate modules

The implementation should evolve toward these responsibilities without treating the initial package names as permanent public APIs:

- **CLI:** interactive loop, explicit commands, rendering, proposal selection, and approval input.
- **Agent orchestration:** system instructions, conversation history, Ollama requests, tool schemas, tool execution, maximum tool rounds, and error recovery.
- **Application services:** task, calendar, planning-context, experience, lesson, reminder, proposal, and scheduling use cases.
- **Domain validation:** pure or database-assisted checks for graph, effort, time, and task-state invariants.
- **Repositories/unit of work:** typed persistence operations and transaction management using Psycopg.
- **Migrations/configuration:** schema evolution, connection settings, timezone/default-capacity settings, and local Docker Compose.

The core domain and validator must not depend on Ollama response shapes. This keeps future model providers and the production backend from inheriting model-client concerns.

## 3. Experimental planning PostgreSQL schema

The tables below are a candidate starting point. Names and fields may change after exercising real plans. All identifiers use UUIDs, all mutable rows include `created_at` and `updated_at`, and timestamp fields are timezone-aware.

### `tasks`

Stores goals, intermediate groups, and executable leaves.

| Field | Purpose |
| --- | --- |
| `id` | Stable UUID primary key. |
| `parent_id` | Nullable self-reference defining the hierarchy tree. |
| `title`, `description` | Human-visible task definition. |
| `status` | Draft, ready, in-progress, blocked, completed, or cancelled. |
| `priority` | Integer 1–5, where 1 is highest; explicit user priority outranks model suggestion. |
| `estimate_minutes` | Nullable only for draft tasks; otherwise a positive 15-minute multiple. |
| `category` | Optional normalized category identifier. |
| `earliest_start`, `deadline_at` | Optional UTC hard bounds with retained planning timezone. |
| `deadline_precision` | Exact instant or local date; date values normalize to exclusive next-day midnight. |
| `splittable` | Defaults true; false requires one contiguous session. |
| `min_session_minutes`, `max_session_minutes` | Optional session constraints in 15-minute units. |
| `constraints` | Versioned JSON for uncommon structured task rules during schema experimentation. |
| `notes` | Free-text context for model judgment. |

Hierarchy-cycle validation is required in application code and should also use database constraints where practical. A leaf is derived by the absence of children rather than stored as a flag. Every non-leaf estimate equals the sum of its direct child estimates before the branch leaves draft. Parent status and actual effort are derived rather than independently edited. Typed task columns are authoritative; `constraints` cannot override them, hard `planning_contexts` add compatible rules, and conflicting hard rules fail validation. Soft context never overrides a hard field.

### `tags`, `task_tags`, and `work_logs`

Normalized tags support task and memory retrieval without hiding identity inside JSON. `task_tags` links them to tasks.

`work_logs` are append-only observed-effort records with task ID, optional session ID, actual start/end or observed minutes, source (`manual`, `timer`, or `import`), occurrence time, notes, and optional superseded/reversal reference. Task and parent actual effort is derived from active work logs; completed planned sessions are not fabricated into actual effort.

### `task_dependencies`

Stores finish-to-start prerequisite edges.

| Field | Purpose |
| --- | --- |
| `prerequisite_task_id` | Task that must complete first. |
| `dependent_task_id` | Task that is blocked by the prerequisite. |
| `created_at` | Audit timestamp. |

The pair is the primary key. A check constraint prevents direct self-dependency. Transaction validation prohibits ancestor/descendant edges, expands parent endpoints to descendant leaves, and validates the effective leaf graph for indirect cycles and expansion-created self-edges. No relationship is inferred from insertion order.

### `availability_windows`

Defines recurring local-time windows where flexible work is allowed.

| Field | Purpose |
| --- | --- |
| `id` | UUID primary key. |
| `weekday` | Local weekday. |
| `start_local_time`, `end_local_time` | Clock bounds for the window. |
| `effective_from`, `effective_until` | Optional local-date range. |
| `label`, `enabled` | User-facing purpose and activation state. |

Windows use the single configured planning timezone in the MVP and may overlap; free-time calculation uses their union. Input spanning midnight is split into two stored rules. All materialized intervals are half-open `[start,end)`; nonexistent DST wall times are rejected and ambiguous times require an explicit offset choice.

### `calendar_blocks`

Represents time unavailable to flexible task scheduling.

| Field | Purpose |
| --- | --- |
| `id` | UUID primary key. |
| `title`, `category`, `notes` | Meaning such as sleep, rest, school, work, holiday, or appointment. |
| `load_class` | Personal, non-personal, or neutral for daily-profile accounting. |
| `start_at`, `end_at` | One-off timezone-aware interval. |
| `all_day_date` | Alternative for an all-day local-date block. |

Exactly one temporal form—half-open interval or all-day local date—is required. Weekly repetition is normalized into a separate `recurring_block_rules` table with typed weekday, local start/end, effective-from/until, enabled state, load class, and the single planning timezone. Overnight input is split at ingestion.

### `scheduled_sessions`

Stores model-proposed, approved allocations for leaf tasks.

| Field | Purpose |
| --- | --- |
| `id` | UUID primary key. |
| `task_id` | Leaf task receiving the work session. |
| `start_at`, `end_at` | Timezone-aware interval on the 15-minute grid. |
| `status` | Planned, in-progress, completed, skipped, or cancelled. |
| `notes` | Session-specific instructions or explanation. |
| `proposal_id` | Mutation proposal that created or last materially changed it. |

PostgreSQL range/exclusion constraints should prevent overlapping active flexible sessions. Availability, blocks, leaf-only references, effort totals, dependency ordering, and deadline checks remain application-level transaction validation.

Only planned and in-progress sessions are active for future overlap/capacity checks. Completed, skipped, and cancelled sessions remain historical. Planned-effort reporting includes planned and in-progress allocations; actual effort always comes from `work_logs`. A dependent session may be planned after a prerequisite's projected end, but execution cannot begin until prerequisite leaves are actually completed.

### `planning_contexts`

Stores reusable specialized conditions.

| Field | Purpose |
| --- | --- |
| `id` | UUID primary key. |
| `scope_type`, `scope_id` | Global, task, or category scope and its optional target. |
| `kind` | Preference or hard constraint. |
| `structured_value` | Versioned JSON for enforceable or machine-readable values. |
| `notes` | Natural-language guidance for the model. |
| `effective_from`, `effective_until` | Optional date/time applicability. |
| `enabled` | Activation state. |

Common constraints should migrate from JSON to typed columns once harness usage proves their shape stable.

### `settings`

Stores single-user harness policy such as planning timezone, 15-minute resolution, fallback personal reserve, daily-profile completeness, proposal expiration, and reminder display limit. Configuration defaults to `Europe/Istanbul`, 15 minutes, and a 720-minute fallback reserve. When a daily/recurring personal profile is confirmed complete, the union of its explicit personal intervals replaces the fallback for affected dates. Environment variables remain the source for secrets and deployment-specific connection/model settings.

### `mutation_proposals` and `mutation_operations`

Provide the approval boundary and a minimal audit trail.

`mutation_proposals` stores the proposal ID, immutable revision, canonical preview hash, redacted source summary or turn ID, assumptions, status, validation result, creation/expiration time, sensitivity, previewed state versions, optional conversation correlation metadata, and applied result. Correlation metadata is observational only and creates no cross-database ordering or transaction behavior. Status transitions are `pending → applied`, `pending → rejected`, `pending → superseded`, or `pending → expired`. Approval locks and revalidates the pending revision, applies domain changes, and marks it applied in one transaction; failures are separate attempt records and never leave an ambiguous durable `approved` state. Repeated approval of an applied revision returns the existing result.

`mutation_operations` stores ordered typed operations with target type/ID, redacted field-level before/proposed values, and a schema version. Operations are data interpreted by an allow-listed application layer, never SQL fragments supplied by the model. Pending sensitive payloads have a short TTL; rejection/expiration purges proposed values while retaining minimal audit metadata.

Proposal control-plane records may be persisted before approval, but no semantic domain operation is applied beforehand. Secrets, raw memory source conversations, and complete hidden model reasoning are never stored.

## 4. Experimental experience/lesson PostgreSQL schema

The memory database is independent of planning storage. Its initial candidate tables are described in `experience-lessons.md`: `experiences`, `lessons`, `lesson_evidence`, `lesson_reviews`, `experience_planning_references`, plus memory-specific mutation proposals and operations. Optional planning references contain opaque UUIDs and immutable source labels, never cross-database foreign keys; missing sources render as tombstones.

Memory migrations and encrypted backups are separate because personal reflections have different retention, export, deletion, and sensitivity requirements. An erasure workflow removes active rows, proposal payload copies, controlled logs/indexes/exports, and future vectors; backups expire under a disclosed retention schedule rather than promising immediate physical erasure. Planning should continue operating when memory storage is unavailable; it reports degraded personalization rather than copying memory into the planning database.

## 5. Tool and orchestration contract

### Read tools

Initial read capabilities should cover:

- task lookup/listing with descendants and ancestors;
- dependency neighborhood or graph inspection;
- schedules and free/busy intervals for a date range;
- availability, blocks, settings, and applicable planning contexts; and
- proposal validation/status inspection.

Memory read capabilities separately cover experience search, lesson search, relevant confirmed lessons, due reviews, lesson evidence, and memory proposal status. Planning tools cannot query memory tables directly; the orchestrator calls the memory tools and deliberately supplies bounded results to planning.

Results use bounded, structured JSON and stable identifiers. The orchestrator should summarize or paginate large results rather than passing an unbounded database dump to the model. Computed free/busy reads are limited to 31 days, merge half-open availability and busy intervals, subtract scheduled work and blocks, and reject ambiguous or nonexistent recurring local times.

### Calculation and external-context tools

Core calculation tools use typed inputs and allow-listed operations for numeric arithmetic, duration aggregation, unit conversion, date/time differences, timezone conversion, capacity totals, and 15-minute rounding. They never pass model-provided text to Python evaluation, a shell, SQL, or another general-purpose interpreter. Validator calculations remain independently implemented against authoritative domain values.

Post-core weather access uses an application-level interface such as `get_weather(location, date_range)`. Adapter results normalize the provider, resolved coordinates/timezone, requested interval, retrieval time, forecast values, alerts, and provider-supplied uncertainty when available. Direct HTTP API and MCP adapters implement the same interface; neither is referenced by task or scheduling repositories.

External context is untrusted, read-only model input. Responses require size limits, timeouts, schema validation, provenance, freshness metadata, and clear separation from system instructions. Weather calls are made only for weather-sensitive plans and should be refreshed near the event. They may inform a newly staged proposal but never directly write domain or calendar state.

### Write tools

The model may propose typed operations such as creating/updating tasks, replacing a task's prerequisites, adding/removing blocks, changing availability, and replacing scheduled sessions for a defined scope. Every call returns a proposal or adds operations to the current proposal; it never reports a domain write as complete.

Tools validate their input schema before accessing persistence. The application validates combined proposal semantics after all operations are composed. Broad replacement operations must state their exact scope so previews can show removals as well as additions.

Planning write tools and memory write tools have distinct schemas, registries, connection pools, and permission scopes. A tool declaration identifies its target database, and the orchestrator rejects mixed-database operation lists. Each database may have one pending proposal. The CLI qualifies proposal commands by database, and approval or failure in one database has no transactional effect on the other.

### Ollama loop

For each user turn, the orchestrator:

1. appends the user message to conversation history;
2. sends system instructions, history, and tool definitions to Ollama;
3. persists the returned assistant message in history;
4. executes requested read/staging tools and appends each tool result;
5. repeats until the model returns a final response or reaches the configured tool-round limit; and
6. surfaces timeouts, invalid tool arguments, model errors, and round exhaustion without losing pending proposal state.

Configuration values must be parsed to their real types: timeouts and tool-round limits are positive integers, URLs/models are non-empty strings, and secrets are not logged. The provider client lives under an application namespace that does not shadow the official `ollama` SDK, deliberately uses either direct HTTP or the SDK, capability-checks the configured model, retains assistant tool-call messages, appends role-`tool` results, and returns stable application-level types rather than raw provider dictionaries.

## 6. Validation and transaction design

Validation runs against the effective state produced by overlaying a proposal on a consistent database snapshot. It returns a collection of issues containing a stable code, severity, message, affected entity IDs, and optional details useful for repair.

Validation groups:

- **Graph:** hierarchy plus expanded effective-leaf dependency cycles, self/duplicate edges, ancestor/descendant edges, and missing references.
- **Effort:** positive 15-minute units, parent/child budget reconciliation, and scheduled-vs-estimated totals.
- **Intervals:** valid ranges, grid alignment, recurrence expansion, unioned availability, blocks, overlap, and the daily capacity ceiling.
- **Ordering:** prerequisite completion, earliest starts, deadlines, and parent-derived completion.
- **Task state:** leaf-only scheduling and consistent completed/cancelled/session states.

The single-user MVP uses optimistic row versions and full revalidation immediately before apply in the target transaction; PostgreSQL constraints remain defense in depth. This is sufficient while the harness is the only writer. Before a Spring backend or any concurrent writer is enabled, add aggregate/range version guards or serializable transactions and integration tests for phantom insertions. Drift or validation failure rolls back all domain changes and requires a new preview.

Memory validation additionally checks evidence references, allowed lesson lifecycle transitions, confidence bounds, reminder/review dates, and preservation of contradictory evidence.

There is no distributed transaction or domain-level commit dependency across the two databases. A planning proposal and memory proposal may both arise from one conversation, but each is previewed, approved, applied, rejected, retried, and reported independently.

## 7. CLI contract

The exact command framework can be selected during implementation, but the behavior should include these stable concepts:

- entering text without a command sends a planning chat turn;
- `tasks`/`task` inspect current work;
- `schedule` inspects a date range or task allocation;
- `availability` and `blocks` inspect time constraints;
- `experiences`, `lessons`, and `reviews` inspect the memory database;
- `validate` checks current state or the pending proposal;
- `proposals` lists pending planning and memory proposals independently;
- `proposal <database>` shows that database's preview, revision, and preview hash;
- `approve <database> <proposal-id> <revision>` and `reject <database> <proposal-id> <revision>` explicitly resolve it; and
- `config` displays non-secret effective configuration.

Approval commands require the displayed proposal identifier and revision and verify the canonical preview hash internally. EOF or interruption exits safely without applying a proposal.

## 8. Packaging and local infrastructure

Before feature implementation:

- move runtime and development dependencies into `pyproject.toml` and regenerate `uv.lock` as the single dependency source;
- omit ChromaDB and `datasets` until a demonstrated MVP use exists;
- add a real `.gitignore` covering `.env`, virtual environments, caches, and generated artifacts;
- provide a non-secret `.env.example` and load deployment configuration from environment variables;
- add Docker Compose for a pinned PostgreSQL image with a short-lived bootstrap role, separate planning/memory owner, migrator, and runtime roles, initialization SQL for both databases, health checks, and a persistent named volume;
- add separate sequential plain SQL streams for both databases, reviewed and applied manually with `psql`; the harness does not depend on a migration framework; and
- establish unit, integration, and CLI test directories.

Tests that depend on PostgreSQL should use isolated test databases and real PostgreSQL features rather than SQLite, because exclusion constraints, timestamp behavior, and dual-database independence are part of what the harness is evaluating. Phase 1 includes real smoke tests rather than an empty suite; later tests cover property-based graph/interval cases, proposal replay/crash recovery, independent database failure, fake Ollama tool transcripts, and DST behavior in a currently transitioning zone. Phantom/concurrent-writer tests become mandatory before production backend access.

## 9. Evolution boundary

Weather, research, and Google Calendar integrations should enter through separate provider-neutral adapter/tool interfaces. Implement the first weather adapter only after core planning is working, while allowing either direct APIs or MCP servers behind the same contract. Calendar import should first create or reconcile external blocks; booking should remain an approval-gated write with an external idempotency key. None of these integrations should be coupled to task persistence.

Before adapting the harness schemas to the production backend, review real usage for hierarchy semantics, recurrence queries, lesson/evidence quality, sensitive-memory handling, JSON constraint patterns, proposal audit needs, scheduling performance, and multi-user ownership. Production adoption should use explicit schema/design migrations, not point a multi-user service directly at the experimental harness databases.

The future Spring/React/AWS application is a separate production phase gated by harness evaluation. Operational control is a separate system and remains unauthorized until it has its own threat model, process boundary, out-of-band authorization, least-privilege identities, immutable audit, signed artifact/commit selection, static action schemas, ephemeral sandboxing, health verification, and tested rollback. Model-authored arbitrary shell remains prohibited even with conversational approval. Planning and memory services never inherit infrastructure privileges.
