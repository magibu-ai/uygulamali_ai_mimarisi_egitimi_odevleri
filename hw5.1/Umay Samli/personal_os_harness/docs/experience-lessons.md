# Experience and Lesson System

## Purpose

The memory system turns personal experience into reusable, reviewable guidance. It records what happened separately from what the model concludes, preserves contradictory evidence, and resurfaces confirmed lessons when they can improve a decision or are due for review.

It uses a PostgreSQL database distinct from the planning database and a separate `memory.*` tool namespace. This separation limits coupling and allows stricter privacy, retention, export, and deletion policies for personal reflections.

## Core behavior

The assistant may detect a noteworthy experience after a completed, skipped, delayed, or reviewed task, or directly from conversation. It may also infer one or more candidate lessons. Detection does not alter memory domain records automatically. Findings accumulate during the interaction and are presented as one reviewable memory batch at interaction end or during an explicit daily review. The CLI discloses when this staged content is temporarily stored before approval.

An experience is evidence, not a conclusion. It records the event, observation, context, outcome, source, and the user's own reflection when available. The assistant should preserve uncertainty and must not rewrite the event to fit an existing lesson.

A lesson is a reusable interpretation. It records a concise statement, rationale, applicability, confidence, lifecycle state, and review policy. Candidate lessons cannot be presented as established personal facts. Every candidate lesson maps to at least one experience, confirmation requires supporting evidence, and later experiences may support, contradict, or contextualize it.

Confirmed lessons can be surfaced:

- when their applicability matches the current planning situation;
- before a task related to their evidence or tags;
- during daily or weekly review; or
- when their next review date arrives.

In the MVP, surfacing is pull-based at CLI startup, relevant planning turns, or explicit review commands; no background notification daemon is implied. Surfacing is read-only. The assistant should avoid reminder overload by ranking relevance, applying a configurable display limit, and allowing snooze/disable preferences. Any semantic change—confirmation, editing, retirement, review outcome, or reminder-policy change—uses an approved memory proposal.

## Candidate schema

### `experiences`

- `id`: UUID primary key.
- `occurred_precision`: date, instant, or bounded interval, with matching typed occurrence fields.
- `title`, `narrative`: concise label and factual description.
- `context`, `outcome`, `reflection`: structured JSON plus user/model-attributed prose.
- `statement_origin`: user observation, imported fact, or model summary; model inference is never presented as a direct user statement.
- `sensitivity`: standard, sensitive, or highly sensitive, used by display, export, retention, and future encryption policies.
- `tags`: searchable topics.
- timestamps and a version for optimistic concurrency.

The record distinguishes user statements from model inference. Raw conversation is not copied by default; the proposed summary must be reviewable.

### `lessons`

- `id`: UUID primary key.
- `statement`, `rationale`: reusable conclusion and explanation.
- `status`: candidate, confirmed, superseded, or retired.
- `confidence`: low, medium, or high with a required rationale rather than false numeric precision.
- `applicability`: structured conditions plus free-text scope.
- `review_policy`, `next_review_at`, `last_reviewed_at`: periodic resurfacing behavior.
- `superseded_by_id`: optional link within the memory database.
- `sensitivity`, `tags`, timestamps, and version.

### `lesson_evidence`

Implements a many-to-many mapping between lessons and experiences. One lesson can draw from many experiences, and one experience can inform many lessons. Each unique lesson/experience pair records a relationship of `supports`, `contradicts`, or `contextualizes`, a reviewable relevance explanation, provenance, and timestamps. Evidence summaries never replace the original experience. A candidate lesson must have evidence, and transition to confirmed requires at least one supporting link; contradictory links remain visible in confidence and review decisions.

### `lesson_reviews`

Records approved review outcomes: still useful, needs revision, contradicted, snoozed, or retired. It stores the review time, notes, and the next review date. A due reminder is computed from lesson state and does not itself require a write.

### `experience_planning_references`

Stores zero or more planning source references with `source_type`, opaque UUID, and a minimal immutable display label. Missing planning entities are shown as tombstoned references. Planning deletion never cascades into personal memory.

### Proposal tables

The memory database has its own `mutation_proposals` and `mutation_operations` tables with the same immutable revision, preview hash, revalidation, idempotent atomic-apply, and semantic approval rules as planning proposals. A memory operation cannot target planning data. Raw conversation is not stored as the source request; proposals use a turn ID and redacted summary. Pending sensitive payloads expire quickly, and rejection/expiration purges proposed values while retaining minimal redacted audit metadata.

## Tool contract

Initial read tools:

- `memory.search_experiences`
- `memory.get_experience`
- `memory.search_lessons`
- `memory.get_lesson_with_evidence`
- `memory.get_relevant_lessons`
- `memory.get_due_reviews`
- `memory.get_proposal`

Initial staged-write tools:

- `memory.propose_review_batch`
- `memory.propose_experience`
- `memory.propose_lesson`
- `memory.propose_evidence_link`
- `memory.propose_lesson_revision`
- `memory.propose_review_outcome`
- `memory.propose_retirement`

Tool results are bounded, typed, and labelled with provenance and sensitivity. The model has no SQL tool and cannot use planning tools to mutate memory or memory tools to mutate planning.

`memory.propose_review_batch` is the normal conversational write path. It atomically proposes experiences, candidate lessons, and all lesson-evidence links in one memory-database proposal. The smaller tools remain available for explicit edits and later evidence.

## Retrieval approach

Start with PostgreSQL full-text search, tags, applicability fields, task/source references, and recency. Do not add ChromaDB until evaluation proves semantic retrieval is necessary. If embeddings are later introduced, PostgreSQL remains authoritative and deletion/export must also remove derived vectors.

## Privacy and safety

- Store the minimum useful personal detail and never hidden model reasoning.
- Preview model summaries so incorrect or overly sensitive inferences can be edited or rejected.
- Do not infer medical diagnoses or turn ADHD-related observations into clinical claims.
- Preserve the user's ability to export, correct, retire, or request erasure of memory records. Erasure removes active rows, proposal payload copies, search indexes, logs under application control, exports, and future vectors; encrypted backups expire according to a disclosed retention period rather than promising immediate physical deletion.
- Keep sensitive memory out of logs, infrastructure diagnostics, research queries, and unrelated model context.
- Supply only the smallest relevant lesson subset to a planning prompt.

## Acceptance scenarios

1. A missed session triggers a staged experience and candidate lesson proposal, but no memory domain record exists before approval and rejected staged values are purged.
2. Two experiences support one confirmed lesson and remain independently inspectable.
3. A new experience contradicts a lesson without deleting or silently rewriting prior evidence.
4. A candidate lesson is clearly labelled and is not treated as a confirmed planning rule.
5. A relevant confirmed lesson is surfaced before planning a matching task.
6. A due review is shown without an automatic semantic database mutation.
7. Rejecting a memory proposal leaves both databases unchanged.
8. Planning remains usable during a memory-database outage with an explicit degraded-personalization notice.
9. One experience can retain multiple planning references, and deleted planning sources render as tombstones rather than deleting memory.
10. A date-only or uncertain occurrence retains its original temporal precision rather than inventing an exact timestamp.
11. A review batch containing several experiences, lessons, and evidence links is approved or rejected atomically within the memory database.
12. Lesson confirmation fails without mapped supporting evidence, while contradictory evidence remains visible and independently reviewable.
