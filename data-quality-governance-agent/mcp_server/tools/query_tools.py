"""Agent-composed read-only query tool (FR-120/121, NFR-201/202).

This is the most powerful and most guarded tool: it lets the agent run
SQL it composed itself, which is what makes the audit adaptive rather
than a fixed checklist. Every guardrail in governance.py/db.py applies
- SELECT-only AST check, schema allowlist, row cap, statement timeout,
PII masking, audit log.
"""
from __future__ import annotations

from typing import Any

from mcp_server.tools.governance import governed_select


def run_readonly_query(
    sql: str,
    schema: str | None = None,
    row_limit: int | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute a single agent-composed SELECT statement against the
    audited database and return the (PII-masked, row-capped) result.

    Args:
        sql: A single SELECT/WITH statement. Anything else is rejected.
        schema: Optional schema this query targets, checked against the
            allowlist before execution.
        row_limit: Optional per-call override of DQ_MAX_ROWS (capped at
            the configured maximum, never raised beyond it).
    """
    from mcp_server.config import settings

    effective_limit = min(row_limit, settings.max_rows) if row_limit else settings.max_rows
    result = governed_select(
        "run_readonly_query",
        sql,
        row_limit=effective_limit,
        schema=schema,
        run_id=run_id,
    )
    return {
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "pii_columns_masked": result.pii_columns,
        "duration_ms": round(result.duration_ms, 2),
    }
