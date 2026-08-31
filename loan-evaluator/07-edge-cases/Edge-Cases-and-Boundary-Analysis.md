# Edge Case & Boundary Analysis — Loan Evaluator

| Field | Value |
|---|---|
| Doc ID | EC-LE-001 |
| Version | 1.0 |
| Purpose | Scenarios beyond straightforward requirement verification — the cases that break naive implementations and that reviewers/auditors will specifically probe for. |

Each edge case is linked into the RTM (`08-traceability/RTM.md`) alongside
the standard test cases. Numeric boundary values themselves are already
covered as TC-002–TC-023 in `06-test-cases/Test-Cases.md`; this catalog
covers combinations, malformed input, timing, and systemic edge cases that
boundary-value analysis alone doesn't surface.

## 1. Input Validation & Malformed Data

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-001 | Missing required field (e.g., `credit_score` key absent entirely, vs. present as `null`) | "Absent" and "explicit no-score" are different business meanings but easy to conflate in code | Absent required field → validation error (400-equivalent); explicit `null` credit score → No-Score business path (FR-103) |
| EC-002 | Negative numeric values (negative income, negative loan amount) | Naive math won't error, it'll silently produce nonsense ratios | Rejected at input validation, not passed to the rules engine |
| EC-003 | Zero values (`annual_income = 0`, `collateral_value = 0`) | Division by zero in DTI/LTV formulas | `annual_income = 0` → DTI undefined → treat as red flag / reject, not a crash or `Infinity`; `collateral_value = 0` on a secured loan type is a validation error |
| EC-004 | Extremely large values (loan amount = $999,999,999,999) | Integer overflow / display truncation in downstream systems | Enforce a sane upper bound at validation; reject or flag for manual review rather than silently truncating |
| EC-005 | Malformed JSON / wrong types (`credit_score: "seven fifty"`) | Type coercion bugs | Reject with a clear validation error, not a coerced/guessed value |
| EC-006 | Oversized payload / injection attempt in free-text fields | Security — the applicant-controlled fields are an attack surface | Input size limits, output encoding, parameterized queries; verify with a security test (see NFR-203 test in Test Strategy §6) |

## 2. Numeric & Rounding Edge Cases

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-007 | DTI/LTV computes to a repeating decimal (e.g., 33.333...%) | Rounding rule must be defined and consistent, or the same application can land on different sides of a boundary depending on where rounding happens | Round to 1 decimal using a single, documented rounding rule (e.g., round-half-up) applied once, at output — not at each intermediate step |
| EC-008 | Currency/floating-point precision (e.g., `$1234.005` debt payment) | Binary floating point can misrepresent exact decimal currency values, shifting a boundary case by a cent | Use a decimal (not binary float) type for all currency math |
| EC-009 | DTI/LTV that lands *exactly* on a threshold after rounding but not before (e.g., raw 36.049999 → rounds to 36.0) | The "inclusive boundary" rule (FR-101/FR-102) must apply to the *rounded, reported* value, and both must agree | Verify the reported value and the tier decision are computed from the same rounded number |

## 3. Rule Interaction & Conflict Edge Cases

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-010 | Every red flag fires simultaneously (RF-1 through RF-8 all true) | Aggregation logic (FR-106) must not crash, dedupe incorrectly, or silently drop flags when many are present | All applicable red flags appear in `red_flags[]`; recommendation still resolves to a single valid enum value (never "more than Refer") |
| EC-011 | Conflicting signals: excellent credit (800) but DTI 60% + RF-3 | Confirms the "worst input wins, red flag is a hard ceiling" rule isn't overridden by a strong compensating factor | Still resolves to High risk / Refer — a strong credit score cannot offset a hard red flag |
| EC-012 | Threshold changed (FR-110) mid-flight between validation and evaluation | Race condition between config read and business-rule application | Each evaluation must pin a single `ruleset_version` atomically at the start of processing; concurrent config changes must not affect an in-flight evaluation |
| EC-013 | Jurisdiction with no configured threshold override (falls back to default) | Silent misconfiguration risk (BR-12) | Explicit fallback-to-default behavior must be defined and logged, not an unhandled lookup miss |

