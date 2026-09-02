# Defect Log
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | DEF-DQGA-10 |
| Traces from | `09-test-execution/Execution-Summary.md`, `07-edge-cases/Edge-Case-Catalog.md` |

## DEF-001 - SQL identifier injection via a maliciously-named column

| Field | Value |
|---|---|
| Severity | Critical |
| Status | **Fixed** (same build pass it was found in) |
| Found via | Manual adversarial analysis of `mcp_server/tools/*.py` while writing `07-edge-cases/Edge-Case-Catalog.md`, confirmed live against `sqlglot` |
| Affected | `profiling_tools.py`, `integrity_tools.py`, `pii_tools.py` |
| Related | `07-edge-cases/Edge-Case-Catalog.md` EC-001, RTM `08-traceability/rtm.csv` BR-01/BR-07 |

**Description**: `profile_table`, `top_values`, `check_duplicates`,
`detect_pii`, and `check_referential_integrity` built SQL text by
interpolating schema/table/column names with a bare
`f'"{name}"'`. A column whose name contains an embedded double-quote
(a legal Postgres identifier, e.g. `x" or pg_sleep(999) --`) closes
the quoted identifier early and splices an arbitrary boolean
expression into an otherwise-valid single `SELECT` statement - which
passes `assert_select_only`'s AST guard (NFR-201) because that guard
checks statement *type*, not identifier *content*.

**Impact if shipped**: a database containing (or later given, by
anyone with `CREATE`/`ALTER` on any table the audit role can see) an
adversarially-named column could use the audit agent itself as an
execution path for arbitrary read-side SQL expressions - directly
undermining BR-01 ("read-only... connection") and BR-07 (governance
limits "not bypassable by the agent's own reasoning") despite the
top-level read-only guard being intact.

**Fix**: `mcp_server/tools/db.py::quote_ident` doubles any embedded
`"` before quoting - the standard SQL identifier escape, which makes
it impossible to terminate the identifier early regardless of content.
Every call site that built a `f'"{...}"'` identifier was switched to
`quote_ident` (verified by grep - zero remaining raw occurrences in
`mcp_server/tools/`).

**Verification**: `09-test-execution/Execution-Summary.md` §2.2 - the
crafted payload parses into an injected `pg_sleep()` expression before
the fix and into one inert literal `Identifier` node after it, checked
via `sqlglot`'s parse tree directly (not inferred from the guard's
accept/reject verdict alone, since both versions pass the statement-type
check - the point is *what* they parse into).

## DEF-002 - FR-132 (governance override persistence) not implemented

| Field | Value |
|---|---|
| Severity | Medium (documented requirement gap, not a defect in shipped behavior) |
| Status | Open |
| Found via | Self-review while writing `08-traceability/RTM.md` |
| Affected | `app/app.py` (no override UI), no override storage exists |

**Description**: FRD-SRS FR-132 specifies that a governance reviewer
shall be able to mark a PII classification as a false positive via the
UI, with the override persisted and reflected in future audits of the
same column. Neither the storage nor the UI control for this exists
yet - `detect_pii` and the always-on masking middleware
(`governance.py`) have no concept of an override.

**Impact**: a column that a human reviewer has confirmed is a false
positive will be re-flagged on every subsequent audit until this is
built. Not a correctness or security defect (the system fails toward
*more* caution, not less) but a real usability/workflow gap for a
governance team using this in practice.

**Recommended fix** (not yet implemented): a small `overrides` table
or JSON store keyed by `(schema, table, column)` plus enough context
to detect a since-changed column (per EC-009's caution about a
dropped-and-recreated column reusing a name) - e.g. a data-type hash
and a review timestamp with a sensible expiry - checked by
`mcp_server/tools/pii.py::classify_columns` before a column is flagged.

## DEF-003 - PK/FK detection silently returns nothing under the real least-privilege role

| Field | Value |
|---|---|
| Severity | Critical |
| Status | **Fixed** (same build pass it was found in) |
| Found via | First live-database run against the real `dq_audit_reader` role (docker-compose / local Postgres, see `09-test-execution/Execution-Summary.md` §2.11) - not caught by any unit test, since unit tests never touched a real database |
| Affected | `schema_tools.py::_INSPECT_SCHEMA_SQL` (PK/FK columns), `integrity_tools.py::_FK_LIST_SQL` |

