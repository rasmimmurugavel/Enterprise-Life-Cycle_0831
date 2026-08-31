# Test Plan
## Project: Loan Evaluator — Release 1.0

| Field | Value |
|---|---|
| Doc ID | TPLAN-LE-001 |
| Version | 1.0 |
| References | TSTRAT-LE-001 (approach), FRD-LE-001 (requirements) |

## 1. Scope of This Release

**Features to test** (maps to FRD-LE-001):

| Feature | Requirement IDs |
|---|---|
| DTI calculation & tiering | FR-101, FR-101a |
| LTV calculation & tiering | FR-102 |
| Credit score tiering | FR-103 |
| Employment stability assessment | FR-104 |
| Red flag detection | FR-105 |
| Risk level & recommendation aggregation | FR-106 |
| Conditions generation | FR-107 |
| Rationale / adverse-action reason codes | FR-108 |
| Audit logging | FR-109 |
| Configurable thresholds | FR-110 |
| Prohibited-factor exclusion | FR-111 |
| Performance, security, fairness, accessibility | NFR-201–212 |

**Features not tested this release:** ML-based scoring (not built — see gap
analysis), credit bureau integration internals (external system, contract
tested only), case management UI beyond the officer-facing recommendation
screen.

## 2. Test Levels Executed This Release

Unit, Integration, System/Functional, Regression (automated), Performance,
Security, Fairness/Disparate-Impact, Accessibility, UAT — per
TSTRAT-LE-001 §2.

## 3. Schedule (illustrative)

| Milestone | Target |
|---|---|
| Test case authoring complete, RTM baselined | Sprint 1 end |
| Unit + integration testing complete | Sprint 2 |
| System/functional + edge-case testing complete | Sprint 3 |
| Non-functional (perf/security/fairness/accessibility) testing | Sprint 3–4 |
| UAT | Sprint 4 |
| Go/no-go decision | Sprint 4 end |

## 4. Entry Criteria (this release)

- FRD-LE-001 approved and baselined.
- Test environment (QA) provisioned with the boundary-value synthetic data fixture set.
- Threshold config service deployed with the agreed v1.0 ruleset.

## 5. Exit Criteria (this release)

- Per TSTRAT-LE-001 §5, plus:
- Zero open S1/S2 defects.
- RTM (`08-traceability/RTM.md`) shows 100% FR/NFR coverage with a linked, passed test case.
- UAT sign-off obtained (`11-uat-and-signoff/UAT-Signoff.md`).

## 6. Suspension / Resumption Criteria

- **Suspend** testing if: the audit log store cannot be verified as
  writing a record for every evaluation (BR-10 is a hard gate), or if any
  test discovers the system can emit a final "Decline" (BR-11 violation).
- **Resume** once the defect is fixed, re-verified in isolation, and the
  affected suite is re-run in full (not just the failing case).

## 7. Resources

| Resource | Allocation |
|---|---|
| QA Engineers | 2 (functional + automation) |
| Dev support | 1 (test-environment/defect fixes) |
| Compliance reviewer | Part-time, fairness testing + UAT |
| Business/Underwriting SME | Part-time, UAT scenarios |
| Environment | QA + Staging per TSTRAT-LE-001 §7 |

## 8. Deliverables

- Test Cases (`06-test-cases/Test-Cases.md`, `test-cases.csv`)
- Edge Case Catalog (`07-edge-cases/Edge-Cases-and-Boundary-Analysis.md`)
- RTM (`08-traceability/RTM.md`, `rtm.csv`)
- Test Execution Summary Report (`09-test-execution/Test-Execution-Summary-Report.md`)
- Defect Log (`10-defects/Defect-Log-Template.md`)
- UAT Sign-off (`11-uat-and-signoff/UAT-Signoff.md`)

## 9. Risks & Contingencies

| Risk | Contingency |
|---|---|
| Synthetic data fixture set doesn't cover all boundary combinations | QA generates additional fixtures from the edge-case catalog before exit |
| Fairness testing surfaces a disparity outside the four-fifths guideline | Escalate to Compliance/Risk before go/no-go; may require threshold recalibration, not just a code fix |
| Config service unavailable in QA | Fallback to a pinned local ruleset version for functional testing; non-functional testing blocked until resolved |

## 10. Approval

| Role | Name | Approved | Date |
|---|---|---|---|
| QA Lead | | ☐ | |
| Engineering Lead | | ☐ | |
| Business Owner | | ☐ | |
| Compliance | | ☐ | |
