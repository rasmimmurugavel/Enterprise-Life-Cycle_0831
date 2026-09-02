"""Audit log read-back tool (FR-142).

Lets the agent (or the Streamlit "Audit Log" view, which also reads
the file directly per HLD 2.1) answer "what have we already checked in
this run" without re-running expensive queries. This tool reads the
log file; it does not touch the target database.
"""
from __future__ import annotations

from typing import Any

from mcp_server.tools.audit_log import read_recent


def get_audit_log(limit: int = 200, tool: str | None = None,
                   since_iso: str | None = None) -> dict[str, Any]:
    """Return recent audit log entries, optionally filtered by tool name
    or an ISO-8601 timestamp lower bound."""
    entries = read_recent(limit=limit, tool=tool, since_iso=since_iso)
    return {"count": len(entries), "entries": entries}
