"""Append-only JSONL audit logger (FR-140/141, BR-06).

Every MCP tool call is written here before its result is returned to
the agent - independent of what the agent later chooses to put in a
findings report. This file is the source of truth for "what did the
agent actually do" (NFR-208) and is designed to be shipped to an
enterprise SIEM/log pipeline unmodified.

Never write raw PII here: callers pass already-governed (masked,
row-capped) summaries, never the row payload itself.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mcp_server.config import settings

_lock = threading.Lock()


@dataclass
class AuditEntry:
    tool: str
    args: dict[str, Any]
    row_count: int | None = None
    truncated: bool | None = None
    duration_ms: float | None = None
    status: str = "ok"
    error: str | None = None
    run_id: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_json(self) -> str:
        return json.dumps(self.__dict__, default=str, separators=(",", ":"))


def _log_path() -> str:
    return settings.audit_log_path


def append(entry: AuditEntry) -> None:
    path = _log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = entry.to_json() + "\n"
    with _lock:
        # Append-only open mode: this process never opens the log for
        # write/truncate, only ever "a" (FR-141).
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)


def read_recent(limit: int = 200, tool: str | None = None,
                 since_iso: str | None = None) -> list[dict[str, Any]]:
    path = _log_path()
    if not os.path.exists(path):
        return []
    entries: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if tool and record.get("tool") != tool:
                continue
            if since_iso and record.get("timestamp", "") < since_iso:
                continue
            entries.append(record)
    return entries[-limit:]


class timed_tool_call:
    """Context manager that times a tool call and logs it on exit.

    Usage:
        with timed_tool_call("profile_table", args, run_id=run_id) as t:
            result = ...
            t.row_count = len(result.rows)
            t.truncated = result.truncated
    """

    def __init__(self, tool: str, args: dict[str, Any], run_id: str | None = None) -> None:
        self.tool = tool
        self.args = args
        self.run_id = run_id
        self.row_count: int | None = None
        self.truncated: bool | None = None
        self._start = 0.0

    def __enter__(self) -> "timed_tool_call":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        duration_ms = (time.monotonic() - self._start) * 1000
        entry = AuditEntry(
            tool=self.tool,
            args=self.args,
            row_count=self.row_count,
            truncated=self.truncated,
            duration_ms=round(duration_ms, 2),
            status="error" if exc else "ok",
            error=str(exc) if exc else None,
            run_id=self.run_id,
        )
        append(entry)
        return False  # never suppress exceptions
