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
**eval** (real model calls against fixtures, scored). The build
environment for this initial pass had neither a live Postgres instance
nor an `ANTHROPIC_API_KEY` configured, so:

- Every deterministic-track claim in `rtm.csv` marked "Executed" was
  actually run during the build - as standalone verification scripts
  against the real code (not asserted from reading the code) - see
  `09-test-execution/Execution-Summary.md` for exactly what ran and
  what it showed.
- Every eval-track claim (BR-03, BR-04's judgment component, BR-08) is
  marked **blocked**, not "passed" - the eval framework and its
  fixtures are built and the scoring logic is unit-tested against
  synthetic inputs, but a real audit run against a real database
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
