# Functional & Non-Functional Requirements Specification (FRD/SRS)
## Project: Loan Evaluator

| Field | Value |
|---|---|
| Doc ID | FRD-LE-001 |
| Version | 1.0 |
| Traces to | BRD-LE-001 |
| Status | Draft for Review |

Each requirement below traces to a Business Requirement (BR-xx) in
`BRD-Loan-Evaluator.md` and forward to test cases in
`06-test-cases/Test-Cases.md` via the Requirements Traceability Matrix
(`08-traceability/RTM.md`).

---

## 1. Input Data Contract

| Field | Type | Notes |
|---|---|---|
| `applicant_id` | string | Required |
| `loan_type` | enum: `mortgage`, `auto`, `personal` | Required |
| `requested_loan_amount` | decimal > 0 | Required |
| `annual_income` | decimal ≥ 0 | Required |
| `monthly_debt_payments` | decimal ≥ 0 | Existing debt, excludes the new loan |
| `credit_score` | integer 300–850, or `null` for thin-file | Required field, nullable value |
| `collateral_value` | decimal > 0 | Required for `mortgage`/`auto`; omitted for `personal` |
| `down_payment` | decimal ≥ 0 | Optional, default 0 |
| `employment_status` | enum: `employed`, `self_employed`, `unemployed`, `retired` | Required |
| `employment_length_years` | decimal ≥ 0 | Required |
| `bankruptcy_discharge_date` | date or `null` | |
| `foreclosure_date` | date or `null` | |
| `income_verified` | boolean | Set by upstream verification step |
| `co_borrower` | object or `null` | Same sub-fields as primary applicant, income/debt combined per FR-104a |

## 2. Output Data Contract

| Field | Type | Notes |
|---|---|---|
| `dti_ratio` | decimal (%) | |
| `ltv_ratio` | decimal (%) or `null` | `null` for `personal` loans |
| `credit_tier` | enum | Excellent / Good / Fair / Poor / Very Poor / No-Score |
| `employment_assessment` | enum | Stable / Limited History / Unverified |
| `red_flags` | array of reason codes | Empty if none |
| `strengths` | array of strings | |
| `risk_level` | enum | Low / Medium / High |
| `recommendation` | enum | Approve / Approve with Conditions / Refer for Manual Underwriting |
| `conditions` | array of strings | Empty if none |
| `rationale` | array of {code, message} | Adverse-action-ready |
| `ruleset_version` | string | For audit trail |
| `evaluated_at` | timestamp (UTC) | |

---

## 3. Functional Requirements

### FR-101 — DTI Calculation *(traces to BR-01)*
The system shall compute:
`DTI = (monthly_debt_payments + proposed_new_payment) / (annual_income / 12) × 100`,
rounded to 1 decimal place.
- Tiering: `DTI ≤ 36.0` → Low · `36.1–43.0` → Medium · `> 43.0` → High.
- If `co_borrower` is present, combine both incomes and debts before computing DTI (FR-101a).

### FR-102 — LTV Calculation *(traces to BR-02)*
Applicable only to `loan_type` in {`mortgage`, `auto`}.
`LTV = requested_loan_amount / collateral_value × 100`, rounded to 1 decimal place.
- Tiering: `LTV ≤ 80.0` → Low · `80.1–95.0` → Medium · `> 95.0` → High.
- For `loan_type = personal`, `ltv_ratio` is `null` and excluded from risk aggregation.

### FR-103 — Credit Score Tiering *(traces to BR-03)*
| Score range | Tier |
|---|---|
| 750–850 | Excellent |
| 700–749 | Good |
| 650–699 | Fair |
| 600–649 | Poor |
| 300–599 | Very Poor |
| `null` (no score / thin file) | No-Score → forces `recommendation = Refer for Manual Underwriting` |

A `credit_score` outside 300–850 (and not `null`) is a **validation error** (reject the request, HTTP 400 equivalent), not a business outcome.

### FR-104 — Employment Stability *(traces to BR-04)*
- `employment_length_years ≥ 2` and `employment_status = employed` → Stable.
- `employment_status = self_employed` with `income_verified = true` **and** `employment_length_years ≥ 2` → Stable; otherwise → Unverified.
- `employment_length_years < 2` (any status except retired) → Limited History (adds condition, not a red flag by itself).
- `employment_status = unemployed` with no other qualifying income → red flag RF-6 (FR-105) and `employment_assessment = Unverified`.

