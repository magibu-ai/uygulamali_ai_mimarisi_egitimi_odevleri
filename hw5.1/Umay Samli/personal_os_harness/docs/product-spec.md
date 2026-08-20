# Personal OS Harness: MVP Product Specification

## 1. Purpose and success criteria

The harness is a single-user CLI assistant for converting goals and personal constraints into realistic long-term and daily plans, then learning from personal experiences and lessons. Planning is personalized for ADHD-related executive-function needs without presenting the system as medical diagnosis or treatment. Its purpose is to test model-driven workflows, deterministic safety boundaries, and two candidate relational databases before production adaptation.

The MVP succeeds when it can:

- capture a goal, clarify it, estimate it, and decompose it into executable work;
- represent nested tasks and shared prerequisite relationships without ambiguity;
- propose a personalized feasible schedule using backward analysis from deadlines;
- account for actual clock availability, personal time, fixed commitments, holidays, and exceptional blocks;
- capture experiences, derive evidence-backed lessons, and resurface relevant or review-due lessons;
- explain why a request is infeasible instead of persisting a logically invalid plan; and
- allow no semantic planning or memory mutation without an exact preview and explicit approval.

The MVP does not need to prove that a plan is globally optimal. “Optimized” means that the model makes a context-aware proposal aligned with the user's stated goals and constraints, then the validator proves that the proposal is structurally and temporally feasible.

## 2. Product principles

### Model judgment, deterministic safety

The model owns decisions that require judgment: how to interpret a goal, what questions to ask, how to divide it, how long work may take, what specialized conditions matter, and which feasible plan is preferable.

Code owns invariants: referential integrity, acyclic dependencies, effort-budget consistency, legal state transitions, clock alignment, non-overlap, availability, dependency order, capacity, and deadlines. Validation may reject a model proposal, but it should not silently replace it with a different plan.

### Clarification before fabrication

When missing information could materially alter an estimate, decomposition, or plan, the assistant asks a focused question. It must not create a write proposal merely to fill an important unknown with an unannounced guess. Non-critical assumptions may be used when they are surfaced in the proposal.

### Every semantic change is reviewable

Creates, updates, deletes, dependency changes, schedule changes, experiences, and lessons all use the same staged workflow. Read operations require no approval. Proposal lifecycle and minimal audit metadata are control-plane records that may be persisted before approval, but they cannot alter planning or memory domain state. A conversational “yes” may approve only the currently displayed immutable proposal revision and preview hash; it must never apply an undisclosed or changed proposal.

### Experimental schema

The planning and experience/lesson schemas are candidates being evaluated inside the harness. Compatibility with a future backend is not yet required. Schema findings and changes should be recorded so that production adaptation is an informed decision rather than a direct database copy.

### Individualized ADHD support

The assistant may learn preferences and patterns involving task initiation, time blindness, focus duration, transitions, energy, breaks, overwhelm, reminders, and recovery after disruption. It must derive these from the user's observations and confirmed lessons rather than hard-code a universal ADHD profile. It should favor small actionable starts, visible assumptions, forgiving replanning, and limited cognitive load when applicable, while preserving user agency.

The harness is an organization and reflection tool, not a clinician. It must not diagnose, prescribe medication, or present planning suggestions as medical advice.

## 3. Functional requirements

### 3.1 Conversation and CLI

The primary interface is a persistent interactive session. Natural language covers planning and editing requests, while explicit commands provide reliable control for operations such as:

- listing or showing tasks and schedules;
- inspecting dependencies and availability;
- validating the current state or a pending proposal;
- reviewing, approving, or rejecting the pending proposal; and
- viewing or changing harness configuration.

The CLI must visibly distinguish ordinary assistant text, clarification questions, read results, mutation previews, validation failures, and applied changes.

Each database manages its own pending proposal. A planning proposal and a memory proposal may coexist, but they are displayed, validated, approved, and applied independently with database-qualified identifiers. A new proposal replaces nothing implicitly within its target database: its previous pending proposal must first be approved, rejected, or explicitly discarded.

### 3.2 Tasks, hierarchy, and effort

