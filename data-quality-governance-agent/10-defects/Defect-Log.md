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

## Summary

| ID | Severity | Status |
|---|---|---|
| DEF-001 | Critical | Fixed |
| DEF-002 | Medium | Open |

Per `04-test-strategy/Test-Strategy.md` §5 exit criteria (no open
critical/high defects), DEF-001 being fixed clears the release-blocking
bar for this pass; DEF-002 is tracked but does not block release of
the current feature set since FR-132 was never claimed as delivered
in this pass (see `09-test-execution/Execution-Summary.md` §3).
