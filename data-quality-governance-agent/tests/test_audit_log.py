"""Unit tests for the append-only audit logger (FR-140/141, NFR-208).
Uses a temp file for the log path - no database connection required."""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

from mcp_server.tools import audit_log as audit_log_module
from mcp_server.tools.audit_log import read_recent, timed_tool_call


@pytest.fixture(autouse=True)
def _isolated_log_path(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.jsonl"
    # settings is a frozen dataclass singleton; replace() gives a copy
    # with just audit_log_path overridden, then swap the module-level
    # reference audit_log.py actually reads from.
    isolated_settings = replace(audit_log_module.settings, audit_log_path=str(log_path))
    monkeypatch.setattr(audit_log_module, "settings", isolated_settings)
    return log_path


def test_successful_call_is_logged_with_row_count(_isolated_log_path) -> None:
    with timed_tool_call("profile_table", {"schema": "public", "table": "orders"}, run_id="run-1") as t:
        t.row_count = 42
        t.truncated = False

    entries = read_recent()
    assert len(entries) == 1
    assert entries[0]["tool"] == "profile_table"
    assert entries[0]["status"] == "ok"
    assert entries[0]["row_count"] == 42
    assert entries[0]["run_id"] == "run-1"


def test_failed_call_is_logged_with_error_and_reraises(_isolated_log_path) -> None:
    with pytest.raises(ValueError):
        with timed_tool_call("run_readonly_query", {"sql": "select 1"}) as _t:
            raise ValueError("boom")

    entries = read_recent()
    assert len(entries) == 1
    assert entries[0]["status"] == "error"
    assert "boom" in entries[0]["error"]


def test_read_recent_filters_by_tool(_isolated_log_path) -> None:
    with timed_tool_call("list_schemas", {}):
        pass
    with timed_tool_call("profile_table", {"table": "orders"}):
        pass

    only_profile = read_recent(tool="profile_table")
    assert len(only_profile) == 1
    assert only_profile[0]["tool"] == "profile_table"


def test_log_file_is_only_ever_appended_to(_isolated_log_path) -> None:
    for i in range(3):
        with timed_tool_call("list_schemas", {"i": i}):
            pass

    with open(_isolated_log_path, encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) == 3  # one JSON object per line, nothing overwritten

    # A 4th call must add a 4th line, not replace the first three.
    with timed_tool_call("list_schemas", {"i": 3}):
        pass
    with open(_isolated_log_path, encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) == 4


def test_source_never_opens_log_in_write_mode() -> None:
    """Static check backing FR-141: append-only from the app's
    perspective means the code never opens the log with 'w'/'w+'."""
    source_path = os.path.join(os.path.dirname(audit_log_module.__file__), "audit_log.py")
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    assert 'open(path, "a"' in source
    assert 'open(path, "w"' not in source
    assert 'open(path, "w+"' not in source