A task may be a top-level goal, an intermediate grouping, or executable leaf work. It supports a title, description, status, priority, optional deadline, optional earliest start, estimate, tags or category, hard structured constraints, and contextual notes. Actual effort is derived from append-only work logs rather than stored as an independently editable task total.

Task hierarchy is a tree in the MVP:

- a task has zero or one parent;
- a parent may have any number of direct children;
- a task cannot parent itself or one of its ancestors; and
- scheduled sessions may reference only leaf tasks.

When a task is decomposed, the parent estimate represents the total effort budget. Each non-leaf estimate must equal the sum of its direct children's estimates, recursively producing the leaf total. Rounding uses the 15-minute scheduling unit. Estimates may be null only while a task is draft; a leaf must have a positive estimate before becoming ready or schedulable.

Changing the parent budget or a child estimate may temporarily create a mismatch only while the affected branch remains draft and has no sessions. A readiness or scheduling proposal is invalid until every budget in the branch reconciles.

Leaf tasks are splittable by default. A task may define a minimum session length, maximum session length, or an `indivisible` constraint. An indivisible task must fit in one contiguous valid interval.

Leaf task status follows explicit transitions among draft, ready, in-progress, blocked, completed, and cancelled. Completion requires the task's execution record to be complete, not merely scheduled. Reopening a terminal task is an explicit proposal. Parent status and actual effort are derived from descendant leaves. Work logs record observed duration or actual start/end, source, occurrence time, optional session ID, and corrections through superseding/reversal entries rather than destructive edits.

### 3.3 Dependencies

A dependency means the prerequisite must finish before the dependent task begins. Dependencies are independent of parent/child hierarchy:

- a task may depend on several prerequisites;
- a prerequisite may be shared by several dependent tasks;
- duplicate dependency edges are invalid;
- a task cannot depend on itself; and
- the effective leaf dependency graph must remain acyclic.

For a decomposed task, each parent endpoint expands to its descendant leaves. Validation constructs the resulting leaf-to-leaf finish-to-start graph and rejects cycles or self-edges introduced by expansion. Direct dependencies between an ancestor and its descendant are prohibited. A dependency on a parent requires all of that parent's leaf work to finish; a dependent parent cannot begin any leaf work until its prerequisites are complete unless a future relationship type explicitly introduces a weaker rule.

Planning feasibility uses projected prerequisite session completion. At execution time, a dependent task cannot start until prerequisite leaf statuses are actually completed; a future dependent session may remain scheduled while awaiting that completion.

The MVP supports only finish-to-start dependencies. Lag time and other dependency types are deferred.

### 3.4 Time, availability, and blocks

All planning uses one IANA planning timezone and defaults to `Europe/Istanbul`. The 15-minute grid is evaluated in local wall time and resulting instants are stored in UTC with the relevant zone retained. Nonexistent daylight-saving wall times are rejected; an ambiguous wall time requires an explicit earlier/later offset choice. A date-only deadline means exclusive local midnight at the start of the following date.

The scheduling grid is 15 minutes. Estimates and session boundaries must be multiples of 15 minutes. The database may store exact timestamps, but a model-created schedule outside this grid is invalid.

Before scheduling, the assistant resolves a daily profile for every affected date from confirmed recurring defaults and date-specific exceptions. It asks focused questions when sleep, personal/rest time, fixed commitments, or usable work windows are materially incomplete. It does not repeat questions already answered by a confirmed recurring profile.

Explicit daily information is authoritative. The effective personal reserve is the union of the supplied sleep and personal/rest intervals when the personal profile is marked complete; otherwise the system uses the configurable 12-hour fallback. Fixed non-personal commitments and flexible sessions must fit in the remaining time and inside availability windows. Thus 8 hours of school plus an explicit 8 hours of sleep and 3 hours of rest leaves at most 5 flexible hours. Availability windows may span more than 12 hours because they express where work could fit, not how much work is allowed.

Blocked periods subtract from otherwise available time. They can represent sleep/rest, school, work, appointments, holidays, travel, or any other commitment. A block may be:

- a one-off interval;
- an all-day date exception; or
- a recurring weekly interval with an effective date range.

