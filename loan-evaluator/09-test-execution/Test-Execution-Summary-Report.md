# Test Execution Summary Report — Template

| Field | Value |
|---|---|
| Doc ID | TEXEC-LE-001 |
| Cycle | *(e.g., Sprint 3 Regression, Release 1.0 RC1)* |
| Build / Version | *(e.g., v1.0.0-rc1, ruleset_version 2026.08.1)* |
| Environment | *(Dev / QA / Staging)* |
| Test Window | *(start – end date)* |
| Prepared by | QA Lead |

This is the reusable reporting shell referenced as a deliverable in
`05-test-plan/Test-Plan.md` §8. Fill in per cycle. A fully worked
illustrative example follows the blank template so the reporting format is
unambiguous — replace it with real numbers once execution begins.

---

## 1. Execution Summary

| Metric | Count |
|---|---|
| Total test cases planned | |
| Executed | |
| Passed | |
| Failed | |
| Blocked | |
| Not Run | |
| Pass rate (Passed / Executed) | |
| Requirement coverage (from RTM) | |

## 2. Results by Priority

| Priority | Total | Passed | Failed | Blocked | Exit criteria met? |
|---|---|---|---|---|---|
| P1 | | | | | |
| P2 | | | | | |
| P3 | | | | | |

## 3. Defect Summary

| Severity | Open | Fixed & Verified | Deferred |
|---|---|---|---|
| S1 – Critical | | | |
| S2 – High | | | |
| S3 – Medium | | | |
| S4 – Low | | | |

Link to full log: `10-defects/Defect-Log-Template.md`.

## 4. Non-Functional Results

| Area | Result | Target | Met? |
|---|---|---|---|
| Performance (p95 latency) | | < 2s @ 100 req/s (NFR-201) | |
| Fairness / adverse-impact ratio | | Four-fifths guideline (NFR-206) | |
| Security scan | | No High/Critical findings open | |
| Accessibility (if UI in scope) | | WCAG 2.1 AA | |

## 5. Risk Assessment & Go/No-Go Recommendation

*(QA's recommendation: Go / No-Go / Go with conditions, and why — tie
explicitly back to the exit criteria in the Test Plan, not just pass %.)*

## 6. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| QA Lead | | ☐ Go ☐ No-Go | |
| Engineering Lead | | ☐ Go ☐ No-Go | |
| Compliance | | ☐ Go ☐ No-Go | |
| Business Owner | | ☐ Go ☐ No-Go | |

---

## Appendix: Worked Illustrative Example (SAMPLE DATA — not a real run)

**Cycle:** Release 1.0 RC1 · **Build:** v1.0.0-rc1 · **Environment:** Staging

| Metric | Count |
|---|---|
| Total test cases planned | 47 (TC) + 27 (EC) = 74 |
| Executed | 74 |
| Passed | 71 |
| Failed | 2 |
| Blocked | 1 |
| Pass rate | 96% |
| Requirement coverage | 100% (per RTM) |

**Failures found (sample):**
- TC-022 (credit score 580 boundary) initially **failed**: implementation
  used `< 580` inclusive incorrectly and flagged 580 as red flag RF-4.
  → Logged as DEF-001 (S2), fixed, re-verified pass.
- EC-017 (bankruptcy exactly 7 years ago) **failed**: date math included
  the boundary day as "within 7 years" instead of excluding it.
  → Logged as DEF-002 (S2), fixed, re-verified pass.
- TC-041 (config threshold hot-reload) **blocked**: config service not
  yet deployed to Staging in this cycle; deferred to next cycle, not a
  product defect.

**Recommendation:** Go, conditional on DEF-001/DEF-002 fixes being
re-verified (done) and TC-041 being executed in the next cycle before
final release sign-off — consistent with the Test Plan's exit criteria
(`05-test-plan/Test-Plan.md` §5), since TC-041 covers a P1 requirement
(BR-12) and cannot simply be waived.
