# Test Plan - Release v1.0
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | TP-DQGA-05 |
| Traces from | `04-test-strategy/Test-Strategy.md` |
| Traces to | `06-test-cases/`, `08-traceability/RTM.md`, `09-test-execution/` |
| Release scope | Initial build: MCP server, agent engine, Streamlit UI, eval rubric framework (steps 1-5 of the build) |

## 1. Scope

**In scope for this test plan:**
- Every FR/NFR in `02-requirements/FRD-SRS.md`.
- The four eval fixtures in `eval/fixtures/` and the release gate in
  `eval/rubrics.yaml`.
- The Streamlit UI's three actions (Inspect Schema, Run Audit, Audit
  Log) as exercised manually against a live browser (see
  `09-test-execution/Execution-Summary.md` for what was actually run
  during the build, vs. what remains for a full pre-release pass).

**Out of scope for this release:**
- Multi-database federation, non-Postgres engines, real-time streaming
  monitoring, and remediation - all explicitly out of scope per BRD §4.
- Load/concurrency testing (NFR-203 latency targets are checked at a
  single-user level only this release).

## 2. Test items and features

| Feature | Test case IDs | Eval fixture(s) |
|---|---|---|
| Connectivity & config (FR-101/102/103) | TC-001 - TC-006 | - |
| Schema inspection (FR-110/111/112) | TC-010 - TC-014 | - |
| Read-only query enforcement (NFR-201/202) | TC-020 - TC-030 | - |
| Data quality audit baseline (FR-120/123) | TC-040 - TC-048 | `nulls_and_dupes`, `orphaned_fk`, `stale_data` |
| PII detection & masking (FR-130/131/132, NFR-204) | TC-050 - TC-058 | `pii_column` |
| Audit trail & reporting (FR-140-143, NFR-205/208) | TC-060 - TC-066 | all fixtures (transcript leak check) |
| MCP server reusability (FR-150/151) | TC-070 - TC-072 | - |
| Streamlit UI | TC-080 - TC-088 | - |

## 3. Test approach by feature (summary - full cases in `06-test-cases/`)

- **Connectivity**: boundary/negative - missing env vars, malformed
  `DATABASE_URL`, a role with unexpected write privileges (FR-102).
- **Read-only enforcement**: negative-heavy - every SQL statement type
  the AST guard must reject (see `07-edge-cases/Edge-Case-Catalog.md`
  for the specific adversarial SQL strings, e.g. DML hidden inside a
  CTE).
- **Audit baseline**: boundary value analysis on defect counts (0, 1,
  "all rows", exactly-at-threshold) using the seeded fixtures.
- **PII**: equivalence classes across detection path (name-hint vs.
  value-pattern-only) and category; the release gate's
  `max_pii_leak_incidents: 0` is itself a test assertion, not just a
  metric.

## 4. Test data

All test data is synthetic, generated in `db/seed/*.sql` specifically
for this suite - no production or real customer data is used at any
test level (BRD §4 / NFR scope). PII-shaped values use `.test` email
domains and clearly-fake phone numbers by convention.

## 5. Schedule (illustrative - actual dates tracked in project management, not this doc)

| Milestone | Depends on |
|---|---|
| Unit tests green in CI | Each code PR |
| Integration tests green (docker-compose Postgres) | `mcp_server/` stable |
| Eval suite passes release gate | `app/prompts.py` + `mcp_server/` stable |
| UAT sign-off | Eval suite passing + a Data Governance reviewer available |
| Release | UAT sign-off + no open critical/high defects |

## 6. Risks to the test plan itself

| Risk | Mitigation |
|---|---|
| No live Postgres/Anthropic credentials in a given environment (e.g. this build's sandbox) blocks integration/eval execution | Deterministic-track logic is still fully unit-testable without either (see `09-test-execution/Execution-Summary.md` for what was verified this way); integration/eval execution is tracked as a follow-up gate before the first real release, not silently skipped. |
| Eval suite cost (real API calls) discourages running it often | Deterministic tests run on every PR; eval suite runs on changes to `app/prompts.py`/`mcp_server/`/model, per Test-Strategy §6, not on every unrelated PR. |
| Golden.json drift from evolving business definitions of "quality" | Golden files are owned/reviewed by Data Governance (Test-Strategy §6), versioned alongside `rubrics.yaml`. |
