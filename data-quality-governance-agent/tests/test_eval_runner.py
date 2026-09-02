"""Unit tests for the pure scoring logic in eval/eval_runner.py.
No live database or Anthropic API call required - these test the
matching/aggregation math against synthetic agent outputs, not the
agent itself (that's what eval_runner.py's actual `main()` run does,
against real fixtures, per 12-eval-rubrics/Eval-Rubric-Spec.md)."""
from __future__ import annotations

from pathlib import Path

from eval.eval_runner import aggregate, load_golden, load_rubrics, score_fixture_result

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "eval" / "fixtures"


def test_load_rubrics_has_expected_shape() -> None:
    rubrics = load_rubrics()
    assert rubrics["version"]
    assert set(rubrics["dimensions"]) == {"completeness", "validity", "uniqueness", "consistency", "timeliness"}
    gate = rubrics["release_gate"]
    for key in ("min_dimension_recall", "min_precision", "min_severity_accuracy", "max_pii_leak_incidents"):
        assert key in gate


def test_all_fixtures_have_loadable_golden_files() -> None:
    fixture_dirs = [p for p in FIXTURES_DIR.iterdir() if p.is_dir()]
    assert len(fixture_dirs) >= 4
    for fixture_dir in fixture_dirs:
        golden = load_golden(fixture_dir)
        assert golden["fixture"] == fixture_dir.name
        assert "schema" in golden
        assert "seed_file" in golden


def test_good_agent_run_scores_full_recall_and_passes_gate() -> None:
    rubrics = load_rubrics()
    golden = load_golden(FIXTURES_DIR / "nulls_and_dupes")

    findings = {
        "findings": [
            {"table": "customers", "column": "full_name", "dimension": "completeness", "severity": "high", "description": "x", "evidence": {}},
            {"table": "customers", "column": "signup_date", "dimension": "completeness", "severity": "low", "description": "x", "evidence": {}},
            {"table": "customers", "column": "email", "dimension": "uniqueness", "severity": "medium", "description": "x", "evidence": {}},
        ],
        "governance_summary": {
            "pii_columns_detected": [{"table": "customers", "column": "email", "category": "email"}],
            "overrides_applied": [],
        },
    }
    score = score_fixture_result(golden, findings, transcript_text="masked values only, e.g. j***@***.test")

    assert score.matched_findings == score.total_golden_findings == 3
    assert score.unmatched_agent_findings == 0
    assert score.severity_correct == 3
    assert score.matched_pii == 1
    assert score.pii_leak_incidents == []

    report = aggregate([score], rubrics["release_gate"])
    assert report.recall == 1.0
    assert report.passed is True
    assert report.failure_reasons == []


def test_bad_agent_run_fails_gate_for_the_right_reasons() -> None:
    rubrics = load_rubrics()
    golden = load_golden(FIXTURES_DIR / "nulls_and_dupes")

    findings = {
        "findings": [
            {"table": "customers", "column": "full_name", "dimension": "completeness", "severity": "low", "description": "x", "evidence": {}},
        ],
        "governance_summary": {"pii_columns_detected": [], "overrides_applied": []},
    }
    # Deliberately leak a raw PII value seeded into this fixture.
    leaking_transcript = 'debug: raw row was {"email": "carol@example.test"}'
    score = score_fixture_result(golden, findings, transcript_text=leaking_transcript)

    assert score.matched_findings == 1
    assert score.severity_correct == 0  # "low" doesn't meet the "medium" floor
    assert score.pii_leak_incidents == ["carol@example.test"]

    report = aggregate([score], rubrics["release_gate"])
    assert report.passed is False
    assert any("recall" in r for r in report.failure_reasons)
    assert any("severity_accuracy" in r for r in report.failure_reasons)
    assert any("pii_leak_incidents" in r for r in report.failure_reasons)


def test_aggregate_with_no_findings_at_all_does_not_divide_by_zero() -> None:
    rubrics = load_rubrics()
    golden = {"fixture": "empty", "findings": [], "pii_columns_detected": [], "known_pii_values": []}
    score = score_fixture_result(golden, {"findings": [], "governance_summary": {}}, transcript_text="")
    report = aggregate([score], rubrics["release_gate"])
    assert report.recall == 1.0  # vacuously true: nothing expected, nothing missed
    assert report.passed is True
