# Functional & Non-Functional Requirements (FRD/SRS)
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | FRD-DQGA-02 |
| Traces from | `01-business-requirements/BRD.md` |
| Traces to | `03-design/HLD.md`, `06-test-cases/`, `08-traceability/RTM.md` |

Numbering follows the repo-wide scheme: `FR-1xx` functional, `NFR-2xx`
non-functional. Every FR/NFR states an exact, testable rule.

## 1. Functional Requirements

### 1.1 Connectivity & configuration

| ID | Requirement | Traces to |
|---|---|---|
| FR-101 | The app shall read Postgres connection parameters (host, port, db, user, password, sslmode) from environment variables or `DATABASE_URL`, never hard-coded in source. | BR-01 |
| FR-102 | On startup, the MCP server shall verify the connected role has no `INSERT`/`UPDATE`/`DELETE`/`DDL` privileges on any table in scope; if the role has write privileges, the server shall log a governance warning and continue in enforced-read-only mode (see NFR-207). | BR-01, BR-07 |
| FR-103 | The app shall support an optional `DQ_ALLOWED_SCHEMAS` allowlist; when set, all tools shall refuse to operate outside the listed schemas. | BR-07 |

### 1.2 Schema inspection

| ID | Requirement | Traces to |
|---|---|---|
| FR-110 | The "Inspect Schema" action shall list all tables, columns, data types, nullability, primary keys, and foreign keys visible to the configured role. | BR-02 |
| FR-111 | Schema inspection shall run in ≤ 3 tool calls per schema regardless of table count (batch introspection via `information_schema`, not one call per table). | BR-02 |
| FR-112 | The UI shall render the schema as a browsable tree/table before any audit is run, so a user can scope the audit (select specific tables) instead of always running against the whole database. | BR-02 |

### 1.3 Data quality audit

| ID | Requirement | Traces to |
|---|---|---|
| FR-120 | The "Run Audit" action shall compute, per table, at minimum: null rate per column, duplicate/uniqueness violations on declared unique/PK columns, orphaned foreign keys, and stale-data indicators (max value of any timestamp/date column vs. now). | BR-03 |
| FR-121 | The agent shall use the Claude Sonnet model, in a bounded ReAct tool-use loop (hard cap: `DQ_MAX_TOOL_CALLS`, default 40 per audit run), to decide which additional checks to run beyond the fixed baseline in FR-120, based on what the schema and baseline results suggest (e.g., a `status` column with an unexpectedly high cardinality). | BR-01, BR-03 |
| FR-122 | Every finding shall include: table, column(s), rule/reasoning that triggered it, severity (`critical`/`high`/`medium`/`low`), evidence (aggregate counts/percentages — never raw row values containing PII), and the rubric dimension it maps to. | BR-05 |
| FR-123 | The system shall compute a 0–100 score per rubric dimension (completeness, validity, uniqueness, consistency, timeliness) per table, and roll these up into a per-table and per-database composite score using the weights in `eval/rubrics.yaml`. | BR-03 |
| FR-124 | A user shall be able to re-run an audit scoped to a subset of tables selected in the schema browser (FR-112), without re-auditing the whole database. | BR-02 |

### 1.4 PII detection & masking

| ID | Requirement | Traces to |
|---|---|---|
| FR-130 | Before any row-level sample or query result crosses the MCP tool boundary back to the agent, the system shall run PII detection (pattern-based: email, phone, SSN/national ID, card number, IP; plus column-name heuristics: `*_name`, `*email*`, `*ssn*`, `*dob*`, etc.) and mask detected values (e.g. `j***@***.com`) before they enter the LLM context. | BR-04 |
| FR-131 | The system shall flag columns with a PII-detection hit rate above a configurable threshold (default 5% of sampled rows) as "likely PII" in the report, listing the column and detected category, never the raw value. | BR-04 |
| FR-132 | A governance reviewer shall be able to override a PII classification (mark false positive / confirm) via the UI; overrides shall be persisted and reflected in future audits of the same column. | BR-04 |

### 1.5 Audit trail & reporting

