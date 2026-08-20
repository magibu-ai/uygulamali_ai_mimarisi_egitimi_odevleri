-- Initial experience and lesson schema for the experimental harness.
-- Planning references are opaque provenance, never cross-database foreign keys,
-- so this private database remains independently available.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO memory_owner;

SET ROLE memory_owner;

CREATE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END
$$;

CREATE TABLE experiences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_precision text NOT NULL
        CHECK (occurred_precision IN ('date', 'instant', 'bounded_interval')),
    occurred_date date,
    occurred_at timestamptz,
    occurred_start_at timestamptz,
    occurred_end_at timestamptz,
    title text NOT NULL CHECK (btrim(title) <> ''),
    narrative text NOT NULL CHECK (btrim(narrative) <> ''),
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
    reflection text,
    statement_origin text NOT NULL
        CHECK (statement_origin IN ('user_observation', 'imported_fact', 'model_summary')),
    sensitivity text NOT NULL DEFAULT 'standard'
        CHECK (sensitivity IN ('standard', 'sensitive', 'highly_sensitive')),
    tags text[] NOT NULL DEFAULT '{}'::text[],
    source_turn_id text,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (
            occurred_precision = 'date'
            AND occurred_date IS NOT NULL
            AND occurred_at IS NULL
            AND occurred_start_at IS NULL
            AND occurred_end_at IS NULL
        )
        OR (
            occurred_precision = 'instant'
            AND occurred_date IS NULL
            AND occurred_at IS NOT NULL
            AND occurred_start_at IS NULL
            AND occurred_end_at IS NULL
        )
        OR (
            occurred_precision = 'bounded_interval'
            AND occurred_date IS NULL
            AND occurred_at IS NULL
            AND occurred_start_at IS NOT NULL
            AND occurred_end_at IS NOT NULL
            AND occurred_start_at < occurred_end_at
        )
    )
);

CREATE TABLE lessons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    statement text NOT NULL CHECK (btrim(statement) <> ''),
    rationale text NOT NULL CHECK (btrim(rationale) <> ''),
    status text NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'confirmed', 'superseded', 'retired')),
    confidence text NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    confidence_rationale text NOT NULL CHECK (btrim(confidence_rationale) <> ''),
    applicability jsonb NOT NULL DEFAULT '{"version": 1}'::jsonb,
    applicability_notes text,
    review_policy jsonb NOT NULL DEFAULT '{"version": 1, "enabled": true}'::jsonb,
    next_review_at timestamptz,
    last_reviewed_at timestamptz,
    superseded_by_id uuid REFERENCES lessons(id) ON DELETE RESTRICT,
    sensitivity text NOT NULL DEFAULT 'standard'
        CHECK (sensitivity IN ('standard', 'sensitive', 'highly_sensitive')),
    tags text[] NOT NULL DEFAULT '{}'::text[],
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (superseded_by_id IS NULL OR superseded_by_id <> id),
    CHECK (status <> 'superseded' OR superseded_by_id IS NOT NULL)
);

-- Contradictory evidence is retained alongside support. A lesson is a reviewable
-- interpretation with provenance, not a replacement for its factual experience
-- records.
CREATE TABLE lesson_evidence (
    lesson_id uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    experience_id uuid NOT NULL REFERENCES experiences(id) ON DELETE RESTRICT,
    relationship text NOT NULL
        CHECK (relationship IN ('supports', 'contradicts', 'contextualizes')),
    relevance_explanation text NOT NULL CHECK (btrim(relevance_explanation) <> ''),
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lesson_id, experience_id)
);

CREATE TABLE lesson_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id uuid NOT NULL REFERENCES lessons(id) ON DELETE RESTRICT,
    outcome text NOT NULL
        CHECK (outcome IN ('still_useful', 'needs_revision', 'contradicted', 'snoozed', 'retired')),
    reviewed_at timestamptz NOT NULL,
    notes text,
    next_review_at timestamptz,
    proposal_id uuid,
    proposal_revision integer,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (proposal_id IS NULL AND proposal_revision IS NULL)
        OR (proposal_id IS NOT NULL AND proposal_revision IS NOT NULL)
    )
);

CREATE TABLE experience_planning_references (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experience_id uuid NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    source_type text NOT NULL CHECK (btrim(source_type) <> ''),
    source_id uuid NOT NULL,
    source_label text NOT NULL CHECK (btrim(source_label) <> ''),
    source_missing boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (experience_id, source_type, source_id)
);

