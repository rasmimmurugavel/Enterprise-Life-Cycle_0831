# Defect Log — Template

| Field | Value |
|---|---|
| Doc ID | DEF-LOG-LE-001 |
| Severity scale | Defined in `04-test-strategy/Test-Strategy.md` §9 (S1 Critical / S2 High / S3 Medium / S4 Low) |

| Defect ID | Title | Severity | Priority | Related TC/EC | Related Req | Status | Root Cause | Fix Version | Reported | Verified |
|---|---|---|---|---|---|---|---|---|---|---|
| DEF-001 | Credit score 580 incorrectly flagged as RF-4 red flag (boundary off-by-one) | S2 | P1 | TC-022 | FR-103, FR-105 | Closed | Comparison used `<= 580` instead of `< 580` | v1.0.0-rc2 | 2026-XX-XX | 2026-XX-XX |
| DEF-002 | Bankruptcy discharge exactly 7 years ago incorrectly counted as within RF-1 window | S2 | P1 | EC-017 | FR-105 | Closed | Date-diff comparison used `<=` instead of `<` on the 7-year window | v1.0.0-rc2 | 2026-XX-XX | 2026-XX-XX |
| *(add rows as discovered)* | | | | | | | | | | |

**Status values:** New → Triaged → In Progress → Fixed → Verified/Closed
(or Deferred / Won't Fix, with sign-off from QA Lead + Business Owner).

**Escalation rule:** any S1 defect (compliance invariant violated — e.g.,
an auto-decline is issued, a prohibited factor influences output, or an
evaluation completes without an audit record) is reported to Compliance
and Engineering Lead immediately, not just logged — see
`04-test-strategy/Test-Strategy.md` §9 and the Test Plan's suspension
criteria (`05-test-plan/Test-Plan.md` §6).
