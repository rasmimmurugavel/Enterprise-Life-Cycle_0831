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

For local development and running the eval fixtures without touching a
real database, see `docker-compose.yml` at the repo root (added in a
later build step) and `db/seed/`, which seeds a disposable Postgres
instance with tables representing each defect class the rubric scores
(nulls, duplicates, orphaned FKs, a PII-shaped column, stale data).
