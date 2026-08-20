# Local PostgreSQL

This directory owns the harness-only PostgreSQL environment. It uses Docker Compose and plain SQL applied by `psql`; it does not use Flyway or another migration framework.

## Python module seams

Keep infrastructure and SQL here, but put executable Python in the installable package:

- `src/personal_os/db/`: Psycopg adapters, repositories, transactions, and the database module interfaces used by the application.
- `src/personal_os/tools/`: bounded model-tool adapters that call application/database interfaces; no SQL and no borrowed connection from the other database.
- `src/personal_os/agent.py`: conversation and tool-round orchestration; it depends on tool interfaces rather than repository implementation details.

The dependency direction is agent → tools → application/database interfaces → Psycopg adapters. Domain validation must not import the agent, CLI, or Ollama provider.

## Start and verify

From the repository root:

```bash
cp db/.env.example db/.env
docker compose -f db/docker-compose.yml config --quiet
docker compose -f db/docker-compose.yml up -d
docker compose -f db/docker-compose.yml exec -T postgres \
  psql -U postgres -d postgres -f /opt/personal-os-db/verify.sql
```

Application URLs matching the defaults are documented in `configs/.env.example`.

Initialization runs only when the named volume is empty. Editing an initialization SQL file does not modify an existing database. Apply later scripts manually and record their sequence, or recreate disposable local data deliberately.

## Stop

```bash
docker compose -f db/docker-compose.yml down
```

Do not use `down --volumes` unless deleting all local harness database data is intentional.
