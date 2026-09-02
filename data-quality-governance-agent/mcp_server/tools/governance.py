"""Cross-cutting governance middleware applied to every MCP tool.

Every tool in mcp_server/tools/*_tools.py routes its DB access through
`governed_select`, which is the single place that:

  1. Checks the schema allowlist (FR-103).
  2. Executes the query as a bounded, read-only SELECT (via db.DBAdapter,
     NFR-201/202).
  3. Classifies and masks PII in the result before it leaves this
     process (FR-130, NFR-204) - this happens unconditionally, not
     only inside the dedicated `detect_pii` tool, so no other tool can
     become an accidental PII-exfiltration path.
  4. Writes one audit log entry per call (FR-140/141).

Tool modules should never call `DBAdapter.run_select` directly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from mcp_server.config import settings
from mcp_server.tools.audit_log import timed_tool_call
from mcp_server.tools.db import DBAdapter
from mcp_server.tools.pii import classify_columns, mask_row

_db = DBAdapter()


class SchemaNotAllowedError(Exception):
    pass


@dataclass
class GovernedResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    duration_ms: float
    pii_columns: dict[str, str]


def new_run_id() -> str:
    return str(uuid.uuid4())


def require_schema_allowed(schema: str) -> None:
    if not settings.is_schema_allowed(schema):
        raise SchemaNotAllowedError(
            f"Schema '{schema}' is not in DQ_ALLOWED_SCHEMAS "
            f"({', '.join(settings.allowed_schemas) or '(all allowed)'})."
        )


def governed_select(
    tool_name: str,
    sql: str,
    params: dict[str, Any] | None = None,
    row_limit: int | None = None,
    schema: str | None = None,
    run_id: str | None = None,
    mask_pii: bool = True,
) -> GovernedResult:
    """The single choke point every tool routes through.

    Raises SchemaNotAllowedError / NotReadOnlyError before touching the
    database if governance checks fail; those raised calls are still
    audit-logged (status="error") by `timed_tool_call`.
    """
    if schema is not None:
        require_schema_allowed(schema)

    args_for_log = {"sql": sql, "schema": schema, "row_limit": row_limit}
    with timed_tool_call(tool_name, args_for_log, run_id=run_id) as t:
        result = _db.run_select(sql, params=params, row_limit=row_limit)
        pii_columns = classify_columns(result.columns, result.rows) if mask_pii else {}
        rows = (
            [mask_row(row, pii_columns) for row in result.rows]
            if pii_columns
            else result.rows
        )
        t.row_count = result.row_count
        t.truncated = result.truncated

    return GovernedResult(
        columns=result.columns,
        rows=rows,
        row_count=result.row_count,
        truncated=result.truncated,
        duration_ms=result.duration_ms,
        pii_columns=pii_columns,
    )
