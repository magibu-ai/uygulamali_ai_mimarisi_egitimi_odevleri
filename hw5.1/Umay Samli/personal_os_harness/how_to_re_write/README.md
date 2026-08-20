# How I Would Rewrite the Whole Stack

This is a proposed production rewrite path for the Personal OS. It is not the
current implementation plan for the Python harness. The harness should remain a
small laboratory and executable specification while the validated behavior is
moved into the future backend and frontend.

The safest rewrite is incremental. Replacing the database, domain rules, agent,
and user interface at the same time would make it difficult to tell whether a
behavior change is intentional or a regression.

This document covers the production Spring Boot/React destination. See
[Rewriting the Python harness](HARNESS.md) for a clean implementation plan that
keeps the project as a local Python experiment.

## Recommended destination

The final shape should be a modular Spring Boot backend, a React/TypeScript
frontend, two isolated PostgreSQL databases, and a direct-HTTP Ollama adapter.

```text
React web application
        |
        | versioned HTTP/JSON
        v
Spring Boot modular monolith
  |-- conversation and agent module
  |-- planning module
  |-- memory module
  |-- proposal and approval modules per database
  |-- provider-neutral external-context interfaces
        |
        +---- planning datasource/transaction manager ---> planning PostgreSQL
        |
        +---- memory datasource/transaction manager -----> memory PostgreSQL
        |
        +---- direct HTTP -------------------------------> Ollama
        |
        +---- bounded provider adapters ----------------> weather/public web
```

A modular monolith is preferable at this stage. The planning and memory modules
need strong internal structure and independent transactions, but they do not yet
need the operational cost of separately deployed microservices. Their isolation
must still be real: separate URLs, runtime roles, Flyway histories, repositories,
and transaction managers.

## Preserve these decisions

These are product safety properties, not Python implementation details:

- Planning and memory remain separate databases. Cross-database references are
  opaque identifiers with display labels, never foreign keys.
- Every semantic write is staged, validated, previewed, explicitly approved,
  revalidated, and atomically applied in one target database.
- Approval binds a proposal ID, immutable revision, and canonical preview hash.
- The model receives narrow typed tools, never SQL, shell, filesystem, or general
  network access.
- Deterministic code owns graph, effort, interval, lifecycle, and proposal
  validation. The model owns contextual judgment and suggestions.
- Time values remain timezone-aware and intervals remain half-open
  `[start_at, end_at)`.
- Tasks, dependencies, lessons, evidence, and proposal audit history retain
  stable UUIDs during migration.
- Experiences remain factual records. Lessons remain reviewable interpretations
  with supporting, contradicting, and contextual evidence.
- Confirmed lessons may inform planning but cannot override hard constraints.
- Ollama remains behind a provider seam and is called through direct HTTP.

## Change these parts

| Current harness | Production rewrite |
| --- | --- |
| Python package as the application | Spring Boot modular monolith as the authoritative application |
| Plain SQL initialized manually | Two Flyway streams owned by the Spring backend |
| Psycopg read repositories | Spring `JdbcClient` or jOOQ adapters with explicit SQL |
| Python records and protocols | Immutable Java records and small module interfaces |
| Typer inspection CLI | React user experience plus a thin development/admin CLI if still useful |
| Python Ollama loop | Spring agent module after transcript parity is proven |
| Handwritten JSON Schema dictionaries | Versioned tool DTOs with generated JSON Schema and contract tests |
| Unit fakes plus opt-in PostgreSQL tests | Unit tests, Testcontainers PostgreSQL, contract tests, and end-to-end tests |
| Local environment files | Typed Spring configuration, secret injection, and environment-specific deployment config |

Prefer explicit SQL through Spring `JdbcClient` initially. The schema uses
recursive CTEs, JSONB, full-text search, exclusion constraints, and PostgreSQL
range semantics; forcing those through a large ORM abstraction would hide useful
database behavior. jOOQ is a good later option if generated types justify the
additional build and licensing decisions.

## Rewrite order

Each phase has an exit gate. Do not start depending on the new implementation
until its gate passes.

### 0. Freeze and measure the current behavior

Before writing the replacement:

1. Make the Python quality suite green.
2. Capture representative fake-Ollama transcripts for every tool and failure
   path.
3. Add golden fixtures for task trees, dependencies, free/busy calculations,
   daylight-saving gaps and folds, lesson evidence, and proposal previews.
4. Export schema definitions and a sanitized sample data set.
5. Record known model failures separately from deterministic code failures.

Exit gate: the same input always produces a comparable typed result or a known,
documented model variance.

### 1. Define versioned contracts

Create contracts before copying implementations:

1. Define HTTP resources and error envelopes in OpenAPI.
2. Define tool names, descriptions, argument DTOs, result DTOs, bounds, and
   versioning rules.
