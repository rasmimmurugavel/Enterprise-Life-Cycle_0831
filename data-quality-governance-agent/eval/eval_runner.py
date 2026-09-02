"""Automated eval rubric runner (BR-08, HLD §2.5).

Runs the real agent (app/agent.py) against each fixture database in
eval/fixtures/*, diffs its findings against that fixture's golden.json,
and scores the run against the release gate in eval/rubrics.yaml. This
is what "an automated eval rubric" means concretely in this project:
not a vibe check, a scored, versioned, CI-runnable regression suite
that a prompt/tool/model change must pass before it ships.

Usage:
    python -m eval.eval_runner                 # run all fixtures
    python -m eval.eval_runner --fixture nulls_and_dupes
    python -m eval.eval_runner --report out.json

Requires:
    - DATABASE_URL / PG* pointing at a Postgres instance the eval can
      seed (needs CREATE SCHEMA privileges - NOT the read-only
      dq_audit_reader role the agent itself uses at audit time; see
      db/README.md). Set DQ_EVAL_ADMIN_DATABASE_URL to use a separate,
      more-privileged connection for seeding only.
    - ANTHROPIC_API_KEY (the eval calls the real model - it is
      deliberately not mocked, since the point is to catch prompt/tool
      regressions an offline unit test can't see).

The matching/scoring functions below (`match_finding`,
`score_fixture_result`, `aggregate`) are pure and unit-tested
independently in tests/test_eval_runner.py without needing a live DB
or API key.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "eval" / "fixtures"
RUBRICS_PATH = ROOT / "eval" / "rubrics.yaml"

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# --- Pure scoring logic (no DB, no network - fully unit-testable) ----------


def load_rubrics(path: Path = RUBRICS_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_golden(fixture_dir: Path) -> dict[str, Any]:
    with open(fixture_dir / "golden.json", encoding="utf-8") as fh:
        return json.load(fh)


def _finding_key(f: dict[str, Any]) -> tuple[str, str, str]:
    return (
        (f.get("table") or "").lower(),
        (f.get("column") or "").lower(),
        (f.get("dimension") or "").lower(),
    )


def match_finding(golden_finding: dict[str, Any], agent_findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the agent finding matching a golden finding on
    (table, column, dimension) - the identity of "did you catch this
    specific defect", independent of exact wording."""
    gkey = _finding_key(golden_finding)
    for f in agent_findings:
        if _finding_key(f) == gkey:
            return f
    return None


def severity_meets_floor(agent_severity: str, min_severity: str) -> bool:
    return _SEVERITY_RANK.get(agent_severity, -1) >= _SEVERITY_RANK.get(min_severity, 99)


def match_pii(golden_pii: dict[str, Any], agent_pii: list[dict[str, Any]]) -> dict[str, Any] | None:
    for p in agent_pii:
        if (p.get("table") or "").lower() != (golden_pii.get("table") or "").lower():
            continue
        if (p.get("column") or "").lower() != (golden_pii.get("column") or "").lower():
            continue
        expected_categories = golden_pii.get("category_any_of") or [golden_pii.get("category")]
        if (p.get("category") or "").lower() in [c.lower() for c in expected_categories if c]:
            return p
    return None


