"""Referential integrity and uniqueness checks (FR-120, BR-03).

Orphaned foreign keys and duplicate values on declared unique/PK
columns are two of the highest-signal, cheapest-to-compute data
quality defects - they indicate either a broken ETL pipeline or a
missing constraint, and they're exactly the kind of thing a human
reviewer expects an audit to already have checked before they open a
ticket.
"""
from __future__ import annotations

from typing import Any

from mcp_server.tools.db import quote_ident
from mcp_server.tools.governance import governed_select, require_schema_allowed

_FK_LIST_SQL = """
    select
        tc.table_name,
        kcu.column_name,
        ccu.table_schema as ref_schema,
        ccu.table_name as ref_table,
        ccu.column_name as ref_column
    from information_schema.table_constraints tc
    join information_schema.key_column_usage kcu
        on tc.constraint_name = kcu.constraint_name and tc.table_schema = kcu.table_schema
    join information_schema.constraint_column_usage ccu
        on tc.constraint_name = ccu.constraint_name and tc.table_schema = ccu.table_schema
    where tc.constraint_type = 'FOREIGN KEY' and tc.table_schema = %(schema)s
      and (%(table)s is null or tc.table_name = %(table)s)
"""


def check_referential_integrity(schema: str, table: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    """Scan declared foreign keys in `schema` (optionally scoped to one
    `table`) for orphaned references - rows whose FK value has no
    matching row in the referenced table."""
    require_schema_allowed(schema)
    fk_result = governed_select(
        "check_referential_integrity.list_fks",
        _FK_LIST_SQL,
        params={"schema": schema, "table": table},
        schema=schema,
        run_id=run_id,
        mask_pii=False,
    )

    findings: list[dict[str, Any]] = []
    for fk in fk_result.rows:
        child = f"{quote_ident(schema)}.{quote_ident(fk['table_name'])}"
        parent = f"{quote_ident(fk['ref_schema'])}.{quote_ident(fk['ref_table'])}"
        child_col = quote_ident(fk["column_name"])
        parent_col = quote_ident(fk["ref_column"])
        sql = f"""
            select count(*) as orphan_count
            from {child} c
            where c.{child_col} is not null
              and not exists (
                  select 1 from {parent} p where p.{parent_col} = c.{child_col}
              )
        """
        result = governed_select(
            "check_referential_integrity.orphan_count",
            sql,
            schema=schema,
            run_id=run_id,
            mask_pii=False,
            row_limit=1,
        )
        orphan_count = (result.rows[0]["orphan_count"] if result.rows else 0) or 0
        if orphan_count > 0:
            findings.append(
                {
                    "table": fk["table_name"],
                    "column": fk["column_name"],
                    "references": f"{fk['ref_schema']}.{fk['ref_table']}.{fk['ref_column']}",
                    "orphan_count": orphan_count,
                }
            )

    return {"schema": schema, "foreign_keys_checked": len(fk_result.rows), "orphaned_fk_findings": findings}


def check_duplicates(schema: str, table: str, columns: list[str], run_id: str | None = None) -> dict[str, Any]:
    """Check whether `columns` (typically a declared PK or unique
    constraint) actually holds unique values - a duplicate here means
    either a broken constraint or a load that bypassed it."""
    require_schema_allowed(schema)
    qualified = f"{quote_ident(schema)}.{quote_ident(table)}"
    col_list = ", ".join(quote_ident(c) for c in columns)
    sql = f"""
        select count(*) as duplicate_key_count
        from (
            select {col_list}, count(*) as c
            from {qualified}
            group by {col_list}
            having count(*) > 1
        ) dupes
    """
    result = governed_select(
        "check_duplicates",
        sql,
        schema=schema,
        run_id=run_id,
        mask_pii=False,
        row_limit=1,
    )
    duplicate_key_count = (result.rows[0]["duplicate_key_count"] if result.rows else 0) or 0
    return {
        "schema": schema,
        "table": table,
        "columns": columns,
        "duplicate_key_count": duplicate_key_count,
    }
