# Harness schema scripts

The harness uses separate plain SQL streams for the planning and memory PostgreSQL databases. Scripts are reviewed and applied manually with `psql`. The harness does not use a migration framework; backend migration tooling is outside this repository's scope.

- Put planning scripts in `planning/`.
- Put memory scripts in `memory/`.
- Name scripts `<three-digit-sequence>_<description>.sql`, starting with `001` in each stream.
- Never run a planning script against the memory database or a memory script against the planning database.

Apply a script explicitly:

```bash
psql "$PLANNING_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/planning/001_example.sql
psql "$MEMORY_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/memory/001_example.sql
```

Initial schema scripts belong to Phase 2 and are intentionally not included in the foundation scaffold.
