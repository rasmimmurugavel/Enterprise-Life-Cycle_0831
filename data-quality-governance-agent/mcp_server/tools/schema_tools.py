"""Schema inspection tools (FR-110/111/112)."""
from __future__ import annotations

from typing import Any

from mcp_server.tools.governance import governed_select, require_schema_allowed

_LIST_SCHEMAS_SQL = """
    select schema_name
    from information_schema.schemata
    where schema_name not in ('pg_catalog', 'information_schema', 'pg_toast')
    order by schema_name
"""

# One batched query per introspection call (FR-111) - never one round
# trip per table.
#
# PK/FK detection deliberately reads pg_catalog (pg_constraint/
# pg_attribute), NOT information_schema.table_constraints/
# key_column_usage/constraint_column_usage (DEF-003): those
# information_schema views are SQL-standard "administrative" views
# that Postgres only populates for constraints on tables the querying
# role OWNS - they silently return zero rows for a plain SELECT-only
# role auditing tables it doesn't own, which is this app's entire
# operating model (BR-01). information_schema.columns has no such
# restriction (it checks column-level privilege, not ownership), so
# it's kept for the column list. Verified live against a real
# dq_audit_reader role with no ownership - see
# 09-test-execution/Execution-Summary.md.
_INSPECT_SCHEMA_SQL = """
    with cols as (
        select
            c.table_schema,
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable = 'YES' as nullable,
            c.column_default,
            c.ordinal_position
        from information_schema.columns c
        where c.table_schema = %(schema)s
    ),
    pks as (
        select
            n.nspname as table_schema,
            c.relname as table_name,
            a.attname as column_name
        from pg_constraint con
        join pg_class c on c.oid = con.conrelid
        join pg_namespace n on n.oid = con.connamespace
        join unnest(con.conkey) as k(attnum) on true
        join pg_attribute a on a.attrelid = c.oid and a.attnum = k.attnum
        where con.contype = 'p' and n.nspname = %(schema)s
    ),
    fks as (
        select
            n.nspname as table_schema,
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
    )
    select
        cols.table_name,
        cols.column_name,
        cols.data_type,
        cols.nullable,
        cols.column_default,
        cols.ordinal_position,
        (pks.column_name is not null) as is_primary_key,
        fks.ref_schema as fk_ref_schema,
        fks.ref_table as fk_ref_table,
        fks.ref_column as fk_ref_column
    from cols
    left join pks
        on pks.table_schema = cols.table_schema
        and pks.table_name = cols.table_name
        and pks.column_name = cols.column_name
    left join fks
        on fks.table_schema = cols.table_schema
        and fks.table_name = cols.table_name
        and fks.column_name = cols.column_name
    order by cols.table_name, cols.ordinal_position
"""


def list_schemas(run_id: str | None = None) -> dict[str, Any]:
    """List database schemas visible to the configured role, filtered by
    DQ_ALLOWED_SCHEMAS when set."""
    result = governed_select("list_schemas", _LIST_SCHEMAS_SQL, run_id=run_id, mask_pii=False)
    from mcp_server.config import settings

    names = [row["schema_name"] for row in result.rows]
    if settings.allowed_schemas:
        names = [n for n in names if n in settings.allowed_schemas]
    return {"schemas": names}


def inspect_schema(schema: str, run_id: str | None = None) -> dict[str, Any]:
    """Return tables, columns, types, nullability, PK/FK for one schema
    in a single batched round trip."""
    require_schema_allowed(schema)
    result = governed_select(
        "inspect_schema",
        _INSPECT_SCHEMA_SQL,
        params={"schema": schema},
        schema=schema,
        run_id=run_id,
        mask_pii=False,  # metadata only - no row values, nothing to mask
        row_limit=5000,
    )

    tables: dict[str, dict[str, Any]] = {}
    for row in result.rows:
        table = tables.setdefault(
            row["table_name"], {"table_name": row["table_name"], "columns": []}
        )
        table["columns"].append(
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "nullable": row["nullable"],
                "default": row["column_default"],
                "is_primary_key": row["is_primary_key"],
                "foreign_key": (
                    {
                        "ref_schema": row["fk_ref_schema"],
                        "ref_table": row["fk_ref_table"],
                        "ref_column": row["fk_ref_column"],
                    }
                    if row["fk_ref_table"]
                    else None
                ),
            }
        )
    return {"schema": schema, "tables": list(tables.values()), "truncated": result.truncated}
