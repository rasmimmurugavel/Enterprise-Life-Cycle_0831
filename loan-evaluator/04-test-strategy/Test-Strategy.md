# Test Strategy
## Project: Loan Evaluator

| Field | Value |
|---|---|
| Doc ID | TSTRAT-LE-001 |
| Version | 1.0 |
| Applies to | All releases of the Loan Evaluator service |
| Traces to | BRD-LE-001, FRD-LE-001 |

Note: the **Test Strategy** is program-level and mostly stable release to
release; the **Test Plan** (`05-test-plan/Test-Plan.md`) is release-specific
and references this document rather than repeating it.

## 1. Objectives

- Verify every functional requirement (FR-101–FR-111) produces correct,
  deterministic output (NFR-211) across normal, boundary, and negative
  inputs.
- Verify the system structurally cannot produce a prohibited outcome
  (auto-decline, use of prohibited factors) — these are compliance
  invariants, not ordinary bugs.
- Verify non-functional requirements: performance, security, auditability,
  fairness.
- Provide full bidirectional traceability from business requirement to
  test result (see `08-traceability/RTM.md`).

## 2. Test Levels & Scope

| Level | Scope | Owner |
|---|---|---|
| Unit | Each rule module (DTI, LTV, credit tier, employment, red flags) in isolation, all boundary values | Dev |
| Integration | Rule engine + config service + audit log store | Dev/QA |
| System / Functional | End-to-end evaluation via the public API against FR-101–FR-111 | QA |
| Regression | Full functional suite automated, run on every build | QA (automated) |
| Non-Functional | Performance, security, accessibility (UI), fairness/bias | QA + specialists |
| UAT | Business-scenario acceptance by Underwriting Ops & Compliance | Business + QA support |

## 3. Test Design Techniques

Because nearly every business rule is threshold-driven (DTI/LTV/credit-score
bands), test design leans heavily on:
- **Equivalence partitioning** — one representative case per tier (Low/Medium/High, each credit tier).
- **Boundary value analysis** — exact threshold, threshold ± 0.1, for every numeric cutoff in FRD-LE-001 (36.0/36.1, 43.0/43.1, 80.0/80.1, 95.0/95.1, 580/579, 600/599, 650/649, 700/699, 750/749).
- **Decision-table testing** — for the risk/recommendation aggregation matrix (FR-106), which combines multiple tiered inputs.
- **Negative/error-guessing testing** — malformed, missing, out-of-range, and prohibited-factor inputs (FR-111).
- **Combinatorial/pairwise testing** — for red-flag combinations (multiple simultaneous red flags) to confirm the aggregator still resolves to the correct, most-conservative outcome.

## 4. Risk-Based Prioritization

| Priority | Criteria | Example |
|---|---|---|
| P1 | Compliance invariants; wrong output changes a lending decision | BR-11 no-auto-decline; DTI/LTV boundary math |
| P2 | Core functional correctness | Red-flag detection, conditions generation |
| P3 | Usability / secondary output formatting | Rationale wording, non-boundary happy paths |

Test execution and defect triage prioritize P1 first; a P1 defect blocks
release regardless of overall pass rate.

## 5. Entry / Exit Criteria

**Entry (program-level):**
- FRD approved and baselined; test cases mapped to every FR/NFR before test execution begins.
- Test environment provisioned with masked/synthetic data (no real NPI below staging).

**Exit (program-level):**
- 100% of P1 test cases pass; ≥ 95% of P2; no open Severity-1/2 defects.
- RTM shows 100% requirement coverage.
- Fairness/disparate-impact test run completed with results reviewed by Compliance.
- Audit-log completeness verified (spot-check + automated check).

## 6. Non-Functional & Specialized Testing

| Type | Approach |
|---|---|
| Performance | Load test to NFR-201 targets (p95 < 2s @ 100 req/s) using k6/JMeter; soak test 4h+ for leaks. |
| Security | OWASP ZAP scan, RBAC verification, encryption-at-rest/in-transit checks, log-masking checks (NFR-203). |
| Fairness / Disparate Impact | Statistical parity / four-fifths-rule analysis across protected-class proxies on deidentified historical/synthetic data (NFR-206); run pre-release and quarterly in production. |
| Accessibility | WCAG 2.1 AA automated (axe-core) + manual screen-reader pass on any officer-facing UI. |
| Auditability | Verify every evaluation produces a matching, immutable audit record (FR-109) under normal load and under induced failure (e.g., store outage → evaluation must fail closed, never succeed without a log). |
| Resilience | Fault injection on config service / audit store dependencies; verify fail-closed behavior. |

## 7. Test Environments & Data

| Environment | Purpose | Data |
|---|---|---|
| Dev | Developer/unit testing | Synthetic, generated |
| QA | Functional/regression | Synthetic, boundary-value fixture set |
| Staging | Non-functional, UAT | Masked/deidentified production-shaped data |
| Production | Live | Real data; monitored, not "tested" against |

No real applicant NPI is used below Staging (NFR-209).

## 8. Tooling

| Purpose | Tooling |
|---|---|
| Test case & traceability management | TestRail/Jira Xray (or equivalent) |
| API/functional automation | REST-assured / Postman+Newman / Playwright API testing |
| Performance | k6 / JMeter |
| Security | OWASP ZAP, dependency/SCA scanning |
| Fairness testing | Statistical analysis notebook (e.g., AIF360/Fairlearn-style adverse-impact ratio calculation) |
| CI/CD gating | Pipeline runs unit + integration + regression suite on every merge; blocks merge on P1 failure |

## 9. Defect Management

| Severity | Definition | Response |
|---|---|---|
| S1 – Critical | Compliance invariant violated (e.g., auto-decline issued, prohibited factor used) | Immediate; blocks release |
| S2 – High | Wrong risk/recommendation for a valid input | Blocks release |
| S3 – Medium | Wrong condition/rationale text, non-blocking calc issue | Fix before next release |
| S4 – Low | Cosmetic, documentation | Backlog |

See `10-defects/Defect-Log-Template.md` for the tracking format.

## 10. Roles & Responsibilities (RACI, abbreviated)

| Activity | Dev | QA | Compliance | Business |
|---|---|---|---|---|
| Unit tests | R | C | — | — |
| Functional/system tests | C | R | I | I |
| Fairness/disparate-impact testing | C | R | A | I |
| UAT | I | C | C | R/A |
| Release go/no-go | C | C | A | A |

## 11. Metrics & Reporting

- Requirement coverage % (RTM)
- Pass/fail/blocked rate by priority
- Defect density and defect escape rate (defects found in UAT/prod vs. pre-release)
- Fairness/adverse-impact ratio trend
- See `09-test-execution/Test-Execution-Summary-Report.md` for the reporting template.
