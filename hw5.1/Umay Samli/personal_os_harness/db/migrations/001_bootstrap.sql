-- Cluster bootstrap only: create isolated databases and least-privilege roles.
-- Domain objects belong to separate planning and memory streams so neither
-- runtime role can borrow the other database.

CREATE ROLE planning_owner NOLOGIN NOINHERIT;
CREATE ROLE planning_migrator LOGIN PASSWORD :'planning_migrator_password' NOINHERIT;
CREATE ROLE planning_runtime LOGIN PASSWORD :'planning_runtime_password' NOINHERIT;

CREATE ROLE memory_owner NOLOGIN NOINHERIT;
CREATE ROLE memory_migrator LOGIN PASSWORD :'memory_migrator_password' NOINHERIT;
CREATE ROLE memory_runtime LOGIN PASSWORD :'memory_runtime_password' NOINHERIT;

GRANT planning_owner TO planning_migrator;
GRANT memory_owner TO memory_migrator;

CREATE DATABASE personal_os_planning
    OWNER planning_owner
    ENCODING 'UTF8'
    TEMPLATE template0;

CREATE DATABASE personal_os_memory
    OWNER memory_owner
    ENCODING 'UTF8'
    TEMPLATE template0;

REVOKE ALL ON DATABASE personal_os_planning FROM PUBLIC;
REVOKE ALL ON DATABASE personal_os_memory FROM PUBLIC;

GRANT CONNECT, TEMPORARY ON DATABASE personal_os_planning
    TO planning_owner, planning_migrator, planning_runtime;
GRANT CONNECT, TEMPORARY ON DATABASE personal_os_memory
    TO memory_owner, memory_migrator, memory_runtime;

ALTER ROLE planning_migrator IN DATABASE personal_os_planning
    SET search_path = public;
ALTER ROLE planning_runtime IN DATABASE personal_os_planning
    SET search_path = public;
ALTER ROLE memory_migrator IN DATABASE personal_os_memory
    SET search_path = public;
ALTER ROLE memory_runtime IN DATABASE personal_os_memory
    SET search_path = public;
