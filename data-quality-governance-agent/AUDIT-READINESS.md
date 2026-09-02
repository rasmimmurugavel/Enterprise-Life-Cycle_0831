# Audit Readiness
## Data Quality & Governance Agent

One-page reference for a compliance reviewer or auditor asking "how do
I know this AI system's outputs can be trusted, and what controls stop
it from doing something it shouldn't." Every claim below links to the
document or code that actually implements it - this page is a map, not
a new source of truth.

## 1. Access control

| Control | Implementation | Evidence |
|---|---|---|
| The agent connects with a dedicated, least-privilege, `SELECT`-only role | `db/README.md` provisioning SQL; `mcp_server/config.py` reads credentials from env, never hard-coded | FR-101, NFR-206 |
| Even a misconfigured role cannot write | AST-level guard rejects any non-`SELECT` statement regardless of what the DB role technically permits | `mcp_server/tools/db.py::assert_select_only`, NFR-207, DEF-001 (an injection variant of this was found and fixed - see below) |
| Access is scoped to specific schemas | `DQ_ALLOWED_SCHEMAS` allowlist enforced at the tool layer on every call | FR-103, `mcp_server/tools/governance.py::require_schema_allowed` |
| Secrets never appear in logs, UI, or reports | `.env`-only credential handling; `redacted_target()` for display; audit log never stores connection strings | NFR-205, TC-065 |

## 2. Data governance / PII handling

| Control | Implementation | Evidence |
|---|---|---|
| PII is masked before it ever reaches the LLM | Masking happens in the tool-layer governance middleware, not as a prompt instruction the model could ignore | `mcp_server/tools/governance.py::governed_select`, `mcp_server/tools/pii.py`, NFR-204 |
| PII detection covers both obvious (column name) and non-obvious (value-pattern-only) cases | Two independent detectors; the `pii_column` eval fixture specifically seeds PII with no name hint | `12-eval-rubrics/Eval-Rubric-Spec.md` §3 |
| Zero tolerance for a PII leak | The eval release gate hard-fails on any known PII value appearing anywhere in a transcript or output - not a soft metric | `eval/rubrics.yaml` `release_gate.max_pii_leak_incidents: 0`, verified in `09-test-execution/Execution-Summary.md` §2.9 |
| PII findings are classifications, never values | `detect_pii` returns category + hit-rate only; sampled raw rows never leave the function | `mcp_server/tools/pii_tools.py`, TC-057 |

## 3. Auditability / traceability

| Control | Implementation | Evidence |
|---|---|---|
| Every tool call is logged, independent of what the agent reports | Append-only JSONL, written before the result reaches the agent | `mcp_server/tools/audit_log.py`, FR-140/141, BR-06 |
| A finding is reproducible from the log alone | The exact query + row count + duration for every call is recorded | NFR-208, TC-066 |
| Output shape is contractually enforced, not just hoped for | Every audit run's final answer is validated against a JSON Schema; a non-conforming answer is a failed run, not a degraded one (fail closed) | `app/agent.py::validate_findings`, `eval/schemas/findings.schema.json` |
| A self-contained report exists for handoff to an external auditor | Markdown report with run metadata, scorecard, findings, governance summary - no dependency on the live session | `app/ui/scorecard.py::build_markdown_report`, FR-143 |

## 4. Model/judgment governance

| Control | Implementation | Evidence |
|---|---|---|
| What counts as a "defect" and how severe it is, is a versioned, business-owned artifact, not implicit in a prompt | `eval/rubrics.yaml`, owned by Data Governance | BR-08 |
| Every release is scored against fixed scenarios with known-correct answers before shipping | `eval/eval_runner.py` + `eval/fixtures/*` | `12-eval-rubrics/Eval-Rubric-Spec.md` |
| A release that regresses recall, precision, severity accuracy, or leaks PII is blocked | Release gate thresholds in `eval/rubrics.yaml`, non-negotiable on the PII dimension | Same |
| The agent never fabricates coverage it didn't actually perform | Hitting the tool-call budget forces an honest partial answer (`tables_not_audited`), never a guessed score | FR-121, `app/agent.py::_run_react_loop` |

## 5. Change management

| Control | Implementation |
|---|---|
| Every requirement traces to a test or eval fixture, and every test/fixture traces back to a requirement | `08-traceability/RTM.md` / `rtm.csv` |
| Defects (including security findings) are logged with severity, fix, and verification - not just fixed silently | `10-defects/Defect-Log.md` |
| A release requires UAT sign-off by a named Data Governance reviewer | `11-uat-and-signoff/UAT.md` |
| Known gaps are documented, not hidden | `09-test-execution/Execution-Summary.md` §3 lists exactly what has and hasn't been verified as of this build pass |

## 6. Known open items (as of this build pass)

Read `09-test-execution/Execution-Summary.md` and
`10-defects/Defect-Log.md` before treating this system as
production-ready. In short: the governance/plumbing layer (sections
1-3 above) has been directly verified against real code AND against a
real, disposable Postgres instance under the actual least-privilege
audit role (`tests/test_live_integration.py`); the judgment layer
(section 4) has a built and unit-tested framework, with its
underlying tool-level results now confirmed correct against live
data, but has not yet been run end-to-end against a live model in
this pass, and UAT (section 5) has not yet started.

Three defects were found and fixed during this build, all through
actually running the system rather than reading the code:

- **DEF-001** (critical): a SQL-identifier-injection path - the
  concrete example of why this system treats "looks read-only" and
  "is provably read-only" as different claims.
- **DEF-003** (critical): PK/FK detection silently returned nothing
  under the real least-privilege role, because the `information_schema`
  views used only expose constraints to a table's *owner* - invisible
  in any test that wasn't run as that exact role. This is the concrete
  example of why "passed my tests" and "passed under the actual
  production permission model" are different claims too.
- **DEF-004** (high): an ambiguous-type query parameter that only
  raised once a real Postgres connection executed it with a `NULL`
  argument.

All three are fixed, verified, and now covered by regression tests
that run automatically whenever a live database is configured
(`tests/test_live_integration.py`).