CREATE TABLE mutation_proposals (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    preview_hash text NOT NULL CHECK (btrim(preview_hash) <> ''),
    source_turn_id text,
    redacted_source_summary text,
    assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'applied', 'rejected', 'superseded', 'expired')),
    validation_result jsonb NOT NULL DEFAULT '{}'::jsonb,
    sensitivity text NOT NULL DEFAULT 'standard'
        CHECK (sensitivity IN ('standard', 'sensitive', 'highly_sensitive')),
    previewed_state_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
    correlation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    applied_result jsonb,
    expires_at timestamptz NOT NULL,
    applied_at timestamptz,
    rejected_at timestamptz,
    superseded_at timestamptz,
    expired_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, revision),
    CHECK (expires_at > created_at),
    CHECK (status <> 'applied' OR applied_at IS NOT NULL),
    CHECK (status <> 'rejected' OR rejected_at IS NOT NULL),
    CHECK (status <> 'superseded' OR superseded_at IS NOT NULL),
    CHECK (status <> 'expired' OR expired_at IS NOT NULL)
);

-- Approval remains bound to one immutable proposal revision and preview hash at a
-- time.
CREATE UNIQUE INDEX mutation_proposals_one_pending
    ON mutation_proposals ((true))
    WHERE status = 'pending';

CREATE TABLE mutation_operations (
    proposal_id uuid NOT NULL,
    proposal_revision integer NOT NULL,
    operation_index integer NOT NULL CHECK (operation_index >= 0),
    operation_type text NOT NULL CHECK (btrim(operation_type) <> ''),
    target_type text NOT NULL CHECK (btrim(target_type) <> ''),
    target_id uuid,
    before_values jsonb,
    proposed_values jsonb,
    schema_version integer NOT NULL DEFAULT 1 CHECK (schema_version > 0),
    purged_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (proposal_id, proposal_revision, operation_index),
    FOREIGN KEY (proposal_id, proposal_revision)
        REFERENCES mutation_proposals(id, revision)
        ON DELETE CASCADE,
    CHECK (purged_at IS NULL OR proposed_values IS NULL)
);

CREATE TABLE mutation_apply_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id uuid NOT NULL,
    proposal_revision integer NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('applied', 'validation_failed', 'drifted', 'error')),
    issue_code text,
    redacted_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id, proposal_revision)
        REFERENCES mutation_proposals(id, revision)
        ON DELETE RESTRICT
);

ALTER TABLE lesson_reviews
    ADD CONSTRAINT lesson_reviews_proposal_fk
    FOREIGN KEY (proposal_id, proposal_revision)
    REFERENCES mutation_proposals(id, revision)
    ON DELETE RESTRICT;

CREATE INDEX experiences_occurred_date_idx ON experiences(occurred_date);
CREATE INDEX experiences_occurred_at_idx ON experiences(occurred_at);
CREATE INDEX experiences_tags_idx ON experiences USING gin(tags);
CREATE INDEX experiences_search_idx
    ON experiences USING gin (
        to_tsvector('simple', title || ' ' || narrative || ' ' || coalesce(reflection, ''))
    );
CREATE INDEX lessons_status_review_idx ON lessons(status, next_review_at);
CREATE INDEX lessons_tags_idx ON lessons USING gin(tags);
CREATE INDEX lessons_search_idx
    ON lessons USING gin (to_tsvector('simple', statement || ' ' || rationale));
CREATE INDEX lesson_evidence_experience_idx ON lesson_evidence(experience_id);
CREATE INDEX experience_planning_references_source_idx
    ON experience_planning_references(source_type, source_id);

CREATE TRIGGER experiences_set_updated_at
BEFORE UPDATE ON experiences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER lessons_set_updated_at
BEFORE UPDATE ON lessons
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER lesson_evidence_set_updated_at
BEFORE UPDATE ON lesson_evidence
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER experience_planning_references_set_updated_at
BEFORE UPDATE ON experience_planning_references
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER mutation_proposals_set_updated_at
BEFORE UPDATE ON mutation_proposals
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

RESET ROLE;

GRANT USAGE ON SCHEMA public TO memory_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO memory_runtime;
GRANT INSERT, UPDATE, DELETE ON
    experiences,
    lessons,
    lesson_evidence,
    lesson_reviews,
    experience_planning_references,
    mutation_proposals,
    mutation_operations
TO memory_runtime;
GRANT INSERT ON mutation_apply_attempts TO memory_runtime;
GRANT EXECUTE ON FUNCTION set_updated_at() TO memory_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE memory_owner IN SCHEMA public
    GRANT SELECT ON TABLES TO memory_runtime;
