-- Runs first (docker-entrypoint-initdb.d executes files alphabetically)
-- against the dev-only docker-compose Postgres. Creates the same
-- least-privilege read-only role documented in db/README.md, pre-wired
-- to match .env.example's defaults so `docker compose up` + `.env`
-- work together with zero manual provisioning for local development.
--
-- This is a LOCAL DEV CONVENIENCE ONLY - a real environment provisions
-- this role by hand (or via infra-as-code) against its own database,
-- following db/README.md, with a secret from its own secrets manager.
create role dq_audit_reader with login password 'devpassword';

grant connect on database dq_dev to dq_audit_reader;

-- The other seed files (running after this one, alphabetically) each
-- create their own schema and grant USAGE on it explicitly - Postgres
-- has no "default privilege" hook for auto-granting USAGE on schemas
-- that don't exist yet. This default-privileges rule only covers the
-- SELECT-on-tables half: any table the `postgres` role (running these
-- init scripts) creates from here on, in any schema, is automatically
-- readable by dq_audit_reader without a second manual grant per table.
alter default privileges for role postgres grant select on tables to dq_audit_reader;