## 4. Co-Borrower Edge Cases

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-014 | Co-borrower has a red flag the primary applicant doesn't (e.g., co-borrower has a foreclosure) | Easy to only evaluate the primary applicant's red-flag fields | Red flags must be evaluated across primary **and** co-borrower per FR-101a's combined-household intent |
| EC-015 | Co-borrower present but with `null`/missing sub-fields | Partial co-borrower data | Treated as a validation error, not silently ignored (which would understate combined DTI) |
| EC-016 | Adverse outcome driven primarily by the co-borrower, not the primary applicant | ECOA notice must correctly attribute reasons | Rationale/reason codes (FR-108) must indicate which applicant (primary/co-borrower) each factor applies to |

## 5. Date & Time Edge Cases

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-017 | Bankruptcy/foreclosure date exactly 7 years ago today | Off-by-one on the "within 7 years" window (FR-105 RF-1/RF-2) | Define and test the boundary explicitly: is exactly 7 years ago inside or outside the window? (Recommended: outside — window is "< 7 years") |
| EC-018 | Leap-year date math for employment length / lookback windows | Naive `(today - date) / 365` miscalculates around Feb 29 | Use a calendar-aware date library, not a fixed 365-day divisor |
| EC-019 | Evaluation submitted at a UTC day boundary vs. local branch time zone | "Discharged 7 years ago" could differ by a day depending on time zone used | Standardize on UTC for all date math and document it (ties to NFR-212 observability/consistency) |
| EC-020 | Future-dated bankruptcy/foreclosure date (data entry error upstream) | Should not be silently accepted | Validation error — dates must not be in the future |

## 6. Concurrency, Idempotency & Resilience

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-021 | Duplicate submission of the same application (double-click, retry after timeout) | Could create two audit records / two different outcomes if ruleset changed between them | Idempotency key on the request; duplicate within a defined window returns the original result, doesn't re-evaluate |
| EC-022 | Audit log store is unavailable at evaluation time | BR-10 makes the audit record mandatory, not best-effort | Evaluation must fail closed (no result returned to the caller) rather than return a recommendation with no audit trail |
| EC-023 | Config service unavailable at evaluation time | Same "fail closed vs. fail open" question as EC-022 | Documented and tested: recommend fail closed, or fall back to the last-known-good pinned ruleset — but never fall back to undefined/hardcoded thresholds silently |
| EC-024 | Two evaluations for the same applicant in flight simultaneously with different input (e.g., updated income mid-review) | Race condition producing an inconsistent audit trail | Each evaluation is independently keyed and logged; no shared mutable state between concurrent requests (supports NFR-207/211) |

## 7. Compliance-Specific Edge Cases

| EC ID | Scenario | Why it matters | Expected handling |
|---|---|---|---|
| EC-025 | Applicant profile that would statistically correlate with a protected class even though no prohibited field was submitted (proxy discrimination, e.g., zip code as an income proxy) | The hardest and most important edge case for a lending system — this is exactly what fair-lending exams look for | Covered by NFR-206 fairness/disparate-impact testing (TC-047), not by a single functional test; requires periodic statistical review, not just unit tests |
| EC-026 | Recommendation is "Refer for Manual Underwriting" but the human underwriter's eventual decision needs to be fed back for audit linkage | The automated system's audit trail (FR-109) must connect to the final human decision, or the audit trail is incomplete for regulatory exam purposes | Confirm the audit record schema supports a later-appended "final human decision" field/link |
| EC-027 | Adverse-action rationale (FR-108) must remain accurate if thresholds change (FR-110) after the evaluation was performed but before the notice is sent | Reason codes must reflect the ruleset actually applied, not the current live config | Rationale is generated and stored at evaluation time using the pinned `ruleset_version`, never recomputed later against current config |
