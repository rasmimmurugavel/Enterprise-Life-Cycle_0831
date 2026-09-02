# Test Strategy
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | TS-DQGA-04 |
| Traces from | `02-requirements/FRD-SRS.md`, `03-design/HLD.md` |
| Traces to | `05-test-plan/Test-Plan.md`, `06-test-cases/`, `07-edge-cases/` |

## 1. Why this system needs a non-standard test strategy

Most of this system's *risk* is not "does the button work" - it's
"does the governance layer actually stop what it claims to stop, and
does the agent's judgment hold up when the model, the prompt, or the
schema changes." A conventional functional test suite covers the
first kind of risk; it does not cover the second. This strategy
therefore has two tracks that run differently and are owned
differently:

| Track | What it proves | How | Owner |
|---|---|---|---|
| **Deterministic** | The governance/plumbing guarantees hold: SELECT-only enforcement, row caps, PII masking, audit logging, schema allowlist, JSON Schema validation. | Unit + integration tests against real code paths (mocking only the network boundary - Postgres and Anthropic - where unavoidable). No LLM judgment involved; a test either passes or it doesn't. | Platform Engineering |
| **Judgment-based** | The agent still finds the right defects, at the right severity, without leaking PII, after a prompt/tool/model change. | The eval rubric suite (`12-eval-rubrics/`) - real model calls against fixed fixtures with known-correct answers, scored against a release gate. Not pass/fail per assertion; pass/fail per threshold. | Data Governance + Platform Engineering jointly |

Test cases in `06-test-cases/` map to the deterministic track. The
judgment-based track's "test cases" are `eval/fixtures/*/golden.json`
- deliberately not duplicated here as prose test cases, since the
golden files ARE the executable spec (see `12-eval-rubrics/Eval-Rubric-Spec.md`).

## 2. Test levels

| Level | Scope | Primary technique |
|---|---|---|
| Unit | Individual functions in `mcp_server/tools/*.py`, `app/agent.py`'s pure helpers, `eval/eval_runner.py`'s scoring functions | Direct function calls, no DB/network. Equivalence partitioning + boundary value analysis on inputs (row limits, empty results, malformed SQL). |
| Integration | MCP server tool calls against a real (disposable) Postgres; agent ↔ MCP client over the real stdio transport | `db/seed/*.sql` fixtures + docker-compose Postgres. Verifies wiring, not judgment - e.g. "does `check_referential_integrity` actually return the orphan count", not "does the agent decide to call it." |
| System / eval | The full agent loop against fixture databases, scored by rubric | `eval/eval_runner.py` - see `12-eval-rubrics/Eval-Rubric-Spec.md`. This is the level that exercises FR-121 (agent judgment) and NFR-204 (no PII reaches the LLM) end-to-end. |
| UAT | A Data Governance reviewer runs a real audit against a representative (non-production or sanitized) database via the Streamlit UI and signs off that the findings are trustworthy and the report is audit-ready. | Manual, see `11-uat-and-signoff/`. |

## 3. Techniques applied per requirement type

- **Governance/security requirements** (NFR-201/202/204/205/206/207):
  negative testing is primary - prove the forbidden thing is actually
  rejected (a `DELETE` statement, a schema outside the allowlist, a
  row count over the cap), not just that the allowed thing works.
- **Data quality computation** (FR-120/123): boundary value analysis
  on the defect fixtures (zero defects, exactly-at-threshold defects,
  every row a duplicate) plus the eval suite for whether the agent
  correctly interprets and reports them.
- **PII detection** (FR-130/131): equivalence partitioning across PII
  categories (email/phone/SSN/card/name/address/DOB/IP) x detection
  path (column-name hint vs. value-pattern-only) - the `pii_column`
  eval fixture exists specifically to cover the value-pattern-only
  case, since a naive implementation that only checks column names
  would pass every other fixture and still leak PII in production.
- **Audit trail** (FR-140/141/142, NFR-208): reproducibility testing -
  replay a logged query against the same fixture state and confirm
  matching results.
- **Concurrency/scale** (NFR-203): out of scope for this phase's test
  suite (single-user, on-demand tool); flagged as a gap for a future
  phase in `SDLC-GAP-ANALYSIS-AND-ENHANCEMENTS.md`-style follow-up if
  concurrent multi-user audits become a requirement.

## 4. Environments

| Environment | Purpose | Data |
|---|---|---|
| Unit test | Pure function tests, no external services | None / in-memory |
| Local dev (`docker-compose.yml`) | Integration tests, manual UI testing, eval suite during development | `db/seed/*.sql` fixtures only - never production data |
| CI | Automated gate on every PR: unit tests always; integration tests + eval suite when `mcp_server/`, `app/`, or `eval/` change | Same fixtures, spun up fresh per run |
| UAT | Governance sign-off before a release | A representative or sanitized dataset, per BRD out-of-scope note - never raw production PII without explicit authorization |

## 5. Entry / exit criteria

**Entry** (a change is ready for test): unit tests added/updated for
any new tool or governance rule; if the change touches `app/prompts.py`,
`mcp_server/`, or the model, at least one new/updated eval fixture
exists if the change targets a defect class not already covered.

**Exit** (a release candidate is shippable): all unit + integration
tests pass; `eval/eval_runner.py` reports `PASS` against the release
gate in `eval/rubrics.yaml`; UAT sign-off recorded in
`11-uat-and-signoff/`; no open `critical`/`high` defects in
`10-defects/`.

## 6. Roles

| Role | Responsibility |
|---|---|
| Platform Engineering | Owns deterministic-track tests, CI wiring, fixture/test-data maintenance |
| Data Governance | Owns golden.json ground truth, rubric weights/thresholds, PII category list, UAT sign-off |
| Security/InfoSec | Reviews the negative-test coverage for NFR-201/202/204-207 before each release |