Fixed commitments may be shown in the daily agenda and carry a duration, but they are not flexible task sessions and the planner cannot move them. Each block is classified as personal, non-personal, or neutral for capacity accounting. School and work normally count toward non-personal load; sleep and rest normally count toward the reserve. Overlapping blocks are allowed as input and their half-open interval unions count only once. Flexible task sessions may not overlap blocks or one another.

Recurring rules use typed weekdays, local start/end times, the planning timezone, effective-from/until dates, and enabled state. Overnight input is split into two rules in the MVP rather than stored as an ambiguous interval.

The system need not account for all 24 hours. It must assign explicit start/end times and durations to everything it actively schedules, while leaving unmodeled time alone.

### 3.5 Planning behavior

For deadline-driven work, the assistant:

1. reads the relevant task tree, dependencies, estimates, calendar constraints, and planning context;
2. asks for material missing information;
3. estimates or decomposes work when requested;
4. orders work according to hierarchy and prerequisite constraints;
5. works backward from the deadline to establish latest-safe bounds, then chooses feasible intervals using buffers and personalized preferences; and
6. presents the schedule, assumptions, tradeoffs, and any safety margin for approval.

The deadline buffer defaults to zero. The user or model may propose a buffer, but it must be visible in the preview. “Latest feasible” is a model objective and evaluation metric, not a deterministic invariant: the model may place work earlier for uncertainty, ADHD-related initiation support, or user preference. The validator proves feasibility, not global optimality. A later session cannot cause an earlier prerequisite to finish after its dependent work starts.

The model may balance concerns such as energy, preferred times, switching cost, importance, or learning sequence when those are supplied as planning context. Hard structured constraints must always be respected; free-text preferences are best-effort and should be identified when they cannot all be satisfied.

If capacity is insufficient, the assistant returns an infeasibility explanation containing the limiting deadline, required effort, available effort, and the constraints responsible. It may then propose alternatives, but cannot apply them without a new approved mutation.

### 3.6 Planning context

Context combines:

- structured hard constraints usable by validation, such as earliest start, deadline, allowed weekdays, session limits, and indivisibility; and
- free-text notes used for model judgment, such as energy patterns, uncertainty, task-specific advice, motivations, or exceptional circumstances.

Each contextual rule identifies its scope, such as global, task, category, or date range. The assistant must not present a prose preference as deterministically guaranteed unless it has a corresponding enforceable field.

### 3.7 Experiences and lessons

The assistant can identify experiences and potential lessons during conversation, task completion, plan review, or missed-work reflection. Detection is automatic; persistence remains reviewable. Rather than interrupting after each observation, it collects findings and presents one memory proposal at the end of the interaction or during an explicit daily review. The batch shows every experience, candidate lesson, evidence relationship, sensitivity, and reminder behavior before saving.

Experiences record what happened and preserve their source as factual observations. Lessons are separate interpretations that may be candidate, confirmed, superseded, or retired. Experiences and lessons have an explicit many-to-many evidence map: one lesson may use many experiences and one experience may inform many lessons. Each link is `supports`, `contradicts`, or `contextualizes` and includes a reviewable explanation. A candidate lesson requires at least one mapped experience, and a lesson cannot become confirmed without mapped supporting evidence. Contradictory evidence is preserved and shown rather than overwritten.

Confirmed lessons are surfaced automatically when relevant to a task or when due for periodic review. In the CLI MVP this is pull-based: surfacing occurs on session start, a relevant planning turn, or an explicit daily/weekly review command; background notifications are deferred. Surfacing is read-only. Editing a lesson, confirming it, or marking a review outcome is a memory mutation and follows normal approval. Planning may use confirmed lessons as context; candidate lessons must be labelled as tentative.

Planning records and memory records live in separate PostgreSQL databases and use separate tool calls, repositories, proposals, and transactions. They do not coordinate commits or share atomic records. Memory may optionally retain a planning ID and immutable source label as informational provenance, but there is no cross-database foreign key, transaction dependency, or cascade. Either database remains usable when the other is unavailable.

See `experience-lessons.md` for the detailed behavior and candidate schema.

### 3.8 Deterministic calculations and external context