**Description**: Both queries joined
`information_schema.table_constraints` / `key_column_usage` /
`constraint_column_usage` to find primary and foreign keys. These
particular `information_schema` views are defined by Postgres to only
return rows for constraints on tables the *querying role owns* - not
merely has `SELECT` on. Every fixture up to this point had been
verified either via pure unit tests (no database) or, implicitly,
would have been run as a superuser during manual testing - so this
never surfaced. The first run against the actual `dq_audit_reader`
role (which owns nothing - it only has `SELECT`, exactly as designed)
returned zero primary keys and zero foreign keys for every table,
silently, with no error.

**Impact**: this is the core function of `inspect_schema` and
`check_referential_integrity` - under the intended real-world
permission model (a read-only role that does NOT own the audited
tables, per BR-01/NFR-206), the agent would never see a single PK or
FK, and orphaned-FK detection (a headline capability, FR-120) would
never fire. The system would have appeared to work perfectly in any
manual test run as an owner/superuser and been silently non-functional
in the one setup it is actually designed for.

**Fix**: rewrote both queries against `pg_catalog`
(`pg_constraint`/`pg_class`/`pg_namespace`/`pg_attribute`, using
`unnest(con.conkey, con.confkey)` to pair local/referenced columns by
position for composite keys) instead of `information_schema`. System
catalogs are readable by any role regardless of ownership.
`information_schema.columns` (used for the plain column list) does
*not* have this restriction and was left as-is - confirmed by testing
both directly as `dq_audit_reader` before changing anything.

**Verification**: `tests/test_live_integration.py` (new,
`DATABASE_URL`/`PGHOST`-gated) - `test_inspect_schema_detects_primary_key_under_readonly_role`
and `test_check_referential_integrity_finds_the_seeded_orphan` run
these exact code paths against a live Postgres under a real
non-owner role and assert the PK/FK/orphan are found. Also verified
manually via `psql` as `dq_audit_reader` directly - see
`09-test-execution/Execution-Summary.md` §2.11.

## DEF-004 - `AmbiguousParameter` when an optional filter parameter is NULL

| Field | Value |
|---|---|
| Severity | High |
| Status | **Fixed** (found immediately after DEF-003, same live run) |
| Found via | Same live-database run, calling `check_referential_integrity` without a `table` filter |
| Affected | `integrity_tools.py::_FK_LIST_SQL` |

**Description**: The clause `%(table)s is null or c.relname = %(table)s`
uses the same parameter in two positions. When the passed value is
Python `None`, psycopg has no type information to send for that
parameter (a bare `NULL` has no type), and Postgres cannot infer one
from `is null`/`= relname` alone across two placeholder occurrences,
raising `psycopg.errors.AmbiguousParameter`. This is a pre-existing
pattern (the same shape existed in the `information_schema`-based
query DEF-003 replaced) that had simply never been executed against a
real connection before.

**Fix**: explicit cast, `%(table)s::text is null or c.relname = %(table)s::text`
- gives Postgres a concrete type for the parameter regardless of
whether the passed value is `NULL`.

**Verification**: `tests/test_live_integration.py::test_check_referential_integrity_finds_the_seeded_orphan`
calls `check_referential_integrity(schema)` with no `table` argument
(the common case - auditing a whole schema) against a live database.

## Summary

| ID | Severity | Status |
|---|---|---|
| DEF-001 | Critical | Fixed |
| DEF-003 | Critical | Fixed |
| DEF-004 | High | Fixed |
| DEF-002 | Medium | Open |

Per `04-test-strategy/Test-Strategy.md` §5 exit criteria (no open
critical/high defects), DEF-001/DEF-003/DEF-004 all being fixed clears
the release-blocking bar for this pass; DEF-002 is tracked but does
not block release of the current feature set since FR-132 was never
claimed as delivered
in this pass (see `09-test-execution/Execution-Summary.md` §3).
