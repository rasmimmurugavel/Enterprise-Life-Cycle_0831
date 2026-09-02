"""Data Quality & Governance MCP server (FR-150/151).

Standalone MCP server exposing read-only Postgres data-quality tools
over stdio. Launchable independently of Streamlit:

    python -m mcp_server.server

so any MCP-compatible client - Claude Code, Claude Desktop, or this
repo's own `app/agent.py` - can attach to the same tool surface without
a second, hand-maintained copy of the tool contract.

Tool docstrings and type hints below ARE the tool schema FastMCP
exposes to clients (FR-151) - keep them accurate, they are what the
agent reads to decide how to call each tool.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.audit_tools import get_audit_log as _get_audit_log
from mcp_server.tools.governance import new_run_id
from mcp_server.tools.integrity_tools import check_duplicates as _check_duplicates
from mcp_server.tools.integrity_tools import (
    check_referential_integrity as _check_referential_integrity,
)
from mcp_server.tools.pii_tools import detect_pii as _detect_pii
from mcp_server.tools.profiling_tools import profile_table as _profile_table
from mcp_server.tools.profiling_tools import top_values as _top_values
from mcp_server.tools.query_tools import run_readonly_query as _run_readonly_query
from mcp_server.tools.schema_tools import inspect_schema as _inspect_schema
from mcp_server.tools.schema_tools import list_schemas as _list_schemas

mcp = FastMCP(
    name="data-quality-governance",
    instructions=(
        "Read-only PostgreSQL data quality and governance tools. Every call is "
        "row-capped, timeout-capped, restricted to the configured schema "
        "allowlist, and appended to an audit log. PII-shaped values are masked "
        "before they are returned - never ask for or expect raw PII in a "
        "result. Typical audit flow: list_schemas -> inspect_schema -> "
        "profile_table + check_referential_integrity + detect_pii per table -> "
        "run_readonly_query for anything the fixed tools don't cover."
    ),
)

# A single run_id groups every tool call made during one Streamlit
# "Run Audit" click in the audit log, without requiring the agent to
# pass it on every call.
_current_run_id: str = new_run_id()


def set_run_id(run_id: str) -> None:
    global _current_run_id
    _current_run_id = run_id


@mcp.tool()
def list_schemas() -> dict[str, Any]:
    """List database schemas visible to the configured role, filtered by
    the DQ_ALLOWED_SCHEMAS allowlist when one is configured. Always the
    first call of an audit."""
    return _list_schemas(run_id=_current_run_id)


@mcp.tool()
def inspect_schema(schema: str) -> dict[str, Any]:
    """Return every table's columns, data types, nullability, primary
    keys, and foreign keys for one schema, in a single batched call."""
    return _inspect_schema(schema, run_id=_current_run_id)


@mcp.tool()
def profile_table(schema: str, table: str, columns: list[str]) -> dict[str, Any]:
    """Compute the data-quality baseline for the given columns of one
    table: null rate, distinct value count, min/max. Aggregates only -
    never returns raw row values."""
    return _profile_table(schema, table, columns, run_id=_current_run_id)


@mcp.tool()
def top_values(schema: str, table: str, column: str, limit: int = 10) -> dict[str, Any]:
    """Return the most frequent values in one column and their counts -
    use this to spot unexpected categorical drift (typo'd duplicate
    categories, an unexpected default value dominating a column)."""
    return _top_values(schema, table, column, limit=limit, run_id=_current_run_id)


@mcp.tool()
def check_referential_integrity(schema: str, table: str | None = None) -> dict[str, Any]:
    """Scan declared foreign keys in a schema (optionally scoped to one
    table) for orphaned references - child rows whose FK value has no
    matching parent row."""
    return _check_referential_integrity(schema, table=table, run_id=_current_run_id)


@mcp.tool()
def check_duplicates(schema: str, table: str, columns: list[str]) -> dict[str, Any]:
    """Check whether the given columns (typically a declared primary key
    or unique constraint) actually hold unique values across all rows."""
    return _check_duplicates(schema, table, columns, run_id=_current_run_id)


@mcp.tool()
def detect_pii(schema: str, table: str, columns: list[str] | None = None) -> dict[str, Any]:
    """Sample rows from a table and classify which columns look like PII
    (email, phone, SSN/national ID, card number, name, address, DOB, IP).
    Returns only category + hit-rate per column - raw sampled values
    never leave this tool."""
    return _detect_pii(schema, table, columns=columns, run_id=_current_run_id)


@mcp.tool()
def run_readonly_query(sql: str, schema: str | None = None, row_limit: int | None = None) -> dict[str, Any]:
    """Run a single agent-composed SELECT statement for anything the
    fixed tools above don't cover. Rejected if it is not exactly one
    SELECT/WITH statement, if it targets a schema outside the
    allowlist, or if it would return more than the configured row cap.
    Results are PII-masked like every other tool."""
    return _run_readonly_query(sql, schema=schema, row_limit=row_limit, run_id=_current_run_id)


@mcp.tool()
def get_audit_log(limit: int = 200, tool: str | None = None, since_iso: str | None = None) -> dict[str, Any]:
    """Read back recent entries from this server's own audit log -
    useful for confirming what has already been checked in the current
    run before deciding what to do next."""
    return _get_audit_log(limit=limit, tool=tool, since_iso=since_iso)


if __name__ == "__main__":
    mcp.run(transport="stdio")
