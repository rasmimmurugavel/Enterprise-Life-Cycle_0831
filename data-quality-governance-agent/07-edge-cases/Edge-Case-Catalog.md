# Edge Case Catalog
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | EC-DQGA-07 |
| Traces from | `02-requirements/FRD-SRS.md`, `03-design/HLD.md` §6 |
| Traces to | `08-traceability/RTM.md`, `10-defects/Defect-Log.md` |

Combinatorial, timing, and compliance-trap cases that a straight
functional test pass over the FRs would miss. EC-001 was found and
fixed during this build (see `10-defects/Defect-Log.md` DEF-001) -
it's the sharpest example of why this catalog exists as a distinct
document from `06-test-cases/`: nobody wrote a *requirement* that says
"column names must not be SQL-injectable," but the system has to
survive one anyway.

## EC-001 - Identifier injection via a maliciously-named column (found & fixed)

**Category**: Security / compliance trap.

Postgres allows a quoted identifier to contain almost any character,
including a literal double-quote (escaped as `""` at creation time):
`create table t ("x"" or pg_sleep(999) --" int)` is legal DDL. Several
tools (`profile_table`, `top_values`, `check_duplicates`, `detect_pii`,
`check_referential_integrity`) build SQL text by interpolating a
schema/table/column name supplied as a **tool-call argument** - which
the agent populates from whatever `inspect_schema` told it, but which
is, at the point the query-building code runs, just a string the
model passed in like any other argument.

The original implementation quoted identifiers with a bare
`f'"{name}"'`. For a column literally named `x" or pg_sleep(999) --`,
that produces:

```sql
select "x" or pg_sleep(999) --" from t
```

which is a **syntactically valid single SELECT statement** - the
closing `"` after `x` ends the identifier early, `or pg_sleep(999)`
becomes a boolean expression appended to the select list, and
`--" from t` is consumed as a trailing comment. Critically, this
statement contains no `INSERT`/`UPDATE`/`DELETE`/DDL node, so
`assert_select_only`'s AST guard (NFR-201) - which checks statement
*type*, not identifier *content* - does not catch it. Verified live
during this build (see `10-defects/Defect-Log.md` DEF-001): the
crafted string parsed as `OK` under the guard both before and after
the fix; the difference is what it parses *into*.

**Fix**: `mcp_server/tools/db.py::quote_ident` doubles any embedded
`"` before wrapping the name in quotes - the standard SQL identifier
escape. The same crafted name now produces
`select "x"" or pg_sleep(999) --" from t`, which sqlglot parses as one
`Identifier` node whose literal value is the entire string
`x" or pg_sleep(999) --` - Postgres would report "column does not
exist," not execute anything. Every dynamic-identifier call site now
routes through `quote_ident` (verified by grep - see the commit that
introduced this fix).

**Test case**: TC-025 covers the DML-inside-CTE class of statement-level
bypass; this class (content-level bypass within an otherwise-valid
SELECT) is exercised in `tests/test_db_guardrails.py::test_quote_ident_neutralizes_injection`.

**Residual risk / follow-up**: `quote_ident` handles identifiers
correctly, and no tool ever interpolates a raw *value* (as opposed to
an identifier) into SQL text outside of parameterized placeholders
(`%(name)s`) - confirmed by the same grep. If a future tool adds
value interpolation, it must use parameters, never string formatting.

## EC-002 - Empty table (zero rows)

`profile_table` divides `null_rows / total_rows`. Verified guarded
(`profiling_tools.py`: `round(null_rows / total, 4) if total else 0.0`)
- a zero-row table reports `null_rate: 0.0` rather than raising
`ZeroDivisionError` and aborting the whole audit over one empty table.

## EC-003 - Self-referencing foreign key

