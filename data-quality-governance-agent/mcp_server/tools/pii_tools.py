"""Explicit PII-scan tool (FR-130/131).

Unlike governance.py's always-on masking (which protects every tool's
output), this tool is what the agent calls when it wants a direct
answer to "is this column PII, and how confident should I be" -
sampling a bounded number of rows, classifying, and returning only the
category + hit-rate summary. The sampled raw values never leave this
function.
"""
from __future__ import annotations

from typing import Any

from mcp_server.config import settings
from mcp_server.tools.audit_log import timed_tool_call
from mcp_server.tools.db import DBAdapter, quote_ident
from mcp_server.tools.governance import require_schema_allowed
from mcp_server.tools.pii import classify_columns, column_name_hint, scan_values

_db = DBAdapter()


def detect_pii(schema: str, table: str, columns: list[str] | None = None,
                run_id: str | None = None) -> dict[str, Any]:
    """Sample rows from `table` and classify which columns look like PII.

    Args:
        schema: Schema containing the table (checked against the allowlist).
        table: Table to sample.
        columns: Columns to check; defaults to all columns in the sample.
    """
    require_schema_allowed(schema)
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
    col_clause = ", ".join(quote_ident(c) for c in columns) if columns else "*"
    sql = f"select {col_clause} from {qualified} limit %(n)s"

    args_for_log = {"schema": schema, "table": table, "columns": columns}
    with timed_tool_call("detect_pii", args_for_log, run_id=run_id) as t:
        result = _db.run_select(sql, params={"n": settings.pii_sample_rows},
                                 row_limit=settings.pii_sample_rows)
        t.row_count = result.row_count
        t.truncated = False  # sampling is intentional, not a governance truncation

    classified = classify_columns(result.columns, result.rows)

    findings = []
    for column in result.columns:
        category = classified.get(column)
        name_hint = column_name_hint(column)
        if not category and not name_hint:
            continue
        values = [row.get(column) for row in result.rows]
        value_matches = scan_values([str(v) for v in values if v is not None])
        hit_rate = next((m.hit_rate for m in value_matches if m.category == category), 0.0)
        findings.append(
            {
                "column": column,
                "category": category or name_hint,
                "detected_by": "value_pattern" if category else "column_name",
                "sample_hit_rate": hit_rate,
                "sample_size": settings.pii_sample_rows,
            }
        )

    return {
        "schema": schema,
        "table": table,
        "rows_sampled": result.row_count,
        "pii_findings": findings,
    }