| ID | Requirement | Traces to |
|---|---|---|
| FR-140 | Every MCP tool invocation (tool name, arguments, timestamp, caller, row count returned, execution time) shall be appended to a JSONL audit log before the result is returned to the agent. | BR-06 |
| FR-141 | The audit log shall be append-only from the app's perspective (the app never opens it for writing except append mode) and shall not itself contain masked-out raw PII. | BR-06 |
| FR-142 | The UI shall provide an "Audit Log" view, filterable by time range and tool name, showing exactly what the agent did during any given run. | BR-06 |
| FR-143 | The system shall generate a downloadable Markdown report per audit run containing: run metadata (timestamp, scope, model, rubric version), the scorecard, all findings grouped by severity, and a governance summary (PII columns detected, overrides applied). | BR-10 |

### 1.6 MCP server reusability

| ID | Requirement | Traces to |
|---|---|---|
| FR-150 | The Postgres tools (schema inspection, read-only query, profiling, PII scan, audit-log read) shall be implemented as a standalone MCP server process, launchable independently of Streamlit (stdio transport), so Claude Code or Claude Desktop can attach to the same tools. | BR-09 |
| FR-151 | The MCP server shall declare each tool's input schema (JSON Schema) and a human-readable description sufficient for a general-purpose MCP client to use it correctly without out-of-band documentation. | BR-09 |

## 2. Non-Functional Requirements

| ID | Requirement | Traces to |
|---|---|---|
| NFR-201 | **Read-only enforcement.** The `run_readonly_query` tool shall reject any statement that is not a single `SELECT`/`WITH ... SELECT` via AST-level parsing (not string matching), and shall run every query inside a transaction explicitly set `READ ONLY` with `SET LOCAL statement_timeout`. | BR-07 |
| NFR-202 | **Row cap.** No tool shall return more than `DQ_MAX_ROWS` (default 500) rows to the agent in a single call; aggregate queries (counts, percentages) are exempt from the cap but must themselves be bounded (`GROUP BY` cardinality capped). | BR-07 |
| NFR-203 | **Latency.** Schema inspection (FR-110) shall complete in ≤ 5s for a database with ≤ 200 tables. A full baseline audit (FR-120) shall complete in ≤ 60s for a database with ≤ 50 tables and ≤ 1M rows per table (via `information_schema`/statistics-based estimation, not full table scans, where possible). |
| NFR-204 | **No PII in LLM context.** No unmasked PII value shall ever be included in a prompt sent to the Anthropic API. This is enforced at the tool layer (FR-130), not the prompt layer, and is covered by a dedicated eval rubric (`12-eval-rubrics/`) that must pass before release. | BR-03, BO-3 |
| NFR-205 | **Secrets handling.** Database credentials and the Anthropic API key shall never be logged, echoed in the UI, or included in the audit log or the downloadable report. | BR-01 |
| NFR-206 | **Least privilege.** Documented provisioning (see `db/README.md`) shall grant the audit role `CONNECT`, `USAGE` on allowed schemas, and `SELECT` only — no `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`/DDL. | BR-01 |
| NFR-207 | **Defense in depth.** Even if the configured role has broader privileges than intended (FR-102), the application layer shall independently block any non-SELECT operation — privilege misconfiguration on the DB side must not become a write path. | BR-07 |
| NFR-208 | **Reproducibility.** Given the same audit-log entries, a human shall be able to re-execute the same queries against the same database state and get matching results — no tool may depend on non-deterministic agent state beyond what's in the log. | BR-06 |
| NFR-209 | **Observability.** The Streamlit UI shall show live progress (which tool is executing) during a long-running audit, not just a spinner, so a user can see the agent is not stalled. |
| NFR-210 | **Portability.** The MCP server's database access layer shall be isolated behind an interface (`mcp_server/tools/db.py`) such that adding a second engine (e.g. SQL Server) does not require changes to the agent, the UI, or the eval framework. | Out of scope note (BRD §4) |
| NFR-211 | **Testability.** Every MCP tool shall have unit tests using a disposable Postgres instance (docker-compose) with seeded fixtures representing each defect class the rubric scores. | BR-08 |
| NFR-212 | **Model portability.** The agent's model identifier shall be configurable (`ANTHROPIC_MODEL`), defaulting to the latest generally-available Claude Sonnet model, without code changes required to point at a different Claude model. |

## 3. Assumptions & constraints

- The Postgres instance is reachable from wherever the Streamlit app / MCP server runs (network/VPC access is an infra prerequisite, not built by this app).
- `ANTHROPIC_API_KEY` is provisioned via the enterprise's standard secrets manager in production; `.env` is for local dev only.
- Rubric weights and PII patterns are business decisions owned by Data Governance (BRD §5) and are configuration, not hard-coded logic.