A table with a FK column referencing its own primary key (e.g. an
`employees.manager_id -> employees.id` hierarchy) produces a
`check_referential_integrity` query that joins the table to itself
under two aliases (`c`/`p` in `integrity_tools.py`). This is valid SQL
regardless of whether parent and child are the same table - no special
case needed, but worth an explicit fixture/test rather than assuming
it "just works" (tracked as a follow-up fixture, not yet in
`eval/fixtures/`).

## EC-004 - Concurrent audit runs writing to the same audit log

Two audit runs (e.g. two Streamlit users, or a UI run overlapping a
scheduled eval run) append to the same `audit_log/audit.jsonl`
concurrently. `audit_log.py` serializes writes with a module-level
`threading.Lock` and writes one JSON object per line atomically via a
single `write()` call - safe against interleaved/corrupted lines
within one process. **Not** safe across multiple *processes* writing
the same file without OS-level advisory locking; single-process
deployment is assumed for this release (see Test-Strategy §3
concurrency note) - flagged as a gap if this app is ever run as
multiple replicas sharing one log file/volume.

## EC-005 - MCP server subprocess crashes mid-audit

If the `mcp_server.server` subprocess dies (OOM, an unhandled
exception outside the tool-call try/except boundary) mid-run, the
`stdio_client` transport's pipe closes and the next `call_tool` await
in `app/agent.py` raises. This propagates as an unhandled exception
out of `run_audit_async`, caught by Streamlit's generic
`except Exception` in `app/app.py::_audit_tab` and shown as "Unexpected
error" rather than hanging indefinitely. Acceptable for this release;
a future improvement would distinguish "transport died" from "tool
returned an error" for a clearer message (tracked, not blocking).

## EC-006 - Extremely wide or deep schema (thousands of tables/columns)

`inspect_schema`'s single batched query (FR-111) avoids the N+1
round-trip problem, but a database with, say, 5,000 tables would
return a very large metadata result in one call. `governed_select` is
called with `row_limit=5000` for this tool (`schema_tools.py`) rather
than the default 500, specifically because metadata rows (one per
column) are cheap and this tool's whole point is a complete picture -
but a schema wider than that still truncates with `truncated: true`
rather than silently dropping rows or OOMing. No fixture currently
exercises the actual truncation path at scale (TC-014 marks this
boundary as planned, not yet executed - see `09-test-execution/`).

## EC-007 - Timezone-naive "staleness" comparison

`stale_data`'s `last_synced_at` is `timestamptz` (timezone-aware) by
design specifically to avoid a subtle defect class: a naive
`timestamp` column compared against `now()` under a session timezone
mismatch can be wrong by hours without ever producing an error. Any
future fixture or real-world table using a naive `timestamp` for a
freshness column should be flagged by the agent as a *validity*
concern in its own right (ambiguous timezone semantics), not silently
trusted - documented here since no current fixture exercises a naive
timestamp specifically.

## EC-008 - A column both PK and declared "unique" via a separate constraint

`check_duplicates` is called per declared unique/PK column *set*, not
globally - a table with both a PK and a separate `UNIQUE` constraint on
a different column needs two calls. The agent decides how many calls
to make from what `inspect_schema` shows it; nothing in the tool layer
deduplicates or caps this per table, so a table with many unique
constraints could consume a large share of the tool-call budget
(FR-121). Acceptable given `DQ_MAX_TOOL_CALLS` is configurable and the
agent is instructed to prioritize (SYSTEM_PROMPT step 3); not
independently guarded at the tool layer.

## EC-009 - Governance override on a column that is later dropped

FR-132 lets a reviewer mark a PII classification as a false positive.
If that column is later dropped and a new column with the same name
added (unrelated data), a naive override store keyed only on
`table.column` would incorrectly suppress PII flagging on the new
column. **Not yet implemented** (FR-132's override persistence itself
is a documented but not-yet-built feature - see
`10-defects/Defect-Log.md` for tracking); noted here so the eventual
implementation keys overrides with enough context (e.g. a hash of the
column's data type + a review timestamp) to expire stale overrides
rather than trusting a bare name match indefinitely.