@dataclass
class FixtureScore:
    fixture: str
    matched_findings: int = 0
    total_golden_findings: int = 0
    unmatched_agent_findings: int = 0
    total_agent_findings: int = 0
    severity_correct: int = 0
    matched_pii: int = 0
    total_golden_pii: int = 0
    pii_leak_incidents: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def score_fixture_result(golden: dict[str, Any], findings: dict[str, Any],
                          transcript_text: str) -> FixtureScore:
    """Pure scoring: given a fixture's golden.json and the agent's
    findings payload (+ a flattened string of everything the agent saw/
    said, for the PII-leak check), compute match counts. No I/O."""
    score = FixtureScore(fixture=golden["fixture"])

    agent_findings = findings.get("findings", [])
    score.total_agent_findings = len(agent_findings)
    score.total_golden_findings = len(golden.get("findings", []))

    matched_agent_finding_ids = set()
    for gf in golden.get("findings", []):
        match = match_finding(gf, agent_findings)
        if match is None:
            score.details.append(f"MISSED finding: {gf['table']}.{gf.get('column')} / {gf['dimension']}")
            continue
        score.matched_findings += 1
        matched_agent_finding_ids.add(id(match))
        min_sev = gf.get("min_severity", "low")
        if severity_meets_floor(match.get("severity", "low"), min_sev):
            score.severity_correct += 1
        else:
            score.details.append(
                f"SEVERITY TOO LOW: {gf['table']}.{gf.get('column')} - expected >= {min_sev}, "
                f"got {match.get('severity')}"
            )

    score.unmatched_agent_findings = sum(
        1 for f in agent_findings if id(f) not in matched_agent_finding_ids
    )
    for f in agent_findings:
        if id(f) not in matched_agent_finding_ids:
            score.details.append(f"EXTRA finding (not in golden): {f.get('table')}.{f.get('column')} / {f.get('dimension')}")

    agent_pii = findings.get("governance_summary", {}).get("pii_columns_detected", [])
    score.total_golden_pii = len(golden.get("pii_columns_detected", []))
    for gp in golden.get("pii_columns_detected", []):
        if match_pii(gp, agent_pii):
            score.matched_pii += 1
        else:
            score.details.append(f"MISSED PII column: {gp['table']}.{gp['column']}")

    for value in golden.get("known_pii_values", []):
        if value and value in transcript_text:
            score.pii_leak_incidents.append(value)

    return score


@dataclass
class AggregateReport:
    fixture_scores: list[FixtureScore]
    recall: float
    precision: float
    severity_accuracy: float
    pii_recall: float
    pii_leak_incidents: int
    passed: bool
    gate: dict[str, Any]
    failure_reasons: list[str] = field(default_factory=list)


def aggregate(scores: list[FixtureScore], gate: dict[str, Any]) -> AggregateReport:
    total_golden = sum(s.total_golden_findings for s in scores)
    total_matched = sum(s.matched_findings for s in scores)
    total_agent = sum(s.total_agent_findings for s in scores)
    total_severity_checked = sum(s.matched_findings for s in scores)
    total_severity_correct = sum(s.severity_correct for s in scores)
    total_golden_pii = sum(s.total_golden_pii for s in scores)
    total_matched_pii = sum(s.matched_pii for s in scores)
    total_leaks = sum(len(s.pii_leak_incidents) for s in scores)

    recall = (total_matched / total_golden) if total_golden else 1.0
    precision = (total_matched / total_agent) if total_agent else 1.0
    severity_accuracy = (total_severity_correct / total_severity_checked) if total_severity_checked else 1.0
    pii_recall = (total_matched_pii / total_golden_pii) if total_golden_pii else 1.0

    reasons = []
    if recall < gate["min_dimension_recall"]:
        reasons.append(f"recall {recall:.2f} < min_dimension_recall {gate['min_dimension_recall']}")
    if precision < gate["min_precision"]:
        reasons.append(f"precision {precision:.2f} < min_precision {gate['min_precision']}")
    if severity_accuracy < gate["min_severity_accuracy"]:
        reasons.append(f"severity_accuracy {severity_accuracy:.2f} < min_severity_accuracy {gate['min_severity_accuracy']}")
    if total_leaks > gate["max_pii_leak_incidents"]:
        reasons.append(f"pii_leak_incidents {total_leaks} > max_pii_leak_incidents {gate['max_pii_leak_incidents']}")
    if pii_recall < gate["min_dimension_recall"]:
        reasons.append(f"pii_recall {pii_recall:.2f} < min_dimension_recall {gate['min_dimension_recall']}")

    return AggregateReport(
        fixture_scores=scores,
        recall=recall,
        precision=precision,
        severity_accuracy=severity_accuracy,
        pii_recall=pii_recall,
        pii_leak_incidents=total_leaks,
        passed=not reasons,
        gate=gate,
        failure_reasons=reasons,
    )


# --- I/O: seeding fixtures and running the real agent -----------------------


def _admin_dsn() -> str:
    return os.getenv("DQ_EVAL_ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL") or ""


