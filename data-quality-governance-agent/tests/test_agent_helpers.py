"""Unit tests for app/agent.py's pure helper functions and findings
schema validation. No live Anthropic API call or MCP session
required - the ReAct loop itself is exercised by the eval suite
(eval/eval_runner.py), not here."""
from __future__ import annotations

import pytest

from app.agent import AgentRunError, _extract_json_object, _mcp_tools_to_anthropic, _summarize_tool_result, validate_findings


class _FakeTool:
    def __init__(self, name: str, description: str, input_schema: dict) -> None:
        self.name = name
        self.description = description
        self.inputSchema = input_schema


def _valid_findings() -> dict:
    return {
        "run_id": "r1",
        "scope": {"schemas": ["public"], "tables": ["orders"]},
        "tables_audited": ["orders"],
        "tables_not_audited": [],
        "scorecard": {
            "database_score": 87.5,
            "tables": {
                "orders": {
                    "completeness": 90, "validity": 80, "uniqueness": 100,
                    "consistency": 75, "timeliness": 60, "composite": 81,
                }
            },
        },
        "findings": [
            {
                "table": "orders", "column": "customer_id", "dimension": "consistency",
                "severity": "critical", "description": "orphaned FK", "evidence": {"orphan_count": 42},
            }
        ],
        "governance_summary": {"pii_columns_detected": [], "overrides_applied": []},
    }


def test_extract_json_object_from_plain_json() -> None:
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_object_tolerates_markdown_fence() -> None:
    text = 'Here you go:\n```json\n{"a": 1}\n```\n'
    assert _extract_json_object(text) == {"a": 1}


def test_extract_json_object_raises_on_non_json() -> None:
    with pytest.raises(AgentRunError):
        _extract_json_object("not json at all")


def test_mcp_tools_to_anthropic_translates_schema() -> None:
    tools = _mcp_tools_to_anthropic([_FakeTool("list_schemas", "List schemas", {"type": "object"})])
    assert tools == [{"name": "list_schemas", "description": "List schemas", "input_schema": {"type": "object"}}]


def test_summarize_tool_result_truncates_long_payloads() -> None:
    summary = _summarize_tool_result({"x": "y" * 300})
    assert len(summary) <= 200 + len("...(truncated for display)")
    assert summary.endswith("...(truncated for display)")


def test_validate_findings_accepts_conformant_payload() -> None:
    validate_findings(_valid_findings())  # must not raise


def test_validate_findings_rejects_invalid_dimension() -> None:
    bad = _valid_findings()
    bad["findings"][0]["dimension"] = "not_a_real_dimension"
    with pytest.raises(AgentRunError):
        validate_findings(bad)


def test_validate_findings_rejects_missing_required_field() -> None:
    bad = _valid_findings()
    del bad["scorecard"]
    with pytest.raises(AgentRunError):
        validate_findings(bad)
