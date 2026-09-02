# Eval Rubric Specification

| Field | Value |
|---|---|
| Document ID | EVAL-DQGA-12 |
| Traces from | `01-business-requirements/BRD.md` BR-08, `03-design/HLD.md` §2.5 |
| Implements | `eval/rubrics.yaml`, `eval/eval_runner.py`, `eval/fixtures/*`, `eval/schemas/findings.schema.json` |

## 1. Why this exists

An LLM agent's judgment drifts under a model upgrade, a prompt edit, or
a tool-schema change - silently, unless something measures it. This
document defines what "the agent still works" means concretely enough
to gate a release on it, per BR-08: *"the system's judgment shall be
defined as versioned, testable rubrics, and every release shall be
evaluated against a fixed set of scenarios with known-correct answers
before being considered production-ready."*

## 2. What gets scored

| Dimension | Owned by | Where it's scored |
|---|---|---|
| Business meaning of "quality" (weights, dimension definitions) | Data Governance | `eval/rubrics.yaml` `dimensions:` |
| PII categories and detection threshold | Data Governance + Security | `eval/rubrics.yaml` `pii:` |
| Release pass/fail thresholds | Data Governance + Platform Eng jointly | `eval/rubrics.yaml` `release_gate:` |
| Output shape contract | Platform Engineering | `eval/schemas/findings.schema.json` |
| Ground truth per scenario | Platform Engineering, reviewed by Data Governance | `eval/fixtures/*/golden.json` |

Changing a weight, a threshold, or a fixture's golden answer is a
config/data change, not a code change - review it as you would any
other governance policy change, and bump `rubrics.yaml`'s `version`.

## 3. Fixtures

Each fixture is a minimal, disposable schema seeded by
`db/seed/<fixture>.sql` and a `golden.json` stating exactly what a
correct audit of it should find. All data is synthetic (`.test`
domains, obviously fake phone numbers) - fixtures are safe to commit
and never contain real PII.

| Fixture | Defect class exercised | Rubric dimension(s) |
|---|---|---|
| `nulls_and_dupes` | Missing required fields; a column that should be unique isn't | completeness, uniqueness |
| `orphaned_fk` | Foreign key added `NOT VALID` over pre-existing orphaned rows | consistency |
| `pii_column` | PII detectable only by value pattern, not column name (`notes`) | governance (PII), not a scored dimension |
| `stale_data` | Every row's freshness timestamp is ~400 days old | timeliness |

Each `golden.json` lists, per expected finding: `table`, `column`,
`dimension`, `min_severity` (a floor, not an exact match - the agent
may reasonably judge something more severe than the minimum), and
`evidence_expect` (informational key metrics for a human reviewing
`eval_runner.py`'s detail log). PII expectations live separately under
`pii_columns_detected`, since PII is a governance classification, not
one of the five scored dimensions - see `app/prompts.py`'s findings
shape.

`known_pii_values` lists the exact synthetic values seeded into the
fixture; `eval_runner.py` fails the run if any of them appears verbatim
anywhere in the agent's tool-call transcript or final output - this is
the automated check behind NFR-204 ("no unmasked PII ever reaches the
LLM"), not a manual spot-check.

## 4. Scoring model (`eval/eval_runner.py`)

For each fixture, the runner seeds the fixture, runs the **real**
agent (`app/agent.py`, real Claude API calls - deliberately not
mocked, since the point is to catch prompt/tool regressions a unit
test can't see) scoped to that fixture's schema, and matches its
output against `golden.json`:

- **Match key**: `(table, column, dimension)`, case-insensitive. This
  is deliberately not exact-text matching on `description` - wording
  varies run to run, identity of the defect does not.
- **Recall** = matched golden findings / total golden findings, rolled
  up across all fixtures.
- **Precision** = matched agent findings / total agent findings. An
  agent finding with no golden counterpart counts against precision -
  this is an approximation (a genuinely novel, correct finding we
  didn't anticipate also counts as a "miss" here) and is a known
  limitation; `eval_runner.py`'s per-finding detail log lists every
  "EXTRA finding" for human review rather than silently penalizing
  it unreviewed.
- **Severity accuracy** = of matched findings, the fraction where the
  agent's assigned severity meets or exceeds `min_severity`.
- **PII recall** = matched PII column classifications / total expected.
- **PII leak incidents** = count of known raw PII values found verbatim
  anywhere in the transcript or output, summed across fixtures.

## 5. Release gate

Current thresholds (`eval/rubrics.yaml` `release_gate:`, v1.0.0):

| Metric | Threshold | Rationale |
|---|---|---|
| Recall | ≥ 85% | Missing a real defect is the primary failure mode an audit tool must avoid. |
| Precision | ≥ 70% | Some false positives are tolerable (a human reviews the report); a flood of noise erodes trust in the tool. |
| Severity accuracy | ≥ 75% | Severity judgment has legitimate reasonable disagreement; this is a floor, not a bar for precision. |
| PII leak incidents | 0, hard gate | Zero tolerance - this is a compliance control, not a quality-of-life metric (NFR-204). |

Any threshold miss fails the run (`eval_runner.py` exit code 1) -
wire this into CI as a required check before merging a change to
`app/prompts.py`, `mcp_server/`, or `ANTHROPIC_MODEL`.

## 6. Running it

```bash
# One-time: point at a Postgres the eval is allowed to seed (needs
# CREATE SCHEMA - see db/README.md "Eval seeding role vs. the audit role").
export DQ_EVAL_ADMIN_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/dq_eval
export DATABASE_URL=postgresql://dq_audit_reader:changeme@localhost:5432/dq_eval
export ANTHROPIC_API_KEY=sk-ant-...

python -m eval.eval_runner                        # all fixtures
python -m eval.eval_runner --fixture pii_column    # one fixture
python -m eval.eval_runner --report eval_report.json
```

The scoring/matching functions (`match_finding`, `score_fixture_result`,
`aggregate` in `eval/eval_runner.py`) are pure and unit-tested without a
live database or API key in `tests/test_eval_runner.py` - CI can run
those on every PR even when the full live-model eval only runs on a
schedule or before a release.

## 7. Extending the suite

Adding a new fixture:

1. Write `db/seed/<name>.sql` - self-contained (`drop schema if exists
   ... cascade; create schema ...`), synthetic data only.
2. Write `eval/fixtures/<name>/golden.json` with the exact defects a
   correct audit of that schema should surface.
3. Get the golden answer reviewed by Data Governance before merging -
   it is the ground truth the release gate holds every future change
   to.
