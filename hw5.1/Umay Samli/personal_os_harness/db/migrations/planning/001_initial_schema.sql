-- Initial planning schema for the experimental harness.
-- SQL constraints provide defense in depth; proposal-wide graph, effort, and
-- scheduling validation remains deterministic application logic.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO planning_owner;

SET ROLE planning_owner;

CREATE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END
$$;

CREATE TABLE settings (
    singleton_id smallint PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
    planning_timezone text NOT NULL,
    scheduling_resolution_minutes integer NOT NULL
        CHECK (scheduling_resolution_minutes > 0 AND 60 % scheduling_resolution_minutes = 0),
    fallback_personal_reserve_minutes integer NOT NULL
        CHECK (fallback_personal_reserve_minutes BETWEEN 0 AND 1440),
    daily_profile_complete_default boolean NOT NULL DEFAULT false,
    deadline_buffer_minutes integer NOT NULL DEFAULT 0
        CHECK (deadline_buffer_minutes >= 0),
    proposal_ttl_minutes integer NOT NULL CHECK (proposal_ttl_minutes > 0),
    reminder_display_limit integer NOT NULL CHECK (reminder_display_limit > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_profiles (
    profile_date date PRIMARY KEY,
    personal_profile_complete boolean NOT NULL DEFAULT false,
    notes text,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    description text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id uuid REFERENCES tasks(id) DEFERRABLE INITIALLY IMMEDIATE,
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text,
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready', 'in_progress', 'blocked', 'completed', 'cancelled')),
    priority smallint NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    estimate_minutes integer,
    category_id uuid REFERENCES categories(id),
    earliest_start timestamptz,
    deadline_at timestamptz,
    deadline_precision text
        CHECK (deadline_precision IS NULL OR deadline_precision IN ('instant', 'local_date')),
    planning_timezone text NOT NULL DEFAULT 'Europe/Istanbul',
    splittable boolean NOT NULL DEFAULT true,
    min_session_minutes integer,
    max_session_minutes integer,
    constraints jsonb NOT NULL DEFAULT '{"version": 1}'::jsonb,
    notes text,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (parent_id IS NULL OR parent_id <> id),
    CHECK (
        (status = 'draft' AND (
            estimate_minutes IS NULL
            OR (estimate_minutes > 0 AND estimate_minutes % 15 = 0)
        ))
        OR (
            status <> 'draft'
            AND estimate_minutes > 0
            AND estimate_minutes % 15 = 0
        )
    ),
    CHECK (
        (deadline_at IS NULL AND deadline_precision IS NULL)
        OR (deadline_at IS NOT NULL AND deadline_precision IS NOT NULL)
    ),
    CHECK (
        min_session_minutes IS NULL
        OR (min_session_minutes > 0 AND min_session_minutes % 15 = 0)
    ),
    CHECK (
        max_session_minutes IS NULL
        OR (max_session_minutes > 0 AND max_session_minutes % 15 = 0)
    ),
    CHECK (
        min_session_minutes IS NULL
        OR max_session_minutes IS NULL
        OR min_session_minutes <= max_session_minutes
    ),
    CHECK (earliest_start IS NULL OR deadline_at IS NULL OR earliest_start < deadline_at)
);

CREATE TABLE tags (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_tags (
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag_id uuid NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, tag_id)
);

-- Direct self-edges and duplicates are constrained here. Transitive, hierarchy,
-- and descendant-expanded cycles still require proposal-wide application
-- validation.
CREATE TABLE task_dependencies (
    prerequisite_task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dependent_task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prerequisite_task_id, dependent_task_id),
    CHECK (prerequisite_task_id <> dependent_task_id)
);

CREATE TABLE availability_windows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    weekday smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_local_time time NOT NULL,
    end_local_time time NOT NULL,
    effective_from date,
    effective_until date,
    label text NOT NULL CHECK (btrim(label) <> ''),
    enabled boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_local_time < end_local_time),
    CHECK (
        effective_from IS NULL
        OR effective_until IS NULL
        OR effective_from <= effective_until
    )
);

CREATE TABLE calendar_blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (btrim(title) <> ''),
    category text,
    notes text,
    load_class text NOT NULL
        CHECK (load_class IN ('personal', 'non_personal', 'neutral')),
    start_at timestamptz,
    end_at timestamptz,
    all_day_date date,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (
            start_at IS NOT NULL
            AND end_at IS NOT NULL
            AND all_day_date IS NULL
            AND start_at < end_at
        )
        OR (
            start_at IS NULL
            AND end_at IS NULL
            AND all_day_date IS NOT NULL
        )
    )
);

CREATE TABLE recurring_block_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (btrim(title) <> ''),
    category text,
    notes text,
    load_class text NOT NULL
        CHECK (load_class IN ('personal', 'non_personal', 'neutral')),
    weekday smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_local_time time NOT NULL,
    end_local_time time NOT NULL,
    effective_from date,
    effective_until date,
    planning_timezone text NOT NULL DEFAULT 'Europe/Istanbul',
    enabled boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_local_time < end_local_time),
    CHECK (
        effective_from IS NULL
        OR effective_until IS NULL
        OR effective_from <= effective_until
    )
);

