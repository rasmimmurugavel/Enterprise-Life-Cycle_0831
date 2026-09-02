# Test Cases
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | TC-DQGA-06 |
| Machine-readable version | `test-cases.csv` (same IDs, one row per case) |
| Traces from | `02-requirements/FRD-SRS.md`, `05-test-plan/Test-Plan.md` |
| Traces to | `08-traceability/RTM.md`, `09-test-execution/Execution-Summary.md` |

Type legend: **POS** positive/happy-path, **NEG** negative (proves a
forbidden thing is rejected), **BND** boundary value, **NFR**
non-functional property check.

These are the deterministic-track cases (see
`04-test-strategy/Test-Strategy.md` §1) - they test plumbing and
guardrails, not agent judgment. Agent judgment is tested by the eval
rubric suite (`12-eval-rubrics/Eval-Rubric-Spec.md`); its "test cases"
are `eval/fixtures/*/golden.json`, not duplicated here.

## Connectivity & configuration (FR-101/102/103)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-001 | Connect via discrete PG* env vars | POS | P1 |
| TC-002 | Connect via DATABASE_URL override | POS | P1 |
| TC-003 | Role privilege check surfaces a warning, not a crash | NEG | P2 |
| TC-004 | Schema allowlist narrows list_schemas | POS | P1 |
| TC-005 | Empty allowlist returns all visible schemas | POS | P2 |
| TC-006 | inspect_schema rejects a schema outside the allowlist | NEG | P1 |

## Schema inspection (FR-110/111/112)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-010 | inspect_schema returns full column/PK/FK metadata | POS | P1 |
| TC-011 | inspect_schema issues exactly one query per schema | NFR | P2 |
| TC-012 | UI renders schema as browsable tree before audit | POS | P2 |
| TC-013 | inspect_schema on empty schema | BND | P3 |
| TC-014 | inspect_schema truncation flag on very wide schema | BND | P3 |

## Read-only query enforcement (NFR-201/202)

The AST-level SELECT-only guard (`mcp_server/tools/db.py::assert_select_only`)
is the single highest-value negative-test surface in this system -
every case here was also exercised as a standalone script during the
build (see `09-test-execution/Execution-Summary.md`).

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-020 | SELECT statement accepted | POS | P1 |
| TC-021 | WITH...SELECT accepted | POS | P1 |
| TC-022 | Bare DELETE rejected | NEG | P1 |
| TC-023 | Bare INSERT rejected | NEG | P1 |
| TC-024 | DDL (DROP TABLE) rejected | NEG | P1 |
| TC-025 | DML hidden inside a CTE rejected | NEG | P1 |
| TC-026 | Multi-statement (stacked query) rejected | NEG | P1 |
| TC-027 | Row cap truncates and flags | BND | P1 |
| TC-028 | Result exactly at row cap not flagged truncated | BND | P2 |
| TC-029 | Statement timeout enforced | NEG | P2 |
| TC-030 | Unparseable SQL rejected | NEG | P2 |

## Data quality audit baseline (FR-120/121/122/123/124)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-040 | profile_table computes null rate correctly | POS | P1 |
| TC-041 | check_duplicates finds duplicate key | POS | P1 |
| TC-042 | check_referential_integrity finds orphan | POS | P1 |
| TC-043 | check_referential_integrity finds zero orphans on clean data | POS | P2 |
| TC-044 | Composite score reflects severity of defects found | POS | P1 |
| TC-045 | Agent runs baseline tools without being told which ones | POS | P1 |
| TC-046 | Audit scoped to selected tables only queries those tables | POS | P2 |
| TC-047 | Every finding cites table/column/evidence | POS | P1 |
| TC-048 | Tool-call budget exhaustion produces partial-but-honest result | BND | P1 |

## PII detection & masking (FR-130/131/132, NFR-204)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-050 | Email column masked in query output | POS | P1 |
| TC-051 | Column-name-hinted PII column flagged | POS | P1 |
| TC-052 | Value-pattern-only PII column flagged (no name hint) | POS | P1 |
| TC-053 | Column below hit-rate threshold not flagged | NEG | P2 |
| TC-054 | No raw PII in tool-call audit log | NEG | P1 |
| TC-055 | No raw PII in agent's final findings JSON | NEG | P1 |
| TC-056 | Governance override persists and suppresses future flag | POS | P3 |
| TC-057 | detect_pii never returns sampled raw values | NEG | P1 |
| TC-058 | All documented PII categories individually detectable | POS | P2 |

## Audit trail & reporting (FR-140-143, NFR-205/208)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-060 | Every tool call appends exactly one audit log entry | POS | P1 |
| TC-061 | Failed tool call still logged with status=error | POS | P1 |
| TC-062 | Audit log file opened only in append mode | NFR | P2 |
| TC-063 | Audit Log UI filters by tool name | POS | P2 |
| TC-064 | Downloaded report is self-contained | POS | P1 |
| TC-065 | No secrets in audit log or report | NEG | P1 |
| TC-066 | Logged query is reproducible | POS | P2 |

## MCP server reusability (FR-150/151)

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-070 | MCP server runs standalone outside Streamlit | POS | P1 |
| TC-071 | Every tool has a non-empty description and valid input schema | NFR | P2 |
| TC-072 | Same server usable from a generic MCP client | POS | P2 |

## Streamlit UI

| TC | Title | Type | Pri |
|---|---|---|---|
| TC-080 | App loads without error with no .env configured | POS | P1 |
| TC-081 | Inspect Schema button triggers agent call and renders result | POS | P1 |
| TC-082 | Inspect Schema failure surfaces a readable error | NEG | P1 |
| TC-083 | Run Audit scoped to multiselect table list | POS | P2 |
| TC-084 | Tool-call budget input bounds respected | BND | P3 |
| TC-085 | Scorecard renders gauge + dimension chart + table chart | POS | P2 |
| TC-086 | Findings list sorted by severity descending | POS | P2 |
| TC-087 | Download report button produces valid Markdown | POS | P2 |
| TC-088 | Audit Log tab reads live log file independent of session state | POS | P1 |

Full Test Data / Steps / Expected Result for every case: see
`test-cases.csv`.
