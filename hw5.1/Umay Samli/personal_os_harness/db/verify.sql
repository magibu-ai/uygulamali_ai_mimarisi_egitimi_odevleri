\set ON_ERROR_STOP on

\connect personal_os_planning

DO $$
BEGIN
    IF to_regclass('public.settings') IS NULL
       OR to_regclass('public.tasks') IS NULL
       OR to_regclass('public.scheduled_sessions') IS NULL
       OR to_regclass('public.mutation_proposals') IS NULL THEN
        RAISE EXCEPTION 'planning schema is incomplete';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM settings
        WHERE singleton_id = 1
          AND planning_timezone = 'Europe/Istanbul'
          AND scheduling_resolution_minutes = 15
    ) THEN
        RAISE EXCEPTION 'planning defaults are missing';
    END IF;
END
$$;

\connect personal_os_memory

DO $$
BEGIN
    IF to_regclass('public.experiences') IS NULL
       OR to_regclass('public.lessons') IS NULL
       OR to_regclass('public.lesson_evidence') IS NULL
       OR to_regclass('public.mutation_proposals') IS NULL THEN
        RAISE EXCEPTION 'memory schema is incomplete';
    END IF;
END
$$;

\connect postgres

DO $$
BEGIN
    IF has_database_privilege('planning_runtime', 'personal_os_memory', 'CONNECT') THEN
        RAISE EXCEPTION 'planning runtime can connect to memory database';
    END IF;

    IF has_database_privilege('memory_runtime', 'personal_os_planning', 'CONNECT') THEN
        RAISE EXCEPTION 'memory runtime can connect to planning database';
    END IF;

    IF pg_has_role('planning_runtime', 'memory_owner', 'MEMBER')
       OR pg_has_role('memory_runtime', 'planning_owner', 'MEMBER') THEN
        RAISE EXCEPTION 'runtime roles cross database ownership boundaries';
    END IF;
END
$$;

SELECT 'database verification passed' AS result;