CREATE TABLE planning_contexts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type text NOT NULL CHECK (scope_type IN ('global', 'task', 'category')),
    scope_id uuid,
    kind text NOT NULL CHECK (kind IN ('preference', 'hard_constraint')),
    structured_value jsonb NOT NULL DEFAULT '{"version": 1}'::jsonb,
    notes text,
    effective_from timestamptz,
    effective_until timestamptz,
    enabled boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (scope_type = 'global' AND scope_id IS NULL)
        OR (scope_type IN ('task', 'category') AND scope_id IS NOT NULL)
    ),
    CHECK (
        effective_from IS NULL
        OR effective_until IS NULL
        OR effective_from < effective_until
    )
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

-- Serial review prevents two mutable previews from both appearing to describe the
-- same current planning state.
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

CREATE TABLE scheduled_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    start_at timestamptz NOT NULL,
    end_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'completed', 'skipped', 'cancelled')),
    notes text,
    proposal_id uuid NOT NULL,
    proposal_revision integer NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id, proposal_revision)
        REFERENCES mutation_proposals(id, revision)
        ON DELETE RESTRICT,
    CHECK (start_at < end_at),
    CHECK ((extract(epoch FROM start_at)::bigint % 900) = 0),
    CHECK ((extract(epoch FROM end_at)::bigint % 900) = 0),
    CHECK ((extract(epoch FROM (end_at - start_at))::bigint % 900) = 0),
    -- '[)' makes adjacent sessions legal. Only active session statuses reserve
    -- time and participate in overlap exclusion.
    EXCLUDE USING gist (
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('planned', 'in_progress'))
);

CREATE TABLE work_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    session_id uuid REFERENCES scheduled_sessions(id) ON DELETE SET NULL,
    actual_start_at timestamptz,
    actual_end_at timestamptz,
    observed_minutes integer,
    source text NOT NULL CHECK (source IN ('manual', 'timer', 'import')),
    occurred_at timestamptz NOT NULL,
    notes text,
    supersedes_work_log_id uuid REFERENCES work_logs(id) ON DELETE RESTRICT,
    is_reversal boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (
            actual_start_at IS NOT NULL
            AND actual_end_at IS NOT NULL
            AND observed_minutes IS NULL
            AND actual_start_at < actual_end_at
        )
        OR (
            actual_start_at IS NULL
            AND actual_end_at IS NULL
            AND observed_minutes > 0
        )
    )
);

CREATE INDEX tasks_parent_id_idx ON tasks(parent_id);
CREATE INDEX tasks_status_deadline_idx ON tasks(status, deadline_at);
CREATE INDEX tasks_search_idx
    ON tasks USING gin (to_tsvector('simple', title || ' ' || coalesce(description, '')));
CREATE INDEX task_dependencies_dependent_idx ON task_dependencies(dependent_task_id);
CREATE INDEX availability_windows_lookup_idx
    ON availability_windows(enabled, weekday, effective_from, effective_until);
CREATE INDEX calendar_blocks_interval_idx ON calendar_blocks(start_at, end_at);
CREATE INDEX calendar_blocks_all_day_idx ON calendar_blocks(all_day_date);
CREATE INDEX recurring_block_rules_lookup_idx
    ON recurring_block_rules(enabled, weekday, effective_from, effective_until);
CREATE INDEX planning_contexts_scope_idx ON planning_contexts(scope_type, scope_id, enabled);
CREATE INDEX scheduled_sessions_task_time_idx ON scheduled_sessions(task_id, start_at);
CREATE INDEX work_logs_task_occurred_idx ON work_logs(task_id, occurred_at DESC);

CREATE TRIGGER settings_set_updated_at
BEFORE UPDATE ON settings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER daily_profiles_set_updated_at
BEFORE UPDATE ON daily_profiles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER categories_set_updated_at
BEFORE UPDATE ON categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER tasks_set_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER tags_set_updated_at
BEFORE UPDATE ON tags
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER availability_windows_set_updated_at
BEFORE UPDATE ON availability_windows
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER calendar_blocks_set_updated_at
BEFORE UPDATE ON calendar_blocks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER recurring_block_rules_set_updated_at
BEFORE UPDATE ON recurring_block_rules
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER planning_contexts_set_updated_at
BEFORE UPDATE ON planning_contexts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER mutation_proposals_set_updated_at
BEFORE UPDATE ON mutation_proposals
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER scheduled_sessions_set_updated_at
BEFORE UPDATE ON scheduled_sessions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO settings (
    planning_timezone,
    scheduling_resolution_minutes,
    fallback_personal_reserve_minutes,
    daily_profile_complete_default,
    deadline_buffer_minutes,
    proposal_ttl_minutes,
    reminder_display_limit
) VALUES (
    'Europe/Istanbul',
    15,
    720,
    false,
    0,
    30,
    5
);

RESET ROLE;

GRANT USAGE ON SCHEMA public TO planning_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO planning_runtime;
GRANT INSERT, UPDATE, DELETE ON
    settings,
    daily_profiles,
    categories,
    tasks,
    tags,
    task_tags,
    task_dependencies,
    availability_windows,
    calendar_blocks,
    recurring_block_rules,
    planning_contexts,
    mutation_proposals,
    mutation_operations,
    scheduled_sessions
TO planning_runtime;
GRANT INSERT ON work_logs, mutation_apply_attempts TO planning_runtime;
GRANT EXECUTE ON FUNCTION set_updated_at() TO planning_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE planning_owner IN SCHEMA public
    GRANT SELECT ON TABLES TO planning_runtime;
