# Database provisioning

## Provisioning a read-only audit role (BR-01, NFR-206)

Run once, as a superuser or a role with `CREATEROLE`/`GRANT` privileges,
against the target database. Replace `changeme` with a generated
secret from your secrets manager before running in any real
environment.

```sql
-- 1. Dedicated login role, no special attributes.
CREATE ROLE dq_audit_reader WITH LOGIN PASSWORD 'changeme';

-- 2. Connect + see the schemas the audit is allowed to touch.
GRANT CONNECT ON DATABASE appdb TO dq_audit_reader;
GRANT USAGE ON SCHEMA public TO dq_audit_reader;

-- 3. SELECT only - on existing tables...
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dq_audit_reader;

-- ...and on tables created after this role is provisioned, so a new
-- table doesn't silently fall outside audit coverage or (worse)
-- require re-granting by hand.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO dq_audit_reader;

-- 4. Explicitly confirm no write privileges (belt and suspenders -
--    the app's own governance layer also independently blocks writes
--    at the AST level regardless of what the role can technically do,
--    per NFR-207).
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM dq_audit_reader;
REVOKE CREATE ON SCHEMA public FROM dq_audit_reader;
```

Repeat step 2-4 for each additional schema you want the agent to be
able to audit, and list them in `DQ_ALLOWED_SCHEMAS` (see
`.env.example`). A schema you do not grant `USAGE` on is invisible to
the role regardless of the allowlist - the allowlist narrows further,
it never widens what the database itself permits.

## Verifying the role is actually read-only

```sql
select has_database_privilege('dq_audit_reader', current_database(), 'CREATE'); -- expect false
select has_schema_privilege('dq_audit_reader', 'public', 'CREATE');             -- expect false
select has_table_privilege('dq_audit_reader', 'public.<any_table>', 'INSERT');  -- expect false
```

`mcp_server/tools/db.py::DBAdapter.check_role_privileges()` runs the
equivalent check programmatically on server startup and logs a
governance warning (not a hard failure - the app-layer AST guard is
what actually blocks writes, per NFR-207) if the role turns out to have
broader privileges than intended.

## Local dev database

```bash
docker compose up -d          # Postgres 16, seeded automatically on first start
cp .env.example .env          # then set PGUSER=dq_audit_reader, PGPASSWORD=devpassword,
                               # PGDATABASE=dq_dev - matching what db/seed/00_provision_role.sql created
pytest tests/                 # unit tests + live integration tests (auto-detected via PGHOST)
```

`docker-compose.yml` mounts `db/seed/` into
`/docker-entrypoint-initdb.d/`, so Postgres runs every `.sql` file
there once, alphabetically, on first container start:
`00_provision_role.sql` creates the exact `dq_audit_reader` role
described above (password `devpassword`, dev-only - never reuse it
anywhere real), then each fixture script creates its own schema,
grants that role `USAGE` on it, and seeds data representing one defect
class the rubric scores (nulls, duplicates, orphaned FKs, a
PII-shaped column, stale data). This is also exactly what
`tests/test_live_integration.py` and `eval/eval_runner.py` expect to
find.

No Docker available? `docker-compose.yml` is just a thin wrapper
around a stock `postgres:16-alpine` plus that init-script convention -
any local Postgres 16+ works identically: create a `dq_dev` database
and run the same files in `db/seed/` against it in order with `psql`.

## Eval seeding role vs. the audit role

`eval/eval_runner.py` needs to `CREATE SCHEMA`/`CREATE TABLE` to load
each fixture (`db/seed/*.sql`) - that is deliberately **not** a
privilege the read-only `dq_audit_reader` role above has, and the eval
runner never grants it one. Instead, point the eval runner at a
separate, more-privileged connection via `DQ_EVAL_ADMIN_DATABASE_URL`
(falls back to `DATABASE_URL` if unset); the agent itself, even during
an eval run, still only ever queries through `dq_audit_reader`
(`PGUSER`/`.env`). This mirrors a real environment: whoever loads
fixtures/test data into a database is a different, more-privileged
actor than the audit agent that later reads it.

```bash
export DQ_EVAL_ADMIN_DATABASE_URL="postgresql://postgres:changeme@localhost:5432/dq_eval"
export DATABASE_URL="postgresql://dq_audit_reader:changeme@localhost:5432/dq_eval"
python -m eval.eval_runner
```
