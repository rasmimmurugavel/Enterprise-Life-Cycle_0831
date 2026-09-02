# Business Requirements Document (BRD)
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | BRD-DQGA-01 |
| Status | Draft for review |
| Owner | Data Governance / Platform Engineering |
| Related docs | `02-requirements/FRD-SRS.md`, `03-design/HLD.md` |

## 1. Business context

Enterprises run critical decisions — lending, billing, compliance
reporting, ML training — on data sitting in PostgreSQL. Data quality
defects (nulls where required, duplicate keys, orphaned foreign keys,
stale records, unmasked PII sitting in the wrong column) are usually
found the expensive way: by an auditor, a regulator, or a downstream
failure, months after the defect was written.

Manual data quality review does not scale: a human analyst can audit a
handful of tables a day, cannot run continuously, and produces findings
in a format that does not survive an audit trail. Existing rule-based DQ
tools (Great Expectations, dbt tests, Deequ) catch what someone
remembered to write a rule for; they do not reason about unfamiliar
schemas, explain *why* a pattern is a defect, or adapt when the schema
changes.

## 2. Business objectives

| ID | Objective |
|---|---|
| BO-1 | Make routine data quality auditing continuous and autonomous instead of a periodic manual exercise. |
| BO-2 | Produce findings that are audit-ready: every finding traces to the exact table/column, the query that surfaced it, and a timestamp — reproducible by a human auditor without re-running the agent. |
| BO-3 | Never let PII reach an LLM provider, a log file, or a screen unmasked. Governance and quality auditing must not itself become a compliance risk. |
| BO-4 | Keep the agent's judgment measurable and regression-tested, so a prompt or model change cannot silently degrade audit quality. |
| BO-5 | Fit the enterprise's existing security posture: read-only database access, least privilege, full activity logging, no direct write path from the agent to production data. |

## 3. Business requirements

| ID | Requirement | Traces to objective |
|---|---|---|
| BR-01 | The system shall connect to a PostgreSQL database using a dedicated, least-privilege, read-only credential — never an admin or application-write credential. | BO-3, BO-5 |
| BR-02 | The system shall let an authorized user trigger a schema inspection and a full data quality audit from a web UI, on demand. | BO-1 |
| BR-03 | The system shall score data quality along standard governance dimensions (completeness, validity, uniqueness, consistency, timeliness) and produce a 0–100 scorecard per table and per database. | BO-1, BO-2 |
| BR-04 | The system shall detect columns that plausibly contain PII (names, emails, SSN/national ID patterns, phone numbers, card numbers) and flag them for governance review, without ever printing the raw values to the UI, an LLM prompt, or a log. | BO-3 |
| BR-05 | Every finding the system reports shall be traceable: which table/column, which query produced the evidence, what rule or reasoning flagged it, and when the audit ran. | BO-2 |
| BR-06 | Every action the agent takes against the database (every query, every tool call) shall be recorded in an append-only audit log, independent of whether the finding made it into the final report. | BO-2, BO-5 |
| BR-07 | The system shall enforce hard limits on what the agent can do: SELECT-only queries, a row cap per query, a statement timeout, and an optional schema allowlist — configurable, not bypassable by the agent's own reasoning. | BO-3, BO-5 |
| BR-08 | The system's judgment (what counts as a defect, how it's scored, how PII is classified) shall be defined as versioned, testable rubrics, and every release shall be evaluated against a fixed set of scenarios with known-correct answers before being considered production-ready. | BO-4 |
| BR-09 | The agent's tool surface (the specific database operations it is allowed to invoke) shall be implemented as a standalone MCP server, independently reusable by other MCP-compatible clients (Claude Code, Claude Desktop) beyond the Streamlit app. | BO-1, BO-5 |
| BR-10 | The system shall produce a downloadable, human-readable audit report (Markdown/PDF) suitable for handing to an auditor or compliance reviewer without further editing. | BO-2 |

## 4. Out of scope (this phase)

- Automatic remediation (the agent never writes/updates/deletes data).
- Multi-database federation in a single audit run (Phase 2 candidate).
- Real-time streaming quality monitoring (this phase is on-demand / scheduled batch).
- Non-Postgres engines (SQL Server, Snowflake, etc. — architecture is designed to allow it later, see HLD §7).

## 5. Stakeholders

| Role | Interest |
|---|---|
| Data Governance Lead | Defines what "quality" and "PII" mean for the org; sign-off on rubric weights and thresholds. |
| Security / InfoSec | Approves the read-only credential model, PII-masking design, audit logging. |
| Data Platform Engineering | Operates the MCP server, the Streamlit app, and the eval pipeline. |
| Compliance / Internal Audit | Consumes the audit reports; needs traceability and reproducibility. |
| End users (data stewards, analysts) | Trigger audits, read scorecards, action findings. |

## 6. Success criteria

- An authorized user can go from "click Run Audit" to a reviewed scorecard + downloadable report in under 5 minutes for a database of ≤ 50 tables.
- Zero instances, across the eval suite and in production audit logs, of raw PII values appearing in an LLM prompt, a UI screen, or a log line.
- 100% of reported findings are reproducible from the audit log alone (the exact query + result that produced them is recoverable).
- The eval rubric suite passes at ≥ the release threshold (see `12-eval-rubrics/`) before any prompt, tool, or model change ships.
