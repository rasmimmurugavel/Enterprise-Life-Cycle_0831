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
            tc.table_schema,
            tc.table_name,
            kcu.column_name
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
            on tc.constraint_name = kcu.constraint_name
            and tc.table_schema = kcu.table_schema
        where tc.constraint_type = 'PRIMARY KEY' and tc.table_schema = %(schema)s
    ),
    fks as (
        select
            tc.table_schema as table_schema,
            tc.table_name as table_name,
            kcu.column_name as column_name,
            ccu.table_schema as ref_schema,
            ccu.table_name as ref_table,
            ccu.column_name as ref_column
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
            on tc.constraint_name = kcu.constraint_name and tc.table_schema = kcu.table_schema
        join information_schema.constraint_column_usage ccu
            on tc.constraint_name = ccu.constraint_name and tc.table_schema = ccu.table_schema
        where tc.constraint_type = 'FOREIGN KEY' and tc.table_schema = %(schema)s
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
