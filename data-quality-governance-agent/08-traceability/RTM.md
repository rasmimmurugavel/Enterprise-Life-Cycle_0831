# Requirements Traceability Matrix (RTM)
## Data Quality & Governance Agent

| Field | Value |
|---|---|
| Document ID | RTM-DQGA-08 |
| Machine-readable version | `rtm.csv` |
| Traces from | `01-business-requirements/BRD.md`, `02-requirements/FRD-SRS.md`, `06-test-cases/`, `07-edge-cases/` |
| Traces to | `09-test-execution/Execution-Summary.md` |

Every Business Requirement traces forward to the FR/NFRs that
implement it, the test/edge cases that verify it, and (honestly)
its current execution status - see `rtm.csv` for the full table.

## How to read the "Status" column

This project has two test tracks (`04-test-strategy/Test-Strategy.md`
§1): **deterministic** (unit/integration, no LLM judgment) and
**eval** (real model calls against fixtures, scored). A live Postgres
instance became available partway through this build and was used to
run real integration tests (`tests/test_live_integration.py`) - which
is how DEF-003 and DEF-004 were found - but no `ANTHROPIC_API_KEY` was
ever available, so:

- Every deterministic-track claim in `rtm.csv` marked "Executed" was
  actually run during the build - either as pure unit tests, or (where
  noted "+ live Postgres integration") against a real, disposable
  Postgres instance under the actual least-privilege `dq_audit_reader`
  role - not asserted from reading the code. See
  `09-test-execution/Execution-Summary.md` for exactly what ran and
  what it showed, including two real defects (DEF-003, DEF-004) that
  only surfaced once real Postgres queries actually ran under that
  role.
- Every eval-track claim (BR-03/BR-04's *agent judgment* component,
  BR-08's live-model run) is still marked **blocked**, not "passed" -
  the eval framework, its fixtures, and the tool-level results they
  depend on are now verified correct against live data, but a real
  audit run against a real database
  scored by a real model call has not yet happened. This is flagged
  explicitly rather than glossed over, per this project's own
  principle (BR-05/BR-06: findings must be reproducible, not asserted).

## Coverage gaps (tracked, not silently dropped)

- **FR-132** (governance override persistence) is specified in the FRD
  and designed for in the UI (`app/app.py` has no override UI yet) -
  not implemented this pass. Tracked as DEF-002 in
  `10-defects/Defect-Log.md`.
- **NFR-203** (latency targets) has no automated test yet - would
  require a fixture at the stated scale (≤200 tables / ≤50 tables with
  ≤1M rows) which is heavier than the current fixture set. Tracked as
  a follow-up, not a defect (the requirement itself is aspirational
  for this phase, per Test-Plan §1 out-of-scope note on load testing).
- **EC-003** (self-referencing FK) and **EC-007** (naive timestamp
  staleness) have no dedicated fixture yet - documented in the edge
  case catalog as known gaps rather than assumed to work.

Full BR -> FR/NFR -> TC/EC -> Status mapping: `rtm.csv`.