The core MVP provides safe, deterministic tools for arithmetic, duration totals, unit conversion, date/time differences, timezone conversion, capacity calculations, and 15-minute rounding. The model uses these tools instead of performing important calculations in prose. Tools accept typed operands and allow-listed operations; they must not evaluate arbitrary code or unrestricted expressions.

Calculation tools improve proposal quality but are not the safety boundary. The validator independently recomputes every value that affects feasibility or a database invariant and rejects a proposal when the model's explanation or calculated result disagrees with authoritative state.

Weather is a post-core, read-only external-context capability for location- and date-sensitive activities. Planning code depends on a provider-neutral weather interface rather than a particular API or MCP server. A weather result includes its provider, resolved location, applicable time window, retrieval time, forecast data, and available uncertainty or alert information.

Weather remains a soft and time-sensitive input. It is consulted only when relevant and only during an interaction in the CLI MVP. Requests beyond the provider's forecast horizon return “forecast unavailable” rather than an invented forecast. Location is resolved with user consent, minimized to the precision needed, cached with freshness metadata, and alerts take precedence over ordinary conditions. A forecast may cause the assistant to propose an indoor alternative, a new time, or a later recheck; it cannot silently mutate the plan. Any resulting database or external calendar write uses the normal preview and approval workflow.

The first weather adapter should be added only after core planning is working. Direct API and MCP implementations may coexist behind the same interface so provider choice does not leak into task or scheduling logic.

Requested news and paper research uses provider-neutral read adapters with citations, publication dates, retrieval dates, deduplication, and explicit separation of source content from trusted instructions. It must distinguish a paper's claims from the assistant's inference and never persist or schedule anything without the appropriate proposal.

### 3.9 Mutations and approval

Each semantic write request produces an immutable proposal revision containing a stable identifier, revision, canonical preview hash, creation time, redacted source summary or turn ID, assumptions, ordered operations, and validation result. The preview shows human-readable before/after values and schedule consequences. Pending sensitive payloads are temporarily stored with sensitivity labels and a short configurable TTL; rejection or expiration purges proposed values and retains only minimal redacted audit metadata.

Approval follows this sequence:

1. Build a proposal without changing domain tables.
2. Validate it against a consistent database snapshot.
3. Display its complete contents and any warnings.
4. Receive explicit approval for that proposal identifier, revision, and preview hash.
5. Begin a transaction, lock the pending revision, detect drift, and validate again.
6. Apply all operations and mark the proposal applied atomically in its target database, or apply none.
7. Record the attempt separately and report the result to the user. Repeated approval of an applied revision returns its existing result without replaying operations.

Any edit to a displayed proposal creates a new immutable revision requiring a new preview and approval. There is no durable ambiguous `approved` state: approval either applies in the same transaction or records a failed attempt while the domain remains unchanged. Rejection or expiration leaves domain state unchanged and purges sensitive staged payloads. Destructive and bulk operations follow the same rule; the MVP has no auto-apply mode.

## 4. Validation requirements

A valid state and proposal must satisfy all applicable checks:

- referenced tasks and parent tasks exist;
- hierarchy and the dependency graph after parent-to-leaf expansion are acyclic;
- no self, duplicate, or contradictory dependency edge exists;
- only leaf tasks have scheduled sessions;
- non-draft direct-child effort budgets reconcile to their parent budgets;
- estimates and sessions align to 15-minute units and have positive duration;
- sessions fall within recurring availability and outside blocks and holidays;
- flexible sessions do not overlap;
- fixed commitments and flexible sessions fit within the daily profile, using explicit complete personal intervals when supplied and the default personal reserve only as fallback;
- indivisible and minimum/maximum session constraints hold;
- all prerequisite work finishes before dependent work begins;
- earliest-start and deadline constraints hold; and
- completed/cancelled tasks are not scheduled inconsistently.

Validation results use stable codes plus human-readable explanations so both the model and CLI can respond accurately. Warnings may describe soft-preference violations, but warnings never downgrade a failed hard constraint.

## 5. Acceptance scenarios