### FR-105 — Red Flag Detection *(traces to BR-05, BR-11)*
| Code | Condition |
|---|---|
| RF-1 | `bankruptcy_discharge_date` within last 7 years |
| RF-2 | `foreclosure_date` within last 7 years |
| RF-3 | `dti_ratio > 50.0` |
| RF-4 | `credit_score < 580` (and not `null`) |
| RF-5 | `ltv_ratio > 100.0` (underwater collateral) |
| RF-6 | `employment_status = unemployed` with no qualifying income |
| RF-7 | `income_verified = false` for `self_employed` applicants |
| RF-8 | Required field missing/malformed after upstream validation gap |

**Any single red flag forces `risk_level = High` and `recommendation` no better than `Refer for Manual Underwriting`.** The system shall never output a final "Decline" (BR-11).

### FR-106 — Risk Level & Recommendation Aggregation *(traces to BR-06, BR-07)*
1. If any red flag present (FR-105) → `risk_level = High`, `recommendation = Refer for Manual Underwriting`.
2. Else if `credit_tier` = No-Score → `risk_level = High`, `recommendation = Refer for Manual Underwriting`.
3. Else take the **worst** of the DTI tier, LTV tier (if applicable), and credit tier (mapped Excellent/Good→Low, Fair→Medium, Poor→High):
   - All Low → `risk_level = Low`, `recommendation = Approve`.
   - Worst = Medium → `risk_level = Medium`, `recommendation = Approve with Conditions`.
   - Worst = High (without a hard red flag) → `risk_level = High`, `recommendation = Refer for Manual Underwriting`.

### FR-107 — Conditions Generation *(traces to BR-08)*
| Trigger | Condition text |
|---|---|
| `80.1 ≤ LTV ≤ 95.0` | "Private mortgage insurance (PMI) required." |
| `36.1 ≤ DTI ≤ 43.0` | "Additional income documentation or reduced loan amount required." |
| Employment = Limited History | "Additional employment/income documentation required." |
| `employment_status = self_employed` | "Two years of tax returns required." |

### FR-108 — Rationale & Adverse-Action Reason Codes *(traces to BR-09)*
For every evaluation, the system shall populate `strengths[]` (e.g., "Credit tier: Excellent", "Stable employment history ≥ 5 years") and, whenever `recommendation ≠ Approve`, a `rationale[]` array of `{code, message}` pairs sufficient to generate an ECOA-compliant adverse-action notice (one entry per red flag or Medium/High tier driver).

### FR-109 — Audit Logging *(traces to BR-10)*
Every evaluation shall be persisted as an immutable record containing: full input snapshot, all computed intermediate values (DTI, LTV, tiers), `ruleset_version`, full output, and `evaluated_at` timestamp. Records are retained 7 years minimum (regulatory retention) and are read-only after write.

### FR-110 — Configurable Thresholds *(traces to BR-12)*
All numeric thresholds in FR-101–FR-105 (DTI/LTV/credit bands, red-flag cutoffs) shall be sourced from a versioned configuration service, scoped by `loan_type` and jurisdiction, changeable via an approval workflow without a code deployment. Each evaluation records the `ruleset_version` used.

### FR-111 — Prohibited Factor Exclusion *(traces to BR-13)*
The input contract (§1) and rule engine (FR-101–FR-107) shall not accept or derive from race, color, religion, national origin, sex, marital status, age (except as a permissible credit-scoring factor per Reg B), or receipt-of-public-assistance income. Any attempt to submit such fields shall be rejected at the API boundary.

---

## 4. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-201 | Performance: p95 evaluation latency < 2 seconds; sustain 100 requests/sec. |
| NFR-202 | Availability: 99.9% uptime during business hours; graceful degradation (queue + async) beyond that. |
| NFR-203 | Security: NPI encrypted at rest (AES-256) and in transit (TLS 1.2+); SSN/account numbers masked in logs; RBAC on all endpoints. |
| NFR-204 | Auditability: 100% of evaluations logged per FR-109; logs tamper-evident. |
| NFR-205 | Explainability: no output without accompanying `rationale[]`/`strengths[]`; no unexplainable black-box scoring. |
| NFR-206 | Fairness: quarterly disparate-impact statistical testing across protected classes on real (deidentified) decision data; four-fifths rule as the monitoring threshold. |
| NFR-207 | Scalability: stateless service, horizontally scalable. |
| NFR-208 | Configurability: threshold changes require a two-person approval workflow and are versioned (FR-110). |
| NFR-209 | Privacy: GLBA-compliant handling of NPI; data minimization; masked/synthetic data in all non-production environments. |
| NFR-210 | Accessibility: any officer-facing UI meets WCAG 2.1 AA. |
| NFR-211 | Reliability: identical inputs + identical `ruleset_version` shall always produce identical output (deterministic, idempotent). |
| NFR-212 | Observability: structured logs/metrics/traces for every evaluation; alerting on error-rate and latency SLO breach. |
