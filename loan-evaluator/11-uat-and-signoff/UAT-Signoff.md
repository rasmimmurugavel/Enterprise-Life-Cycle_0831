# User Acceptance Testing (UAT) & Sign-off — Loan Evaluator

| Field | Value |
|---|---|
| Doc ID | UAT-LE-001 |
| Participants | Underwriting Ops (business), Compliance, QA (facilitator) |

UAT validates the system from a **business scenario** perspective —
distinct from the technical test cases in `06-test-cases/Test-Cases.md`.
Scenarios are written in business language and executed by actual
underwriters/loan officers against Staging with masked, production-shaped
data.

## 1. UAT Scope

- End-to-end evaluation of a representative sample of real (deidentified)
  historical applications across all three loan types, spanning the full
  outcome spectrum (Approve / Approve with Conditions / Refer).
- Officer review of rationale/conditions text for clarity and usefulness
  in a live workflow — not just correctness.
- Compliance review of a sample of adverse-action-eligible outputs for
  ECOA/Reg B adequacy.

## 2. Acceptance Criteria

- 100% of UAT scenarios produce a recommendation the underwriter agrees
  is *reasonable* given the file (not necessarily identical to what they'd
  have decided manually — but explainable and defensible).
- Compliance confirms rationale text is adverse-action-notice-ready for
  every non-Approve outcome sampled.
- No P1/P2 defects open at UAT start (per Test Plan exit criteria).
- Underwriters confirm the tool measurably reduces time spent on
  clear-cut (Low risk) files, supporting BO-1/BO-4 in the BRD.

## 3. UAT Scenarios (business-level, sample set)

| Scenario ID | Business Scenario | Expected Business Outcome |
|---|---|---|
| UAT-01 | First-time homebuyer, strong credit, 10% down payment | Approve with Conditions (PMI), officer agrees rationale is clear |
| UAT-02 | Self-employed applicant, 2 years tax returns provided | Stable employment assessment; officer confirms doc requirement matches policy |
| UAT-03 | Applicant with bankruptcy discharged 4 years ago | Referred for manual underwriting; officer confirms this matches current manual practice |
| UAT-04 | Auto loan, thin credit file (no score) | Referred for manual underwriting; officer agrees this is the right conservative outcome |
| UAT-05 | Strong file across the board (Low/Low/Excellent) | Approve, no conditions; officer confirms no manual review would have added value |
| UAT-06 | Joint application where co-borrower carries the risk | Officer confirms rationale correctly attributes the driving factor to the co-borrower |

## 4. Sign-off

| Role | Name | Accepted | Date | Notes |
|---|---|---|---|---|
| Head of Underwriting Ops | | ☐ | | |
| Compliance Officer | | ☐ | | |
| QA Lead (facilitator) | | ☐ | | |

UAT sign-off, together with the exit criteria in
`05-test-plan/Test-Plan.md` §5 and a clean
`09-test-execution/Test-Execution-Summary-Report.md`, is the release
go/no-go gate.