1. **Shared prerequisite:** Task A is a prerequisite of B and C. The graph remains valid, and both B and C are scheduled only after A completes.
2. **Cycle rejection:** A depends on B and a proposal makes B depend on A. The proposal is rejected before approval can apply it.
3. **Hierarchy cycle rejection:** A descendant cannot become an ancestor of its current parent.
4. **Effort roll-up:** A 10-hour parent split into 4-hour and 6-hour branches validates; a 4-hour and 5-hour split does not.
5. **Split work:** A splittable 3-hour leaf may occupy three valid sessions on different days.
6. **Indivisible work:** A 3-hour indivisible leaf is rejected when only separate 90-minute windows exist.
7. **Blocked time:** Sessions overlapping a school interval, holiday, personal block, or another flexible session are rejected.
8. **Backward plan:** Backward analysis establishes latest-safe bounds; prerequisites occupy earlier valid slots and an explicitly explained buffer or personal preference may place work earlier than the latest possible slot.
9. **Insufficient capacity:** A plan needing 12 hours with only 8 valid hours reports infeasibility and persists nothing.
10. **Clarification:** A task with materially insufficient scope triggers a question rather than an estimate or mutation.
11. **Approval safety:** A valid proposal does not change domain data until its exact identifier is explicitly approved.
12. **Concurrent change:** If relevant state changes after preview, approval revalidation fails or produces a new proposal; the stale operations are not applied.
13. **Timezone behavior:** A recurring local availability window is interpreted correctly across timezone-offset changes.
14. **Calculation safety:** Effort, capacity, and date arithmetic comes from deterministic tools and is independently reproduced by validation; arbitrary code cannot be evaluated.
15. **Weather context:** A weather-sensitive activity may receive a forecast-based alternative, but no schedule change occurs until the alternative is previewed and approved.
16. **Experience capture:** A completed or missed task can trigger an experience/lesson proposal, but neither record exists until its memory proposal is approved.
17. **Contradictory evidence:** A new experience can contradict a confirmed lesson without deleting it; the contradiction is shown and a revision or retirement is separately proposed.
18. **Lesson reminder:** A due confirmed lesson is surfaced without causing an unapproved database write.
19. **Database separation:** Planning and memory tools cannot write to each other's database; either proposal may be approved or rejected without affecting the other.
20. **Expanded dependency cycle:** Two individually acyclic parent trees are rejected when parent-to-leaf dependency expansion creates a cycle or self-edge.
21. **Draft decomposition:** A partially estimated branch may remain draft without sessions, but cannot become ready or schedulable until direct-child budgets reconcile.
22. **Daily profile:** With 8 hours of school, 8 hours of sleep, and 3 hours of rest explicitly supplied, at most 5 flexible hours remain; an incomplete personal profile uses the 12-hour fallback.
23. **Pull reminder:** A due lesson appears at the next CLI start or review command without implying a background notification service.
24. **ADHD agency:** Candidate or rejected patterns are not reused as confirmed facts; confirmed strategies may influence a proposal but never override hard constraints, and the user can revise or disable them.
25. **Nonjudgmental replanning:** Missed work produces a bounded, user-controlled replanning proposal without diagnostic labels or shaming language.
26. **Sensitive proposal cleanup:** Rejecting or expiring a staged memory proposal purges its proposed values while retaining only redacted audit metadata.
27. **Dangling memory reference:** Deleting a planning task preserves the related experience with a tombstoned source label rather than cascading deletion.
28. **Missing daily information:** The model asks about material gaps before scheduling but reuses confirmed recurring answers and asks only for exceptions.
29. **Evidence mapping:** Multiple experiences can support or contradict one lesson, one experience can inform multiple lessons, and confirmation is rejected without supporting evidence.

## 6. Out of scope for the core MVP

- Web research and source citation.
- A concrete weather provider in the core milestone; only its future interface and behavior are specified.
- Google Calendar access or booking.
- Multi-user ownership and authentication.
- Notifications, mobile/web user interfaces, and collaboration.
- Automated replanning triggered by external calendar events.
- Probabilistic simulations or a deterministic global optimizer.
- Dependency types other than finish-to-start.
- Production schema stability, public APIs, and migration compatibility with a separate backend.
- Route planning and production operational automation.
