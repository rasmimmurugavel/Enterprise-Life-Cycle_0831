# UAT & Sign-off
## Data Quality & Governance Agent - Initial Build

| Field | Value |
|---|---|
| Document ID | UAT-DQGA-11 |
| Traces from | `05-test-plan/Test-Plan.md`, `09-test-execution/Execution-Summary.md` |
| Status | **Not started** - see §1 |

## 1. Status

UAT has not yet been performed. It requires a completed, real audit
run (real Postgres, real `ANTHROPIC_API_KEY`) for a Data Governance
reviewer to assess - neither was available during this build pass
(see `09-test-execution/Execution-Summary.md` §3). This document
records the planned UAT scenarios and sign-off criteria so that
running UAT is the *next* concrete step, not an undefined one.

## 2. UAT scenarios (to be executed against a real environment)

| ID | Scenario | Pass criteria |
|---|---|---|
| UAT-01 | Reviewer connects the app to a representative (non-production or sanitized) database and runs **Inspect Schema** | Schema tree matches the reviewer's own knowledge of the database; no data values are read (BR-02) |
| UAT-02 | Reviewer runs a full **Run Audit** against 3-5 tables they know well | Every reported finding is one the reviewer agrees is real; scorecard direction (which tables are worse) matches their own judgment |
| UAT-03 | Reviewer inspects a table they know contains PII | The PII column(s) are flagged in the governance summary; no raw PII value appears anywhere in the UI, the audit log, or the downloaded report |
| UAT-04 | Reviewer downloads the Markdown report and reviews it without the live UI open | Report is self-contained and readable as a standalone artifact suitable for an external auditor (BR-10, FR-143) |
| UAT-05 | Reviewer opens the Audit Log tab and picks one finding from UAT-02 | The exact query and result that produced that finding is recoverable from the log alone (BR-06, NFR-208) |
| UAT-06 | Reviewer deliberately runs the audit with a tool-call budget too small to finish | `tables_not_audited` is populated and the UI clearly says the audit is incomplete, rather than presenting partial results as if complete (FR-121) |

## 3. Sign-off criteria

UAT passes when a named Data Governance reviewer confirms, in writing
(recorded below), that:

1. All six scenarios in §2 behaved as specified.
2. `eval/eval_runner.py` reports `PASS` against the release gate in
   `eval/rubrics.yaml` (see `12-eval-rubrics/Eval-Rubric-Spec.md` §6)
   for the same model/prompt version being signed off.
3. No open `critical`/`high` defect exists in `10-defects/Defect-Log.md`.
4. The reviewer is satisfied the tool's judgment (severity assignment,
   what counts as a defect) is usable as-is or has documented,
   acceptable limitations.

## 4. Sign-off record

| Reviewer | Role | Date | Decision | Notes |
|---|---|---|---|---|
| _(pending)_ | Data Governance Lead | _(pending)_ | _(pending)_ | UAT not yet started - see §1 |

This table is the durable record once UAT runs; do not backfill it
with an assumed or simulated result.
