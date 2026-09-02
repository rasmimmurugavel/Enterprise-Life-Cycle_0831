"""Table/column profiling tool (FR-120, BR-03).

Computes the standard data-quality baseline the agent always runs
before it decides what else to investigate: null rate, distinct count,
min/max, and (for low-cardinality columns) a top-N value distribution.
All aggregates - no raw rows are returned by this tool, so it never
needs PII masking on its own output; it still routes through
governed_select for the audit log and schema allowlist check.
"""
from __future__ import annotations

from typing import Any

from mcp_server.tools.db import quote_ident
from mcp_server.tools.governance import governed_select, require_schema_allowed


def profile_table(schema: str, table: str, columns: list[str], run_id: str | None = None) -> dict[str, Any]:
    """Profile the given columns of one table.

    Args:
        schema: Schema containing the table (checked against the allowlist).
        table: Table name.
        columns: Column names to profile (from a prior inspect_schema call).
    """
    require_schema_allowed(schema)
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"

    profiles: list[dict[str, Any]] = []
    for column in columns:
        col_ident = quote_ident(column)
        sql = f"""
            select
                count(*) as total_rows,
                count({col_ident}) as non_null_rows,
                count(*) - count({col_ident}) as null_rows,
                count(distinct {col_ident}) as distinct_values,
                min({col_ident}::text) as min_value,
                max({col_ident}::text) as max_value
            from {qualified}
        """
        result = governed_select(
            "profile_table.aggregate",
            sql,
            schema=schema,
            run_id=run_id,
            mask_pii=False,  # aggregates only (counts/min/max), not raw rows
            row_limit=1,
        )
        row = result.rows[0] if result.rows else {}
        total = row.get("total_rows") or 0
        null_rows = row.get("null_rows") or 0
        profiles.append(
            {
                "column": column,
                "total_rows": total,
                "null_rows": null_rows,
                "null_rate": round(null_rows / total, 4) if total else 0.0,
                "distinct_values": row.get("distinct_values"),
                "min_value": row.get("min_value"),
                "max_value": row.get("max_value"),
            }
        )

    return {"schema": schema, "table": table, "column_profiles": profiles}


def top_values(schema: str, table: str, column: str, limit: int = 10, run_id: str | None = None) -> dict[str, Any]:
    """Return the top-N most frequent values and their counts for a
    column - useful for spotting unexpected categorical drift (e.g. a
    'status' column with a typo'd duplicate value). Values themselves
    are subject to PII masking like any other tool output."""
    require_schema_allowed(schema)
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
    col_ident = quote_ident(column)
    sql = f"""
        select {col_ident} as value, count(*) as frequency
        from {qualified}
        where {col_ident} is not null
        group by {col_ident}
        order by frequency desc
        limit %(limit)s
    """
    result = governed_select(
        "profile_table.top_values",
        sql,
        params={"limit": limit},
        schema=schema,
        run_id=run_id,
        row_limit=limit,
    )
    return {
        "schema": schema,
        "table": table,
        "column": column,
        "top_values": result.rows,
        "pii_masked": bool(result.pii_columns),
    }
