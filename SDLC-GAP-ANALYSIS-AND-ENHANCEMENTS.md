# SDLC Gap Analysis & Enhancements

Everything you asked for — BRD → test strategy → test plan → test cases →
traceability → edge cases → results — is now built out in this repo for
the Loan Evaluator example. That covers the **requirements-through-QA
spine** of the SDLC well. What's below is what a spine alone doesn't cover:
the phases around it that real programs get audited on, and a few
genuinely newer practices worth layering in. Organized by how much it
matters for a lending system specifically.

## 1. Structural gaps in a "BRD → test cases" lifecycle

These are missing regardless of domain — a requirements/QA chain isn't a
full SDLC without them:

| Gap | Why it matters | Where it'd live in this repo |
|---|---|---|
| **Design phase** (HLD/LLD) | Test cases implicitly assume an architecture; without a design doc, "expected result" has nothing to be verified against except the requirement text itself | Added: `03-design/HLD-Loan-Evaluator.md` |
| **Release / deployment plan** | How does this actually go to production — rollout sequence, feature flags, rollback plan, migration steps? | Not yet in this repo — add a `12-release-management/` folder: deployment runbook, rollback criteria, canary/phased-rollout plan |
| **Post-release monitoring & production validation** | Testing that stops at UAT sign-off misses the highest-signal environment: production itself | Add a `13-production-monitoring/` folder: SLO dashboards, synthetic-transaction smoke tests, alerting thresholds, on-call runbook |
| **Change management / CAB process** | Who approves a threshold change (BR-12) after go-live, and how is that different from a code change? | Reference NFR-208's two-person approval workflow; add a lightweight change-request template |
| **Retrospective / continuous improvement loop** | Without this, defects found in production never feed back into the BRD or test strategy — the "lifecycle" stops being a cycle | Add a short post-release retro template that explicitly asks "which of these defects should have been an edge case we already had?" |
| **Documentation & training / runbooks for end users** | Underwriters need more than a UAT session to adopt the tool day-to-day | Add a `14-training-and-runbooks/` folder |

## 2. Lending-domain-specific gaps (the ones that matter most here)

Because Loan Evaluator makes automated recommendations about credit, these
aren't "nice to have" — regulators specifically look for them, and
several are already reflected as requirements (BR-11, BR-13, NFR-205,
NFR-206) but need dedicated lifecycle artifacts, not just test cases:

| Gap | Why it matters |
|---|---|
| **Model/rules governance program** | Even a deterministic rules engine (not ML) needs a documented, versioned, approved change-control process for thresholds — this is closer to "model risk management" (SR 11-7-style) than ordinary software change control, because a threshold change directly changes who gets approved. |
| **Fair-lending / disparate-impact testing as an ongoing program, not a one-time test case** | TC-047 gets you a point-in-time check. Regulators expect *periodic, statistically rigorous* monitoring against real (deidentified) outcome data, with a defined escalation path if the four-fifths ratio drifts — this needs an owner and a cadence, not just a test ID. |
| **Adverse-action notice generation & delivery testing** | This repo tests that `rationale[]`/reason codes are *produced* (FR-108); it doesn't yet test the downstream notice-generation and delivery path end-to-end, which is where ECOA timing requirements (30 days) actually bite. |
| **Data lineage & permissible-use testing (FCRA)** | Verify credit data is only used for the permissible purpose it was pulled for, and that it isn't retained/reused beyond that purpose. |
| **Explainability audit trail for examiners** | NFR-205/FR-108 give you explainability at the API level; regulators will also want a report generator that reconstructs "why did applicant X get outcome Y" from the audit log months later without re-running code. |

## 3. Non-functional and operational gaps worth calling out explicitly

The FRD already has NFR-201–212, but a few categories are easy to
under-invest in even when they're "in scope":

- **Disaster recovery / business continuity** — RTO/RPO targets for the
  audit log store specifically (it has a 7-year regulatory retention
  requirement — losing it is a compliance incident, not just downtime).
- **Data retention & deletion policy** — GLBA/state privacy law may
  require deletion paths that conflict with the 7-year audit retention
  requirement for *decision* records vs. raw applicant NPI; these need to
  be reconciled explicitly, not left implicit.
- **Capacity planning beyond NFR-201's steady-state number** — seasonal
  spikes (e.g., mortgage rate drops) can be 5–10x normal volume.
- **Test data management as its own discipline** — synthetic data
  generation that actually produces every boundary combination in
  `07-edge-cases/`, with PII masking guaranteed by construction rather
  than by policy.

## 4. Newer practices worth adding (beyond "classic" SDLC)

These aren't required to call the lifecycle complete, but they're where
mature teams are investing now, and they map cleanly onto what's already
built here:

| Practice | How it'd plug in here |
|---|---|
| **Shift-left, requirement-linked test generation** | Since every FR here already states exact numeric thresholds, test cases for new boundaries can be generated (and kept in sync) programmatically/with LLM assistance directly from the FRD table — worth automating so `06-test-cases` never drifts from `02-requirements`. |
| **Property-based / metamorphic testing** | Instead of only fixed boundary values, assert invariants that must always hold — e.g., "increasing `credit_score` while holding everything else constant never worsens `risk_level`" (monotonicity), or "the output is always one of exactly 3 recommendation values" (BR-11 as a property, not just a test case). This catches classes of bugs boundary-value testing alone misses. |
| **Contract testing** | For the upstream credit-bureau/employment-verification integrations this system depends on — verifies the input contract (§1 of the FRD) doesn't silently drift without a full integration-test run. |
| **Policy-as-code for compliance rules** | Encode BR-11 (no auto-decline), BR-13 (no prohibited factors), and the red-flag ceiling rule (FR-105) as machine-checked policies that run in CI against every build — turning compliance invariants into a hard gate, not just a manual test case someone might skip. |
| **Chaos/fault-injection testing** | EC-022/EC-023 (audit store or config service unavailable) are written as test cases here; running them as automated, scheduled fault-injection exercises in staging (not just a one-time manual test) catches regressions in fail-closed behavior over time. |
| **Continuous fairness monitoring in production** | Move NFR-206 from "a test we run before release" to a dashboard that's watched continuously against live (deidentified) outcomes, with automatic alerting on drift — this is the single highest-value modern addition for a lending system specifically. |
| **AI-assisted defect triage / root-cause clustering** | If defect volume grows, clustering defects by root cause (as loosely modeled in `10-defects/Defect-Log-Template.md`) helps spot systemic issues (e.g., "we keep getting boundary off-by-ones on date math" — see DEF-002) faster than reading a flat log. |

## 5. Suggested next steps, roughly in priority order

1. Wire the RTM (`08-traceability/RTM.md`) into CI so a new FR without a
   linked TC fails the build, not just a manual review step.
2. Stand up the fairness/disparate-impact monitoring as a recurring job,
   not a pre-release test case (§2, §4 above) — this is the biggest
   compliance-risk gap relative to effort.
3. Add the release-management and production-monitoring folders (§1) —
   right now the lifecycle stops at UAT sign-off, which is the most
   common place real programs quietly under-invest.
4. Turn BR-11/BR-13 into policy-as-code CI gates (§4) so the two hardest
   compliance invariants can't regress silently.
5. Only after the above: consider whether any component (e.g., credit
   tiering) becomes a genuine ML model — if so, this whole gap analysis
   gets a second pass for model risk management, drift monitoring, and
   explainability tooling specific to ML, which a rules engine doesn't
   need today.
