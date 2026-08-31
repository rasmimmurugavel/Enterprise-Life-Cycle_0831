# Business Requirements Document (BRD)
## Project: Loan Evaluator — Automated Underwriting Pre-Screening Engine

| Field | Value |
|---|---|
| Doc ID | BRD-LE-001 |
| Version | 1.0 |
| Status | Draft for Review |
| Author | Business Analysis |
| Business Owner | VP, Underwriting Operations |
| Related Docs | FRD-LE-001, HLD-LE-001, TSTRAT-LE-001, TPLAN-LE-001 |

---

## 1. Executive Summary

Loan officers currently perform a fully manual first pass on every incoming
application (mortgage, auto, personal) to compute basic affordability and risk
metrics before an underwriter ever looks at the file. This is slow
(average 2–3 business days to first triage), inconsistent across officers,
hard to audit, and does not scale with application volume.

**Loan Evaluator** is a rules-based decision-support engine that automatically
computes standard underwriting metrics — Debt-to-Income (DTI), Loan-to-Value
(LTV), credit tier, and employment stability — from an applicant's financial
profile, and returns a structured, explainable recommendation (risk level,
strengths, red flags, conditions, and next step) within seconds. It is a
**pre-screening / decision-support tool, not an autonomous approval or denial
authority** — a human underwriter remains in the loop for every adverse
outcome, per Regulation B (ECOA).

## 2. Business Problem Statement

- Inconsistent underwriting judgment across officers leads to disparate
  treatment risk and rework.
- No standardized, auditable record of *why* a decision leaned a certain way.
- Underwriters spend the majority of their time on applications that could be
  auto-approved or auto-triaged, instead of focusing on genuinely borderline
  cases.
- Manual DTI/LTV math is a recurring source of clerical error.

## 3. Business Objectives

| ID | Objective |
|---|---|
| BO-1 | Reduce average time-to-first-triage from ~2 days to under 1 minute for straightforward applications. |
| BO-2 | Standardize underwriting criteria across all channels and officers. |
| BO-3 | Produce a defensible, auditable rationale for every recommendation, including adverse-action-ready reason codes. |
| BO-4 | Reduce manual underwriter workload by auto-routing only borderline/high-risk files for full manual review. |
| BO-5 | Lower disparate-impact / fair-lending risk versus ad hoc human judgment, and make that risk continuously measurable. |

## 4. Scope

### In Scope
- Mortgage, auto, and unsecured personal loan applications.
- Computation of DTI, LTV (where collateral applies), credit score
  tiering, and employment stability.
- Red-flag detection (bankruptcy, foreclosure, extreme DTI, very low
  credit score, unverifiable income, etc.).
- Output of: risk level, strengths, red flags, conditions, recommendation,
  and human-readable rationale.
- Full audit logging of every evaluation.
- Configurable underwriting thresholds by loan type and jurisdiction.

### Out of Scope (this release)
- Final loan approval/denial authority (remains with human underwriter).
- Loan origination, document generation, closing, servicing, payment
  processing.
- KYC/AML/identity verification (assumed to happen upstream).
- Direct credit bureau integration UI (bureau data assumed to arrive as
  input via an existing upstream service).

## 5. Stakeholders

| Role | Stakeholder | Interest |
|---|---|---|
| Executive Sponsor | Head of Lending | ROI, throughput, risk reduction |
| Business Owner | VP, Underwriting Operations | Process standardization |
| End Users | Loan Officers / Underwriters | Usability, trustworthy output |
| Compliance & Legal | Chief Compliance Officer | ECOA/Reg B, FCRA, fair lending |
| Risk Management | Credit Risk | Threshold calibration, model risk |
| Engineering | Dev/QA/SRE | Build, test, operate |
| Indirect | Applicants/Consumers | Fair, timely, explainable decisions |

## 6. Business Requirements

| ID | Requirement |
|---|---|
| BR-01 | The system shall calculate a Debt-to-Income (DTI) ratio for every applicant. |
| BR-02 | The system shall calculate a Loan-to-Value (LTV) ratio whenever collateral value applies (mortgage, auto). |
| BR-03 | The system shall classify the applicant's credit score into a standard risk tier. |
| BR-04 | The system shall evaluate employment history and income stability. |
| BR-05 | The system shall detect defined red-flag conditions (e.g., recent bankruptcy/foreclosure, extreme DTI, very low credit score, unverifiable income). |
| BR-06 | The system shall produce an overall Risk Level of Low, Medium, or High. |
| BR-07 | The system shall produce a Recommendation: Approve, Approve with Conditions, or Refer for Manual Underwriting. |
| BR-08 | The system shall list specific Conditions required for approval (e.g., PMI, co-signer, additional documentation). |
| BR-09 | The system shall provide a plain-language rationale for every recommendation, including reason codes suitable for adverse-action notices. |
| BR-10 | The system shall retain a complete, immutable audit trail of inputs, computed metrics, ruleset version, and output for every evaluation. |
| BR-11 | The system shall never issue a final decline; the strongest automated outcome is "Refer for Manual Underwriting" — a human underwriter makes all adverse decisions. |
| BR-12 | The system shall support configurable underwriting thresholds per loan type and jurisdiction without a code deployment. |
| BR-13 | The system shall exclude prohibited factors (race, color, religion, national origin, sex, marital status, age, public-assistance income) from evaluation logic, directly or as a proxy. |

## 7. Assumptions & Constraints

- Credit bureau score and applicant financial data arrive pre-validated
  from an upstream intake service.
- Thresholds in this release reflect current underwriting policy and are
  subject to periodic recalibration by Risk Management.
- The system operates as a decision-support tool; legal responsibility for
  adverse decisions rests with the human underwriter of record.
- Regulatory environment: U.S. federal (ECOA/Reg B, TILA, FCRA, GLBA) plus
  applicable state lending law.

## 8. Success Metrics / KPIs

| KPI | Target |
|---|---|
| Time-to-first-triage | < 1 minute for 95% of applications |
| Manual underwriting queue volume | -30% within 2 quarters |
| Decision consistency (same inputs → same output) | 100% |
| Fair-lending disparity ratio (adverse-impact ratio) | Within regulatory 80% "four-fifths rule" guideline, monitored quarterly |
| Audit trail completeness | 100% of evaluations logged |

## 9. Regulatory & Compliance Considerations

- **ECOA / Regulation B** — adverse action notices, prohibited basis factors, human-in-the-loop for denials.
- **TILA** — disclosure accuracy for any terms referenced in output.
- **FCRA** — permissible use of credit data, adverse-action credit score disclosure.
- **GLBA** — safeguarding of nonpublic personal information (NPI).
- **Fair lending / disparate impact** — ongoing statistical monitoring across protected classes.
- **State usury and lending law** — jurisdiction-specific threshold configuration (BR-12).

## 10. Key Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Thresholds encode unintended bias | Regulatory/legal exposure | Fair-lending testing (see Test Strategy §6), periodic disparate-impact review |
| Over-reliance on automation for denials | ECOA violation | BR-11 hard constraint: no auto-decline, enforced in code and tested |
| Stale/misconfigured thresholds | Bad business outcomes | Config versioning + approval workflow (BR-12, NFR-208) |
| Incomplete audit trail | Regulatory exam failure | BR-10 mandatory logging, tested end-to-end |

## 11. Approval / Sign-off

| Role | Name | Approved | Date |
|---|---|---|---|
| Business Owner | | ☐ | |
| Compliance | | ☐ | |
| Engineering Lead | | ☐ | |
| QA Lead | | ☐ | |
