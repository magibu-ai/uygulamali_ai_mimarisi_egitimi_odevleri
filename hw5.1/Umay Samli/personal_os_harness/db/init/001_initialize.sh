#!/usr/bin/env bash
# PostgreSQL runs this file only for a new data volume. Restarting Compose does
# not migrate an existing volume; apply later SQL streams manually in sequence.

set -Eeuo pipefail

readonly sql_root="/opt/personal-os-db/migrations"

psql   --username "$POSTGRES_USER"   --dbname "$POSTGRES_DB"   --set=ON_ERROR_STOP=1   --set=planning_migrator_password="$PLANNING_MIGRATOR_PASSWORD"   --set=planning_runtime_password="$PLANNING_RUNTIME_PASSWORD"   --set=memory_migrator_password="$MEMORY_MIGRATOR_PASSWORD"   --set=memory_runtime_password="$MEMORY_RUNTIME_PASSWORD"   --file="$sql_root/001_bootstrap.sql"

psql   --username "$POSTGRES_USER"   --dbname personal_os_planning   --set=ON_ERROR_STOP=1   --file="$sql_root/planning/001_initial_schema.sql"

psql   --username "$POSTGRES_USER"   --dbname personal_os_memory   --set=ON_ERROR_STOP=1   --file="$sql_root/memory/001_initial_schema.sql"