3. Define stable validation issue codes and proposal lifecycle states.
4. Define canonical JSON serialization and preview hashing.
5. Generate a TypeScript client for the frontend and validate Java DTOs against
   the same examples.

The contract must not expose Ollama payloads, database rows, or framework
exceptions. Tool results must continue to identify whether their source is the
planning or memory database.

Exit gate: Python fixtures validate against the contracts and Java contract tests
consume the same examples.

### 2. Establish the Spring backend skeleton

Create one Spring Boot repository with modules such as:

```text
backend/
  application/
  agent/
  planning-domain/
  planning-persistence/
  memory-domain/
  memory-persistence/
  proposals/
  web/
  providers/ollama-http/
```

Use dependency injection at module seams. Domain modules must not import web,
Ollama, or persistence implementations. Avoid creating one interface for every
class; introduce a seam when there are real adapters or when it protects a
domain/provider boundary.

Exit gate: the application starts, configuration validation fails clearly, and
architecture tests enforce allowed module dependencies.

### 3. Move database ownership to Flyway

Flyway belongs in the future backend, not in this harness.

1. Configure two datasources.
2. Configure two Flyway instances with different locations and history tables.
3. Give each migrator role DDL rights only in its database.
4. Give each runtime role only the DML it needs in its database.
5. Create a reproducible fresh-database baseline for planning and another for
   memory.
6. For an existing database, compare its schema to the baseline, back it up, and
   then baseline Flyway at the matching version. Never pretend an unknown schema
   is compatible.
7. Use Testcontainers to apply every migration from empty state.

Do not share a transaction manager, entity manager, repository, or migration
location between planning and memory.

Exit gate: both databases build from empty independently, runtime roles cannot
perform DDL, and either database may be unavailable without corrupting the other.

### 4. Rewrite deterministic domain behavior

Port rules before endpoints:

1. Timezone parsing, half-open intervals, DST gap/fold rejection, interval union,
   and subtraction.
2. Task hierarchy traversal and cycle detection.
3. Descendant-expanded dependency validation.
4. Parent/child effort budgets and append-only actual effort.
5. Availability, blocks, capacity, and free/busy calculation.
6. Lesson evidence and lifecycle validation.
7. Proposal state machine, canonical preview, drift detection, idempotency, and
   sensitive payload cleanup.

Use immutable Java records for values and return all validation issues together.
Do not silently repair a failed model proposal.

Exit gate: Java tests pass the Python golden fixtures, including DST cases in a
timezone that actually changes offset.

### 5. Rewrite persistence adapters

Implement bounded repository operations behind the domain module interfaces:

1. Planning settings and bounded task reads.
2. Task trees, ancestors, and dependency reads.
3. Availability, blocks, sessions, and planning contexts.
4. Experience and lesson search, evidence, and reviews.
5. Proposal creation, approval, rejection, expiry, and apply-attempt audit.
6. Atomic application of one proposal in one target database.

Keep PostgreSQL-specific SQL in persistence modules. Preserve explicit limits,
deterministic ordering, full-text-search configuration, and half-open overlap
predicates.

Exit gate: repository tests run against real PostgreSQL containers and exercise
constraints, transaction rollback, role separation, and one-database outage.

### 6. Expose read and proposal HTTP interfaces

Add the backend interface in safety order:

1. Health and non-secret configuration.
2. Read-only planning endpoints.
3. Read-only memory endpoints with privacy-aware result limits.
4. Proposal staging and exact preview retrieval.
5. Approval/rejection with revision and hash preconditions.
6. Revalidation and atomic apply.

Use idempotency keys for externally retried operations. Do not expose a generic
mutation endpoint.

Exit gate: end-to-end tests prove that an unapproved, stale, changed, expired, or
replayed proposal changes no semantic state.

### 7. Rewrite the agent module

Only replace the Python agent after the backend module interfaces are stable:

1. Implement the direct Ollama `/api/show` capability check.
2. Implement complete assistant/tool-message history.
3. Generate tool declarations from versioned DTOs.
4. Preserve strict argument parsing and bounded result sizes.
5. Preserve the maximum tool-round limit.
6. Return expected tool and dependency errors to the model as typed results.
7. Add staged-write tools; never give the model direct repository access.
8. Verify final answers against authoritative tool results for critical facts
   such as timezones, durations, IDs, and proposal state.

The last point is a deliberate improvement. A model can call the correct tool and
still paraphrase its result incorrectly. Critical output should be checked or
rendered from structured facts rather than trusted merely because tool calling
succeeded.

Exit gate: the Spring loop passes the saved Python transcripts and live Ollama
smoke tests, including refusal to claim unapproved writes.

### 8. Build the React interface

Build the interface around the proposal workflow:

