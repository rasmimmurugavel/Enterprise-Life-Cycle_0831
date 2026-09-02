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

# pg_catalog, not information_schema.table_constraints/key_column_usage/
# constraint_column_usage - see the long comment in schema_tools.py's
# _INSPECT_SCHEMA_SQL (DEF-003): those information_schema views only
# show constraints on tables the querying role owns, which silently
# breaks referential-integrity auditing for exactly the least-privilege
# read-only role this app is designed to use.
_FK_LIST_SQL = """
    select
        c.relname as table_name,
        a.attname as column_name,
        fn.nspname as ref_schema,
        fc.relname as ref_table,
        fa.attname as ref_column
    from pg_constraint con
    join pg_class c on c.oid = con.conrelid
    join pg_namespace n on n.oid = con.connamespace
    join pg_class fc on fc.oid = con.confrelid
    join pg_namespace fn on fn.oid = fc.relnamespace
    join unnest(con.conkey, con.confkey) as k(attnum, fattnum) on true
    join pg_attribute a on a.attrelid = c.oid and a.attnum = k.attnum
    join pg_attribute fa on fa.attrelid = fc.oid and fa.attnum = k.fattnum
    where con.contype = 'f' and n.nspname = %(schema)s
      and (%(table)s::text is null or c.relname = %(table)s::text)
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