def seed_fixture(golden: dict[str, Any]) -> None:
    dsn = _admin_dsn()
    if not dsn:
        raise RuntimeError(
            "DQ_EVAL_ADMIN_DATABASE_URL or DATABASE_URL must be set to a role with "
            "CREATE SCHEMA privileges to seed eval fixtures (see db/README.md)."
        )
    seed_path = ROOT / golden["seed_file"]
    sql = seed_path.read_text(encoding="utf-8")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


async def run_fixture_async(fixture_dir: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    golden = load_golden(fixture_dir)
    seed_fixture(golden)

    # Scope the agent to exactly this fixture's schema so fixtures don't
    # bleed into each other's results, and so a fresh MCP server
    # subprocess (spawned per run, see app/agent.py::_mcp_session) picks
    # up the restriction via its inherited environment.
    os.environ["DQ_ALLOWED_SCHEMAS"] = golden["schema"]

    from app.agent import run_audit_async  # deferred import: needs env set above first

    events: list[Any] = []
    result = await run_audit_async(
        f"Audit all tables in schema {golden['schema']}",
        on_progress=lambda e: events.append(e),
    )
    transcript_text = json.dumps(
        [{"tool": e.tool_name, "args": e.arguments, "summary": e.result_summary} for e in events]
    ) + json.dumps(result.findings, default=str)
    return golden, result.findings, transcript_text


def discover_fixtures(only: str | None = None) -> list[Path]:
    fixtures = sorted(p for p in FIXTURES_DIR.iterdir() if (p / "golden.json").exists())
    if only:
        fixtures = [f for f in fixtures if f.name == only]
    return fixtures


async def main_async(only: str | None, report_path: str | None) -> int:
    rubrics = load_rubrics()
    fixtures = discover_fixtures(only)
    if not fixtures:
        print(f"No fixtures found (filter={only!r}) under {FIXTURES_DIR}", file=sys.stderr)
        return 2

    scores: list[FixtureScore] = []
    for fixture_dir in fixtures:
        print(f"--- Running fixture: {fixture_dir.name} ---")
        golden, findings, transcript_text = await run_fixture_async(fixture_dir)
        score = score_fixture_result(golden, findings, transcript_text)
        scores.append(score)
        print(
            f"  findings: {score.matched_findings}/{score.total_golden_findings} matched, "
            f"{score.unmatched_agent_findings} extra; pii: {score.matched_pii}/{score.total_golden_pii}; "
            f"leaks: {len(score.pii_leak_incidents)}"
        )
        for detail in score.details:
            print(f"    {detail}")

    report = aggregate(scores, rubrics["release_gate"])

    print("\n=== Eval summary ===")
    print(f"recall:             {report.recall:.2%}  (gate: >= {report.gate['min_dimension_recall']:.0%})")
    print(f"precision:          {report.precision:.2%}  (gate: >= {report.gate['min_precision']:.0%})")
    print(f"severity_accuracy:  {report.severity_accuracy:.2%}  (gate: >= {report.gate['min_severity_accuracy']:.0%})")
    print(f"pii_recall:         {report.pii_recall:.2%}")
    print(f"pii_leak_incidents: {report.pii_leak_incidents}  (gate: <= {report.gate['max_pii_leak_incidents']})")
    print(f"\nRESULT: {'PASS' if report.passed else 'FAIL'}")
    for reason in report.failure_reasons:
        print(f"  - {reason}")

    if report_path:
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "passed": report.passed,
                    "recall": report.recall,
                    "precision": report.precision,
                    "severity_accuracy": report.severity_accuracy,
                    "pii_recall": report.pii_recall,
                    "pii_leak_incidents": report.pii_leak_incidents,
                    "failure_reasons": report.failure_reasons,
                    "fixtures": [
                        {
                            "fixture": s.fixture,
                            "matched_findings": s.matched_findings,
                            "total_golden_findings": s.total_golden_findings,
                            "details": s.details,
                        }
                        for s in scores
                    ],
                },
                fh,
                indent=2,
            )

    return 0 if report.passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", help="Run only this fixture (directory name under eval/fixtures/)")
    parser.add_argument("--report", help="Write a JSON report to this path")
    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args.fixture, args.report))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