1. Goal and planning conversation.
2. Read-only task tree, schedule, and free/busy views.
3. Proposal preview that clearly shows assumptions, warnings, and exact changes.
4. Explicit approve, reject, and revise actions.
5. Separate experience and lesson review screens.
6. Accessible loading, outage, stale-proposal, and validation-error states.

Use the generated TypeScript client rather than duplicating DTOs manually. The
browser never calls Ollama or PostgreSQL directly.

Exit gate: a user can inspect state, discuss a change, preview it, approve it, and
see the committed result in an end-to-end test.

### 9. Add external context behind adapters

Add weather, requested research, calendars, and routes one provider at a time.
Treat their content as untrusted, bounded, provenance-labelled input. External
data may inform a proposal but may not mutate planning or memory directly.

Carry forward the harness contracts for `time.get_current_date`,
`web.scrape_page`, and `weather.get_for_date` as versioned DTOs; provider names
must not leak into scheduling/domain code. The Spring web adapter must enforce
SSRF protections at the outbound network boundary (public address policy,
redirect revalidation, standard ports, content-type allow-list, response-size
and text-size caps, and timeouts). Weather must preserve the resolved location
and timezone, requested date/window, retrieval time, provenance, uncertainty,
alert availability, and explicit out-of-horizon results.

The React conversation view should show validated tool names and arguments in a
collapsible activity trace before the final answer. Do not expose raw tool
results by default because planning, memory, and location results may be
sensitive.

Exit gate: each adapter has contract tests, timeouts, bounded responses, and a
clear unavailable state.

### 10. Migrate data and cut over

1. Stop semantic writes to the old implementation.
2. Back up both databases independently.
3. Restore backups into a staging rehearsal.
4. Run schema and data transformations with Flyway or a one-time, reviewed
   migration tool.
5. Verify row counts, UUID preservation, foreign keys, proposal hashes, time
   zones, and representative domain queries.
6. Run read parity and end-to-end acceptance tests.
7. Cut over one environment at a time.
8. Retain a tested rollback window and the original backups.

Avoid long-lived dual writes. Coordinating two implementations and two isolated
databases would create more failure modes than it removes.

Exit gate: production traffic uses the new backend, verification is clean, and
rollback has been rehearsed.

## Suggested first pull requests

1. Contract fixtures and golden behavior suite.
2. Spring multi-module skeleton and architecture tests.
3. Dual datasource and dual Flyway Testcontainers setup.
4. Planning baseline migration and least-privilege roles.
5. Memory baseline migration and least-privilege roles.
6. Time/free-busy domain port with parity tests.
7. Task graph and effort domain port with parity tests.
8. Lesson/evidence domain port with parity tests.
9. Proposal state machine and canonical preview hashing.
10. Bounded read repositories and HTTP endpoints.
11. Staged-write repositories and approval endpoints.
12. Direct-HTTP Ollama adapter and read-only tool loop.
13. Staged-write tools and output verification.
14. React inspection and proposal-preview interface.

Small pull requests make parity failures attributable. Database migrations should
not be mixed with unrelated user-interface changes.

## Testing and release gates

The replacement is ready only when it has:

- Unit tests for every deterministic invariant.
- PostgreSQL Testcontainers tests for migrations, repositories, roles, exclusion
  constraints, and rollback.
- Contract tests shared by Java, TypeScript, and retained Python fixtures.
- Fake-Ollama transcript tests that require no network or local model.
- Live Ollama smoke tests outside the routine suite.
- End-to-end proposal tests covering stale, replayed, expired, rejected, failed,
  and successful proposals.
- Privacy tests for bounded memory retrieval, sensitive proposal cleanup, export,
  correction, retirement, and erasure.
- Observability that excludes secrets, raw conversations, and sensitive memory
  payloads.
- Backups, restore tests, and a documented rollback procedure.

## Decisions that can wait

These do not block the first rewrite phases:

- Whether the optional admin CLI remains Java, Python, or shell-free HTTP tooling.
- Whether `JdbcClient` should later be replaced by jOOQ.
- Which React state/query libraries to use.
- Whether weather, research, calendar, or route providers need their own deployed
  processes.
- Whether Kubernetes or a public cloud is needed.

Authentication and multi-user tenancy can wait only while the system remains
strictly local and single-user. They must be designed before exposing the backend
to an untrusted network.

## Things I would not do

- I would not merge planning and memory into one database for convenience.
- I would not let the agent issue SQL or call repository methods directly.
- I would not introduce distributed transactions across the two databases.
- I would not use Flyway inside the Python harness.
- I would not rewrite the agent before deterministic domain parity exists.
- I would not assume a successful tool call guarantees a factually correct final
  model answer.
- I would not add embeddings, microservices, Kubernetes, or a message broker
  before measured requirements justify them.
- I would not delete the harness until the replacement passes contract, data, and
  transcript parity checks.
