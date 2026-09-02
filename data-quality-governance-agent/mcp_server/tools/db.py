"""Database access layer.

Isolates all Postgres-specific SQL behind a small `DBAdapter`
interface (NFR-210) so the tool logic in the rest of `mcp_server/`
never imports `psycopg` directly. A second engine later means a new
adapter implementing the same interface, not a rewrite of the tools.

Every read goes through `run_select`, which is the single choke point
that enforces: READ ONLY transaction, statement_timeout, and rejects
anything that isn't exactly one SELECT statement (NFR-201).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg
import sqlglot
from psycopg.rows import dict_row

from mcp_server.config import settings


class NotReadOnlyError(Exception):
    """Raised when the agent-composed SQL is not a single read-only SELECT."""


def quote_ident(name: str) -> str:
    """Safely quote a single Postgres identifier (schema/table/column
    name) for interpolation into SQL text.

    Every tool that builds SQL from an agent-supplied identifier
    (profiling_tools.py, integrity_tools.py, pii_tools.py) MUST go
    through this - a bare f'"{name}"' is not safe. Those names
    ultimately come from real database metadata, but they arrive at
    the query-building call sites as plain tool-call arguments the
    agent supplies, indistinguishable at that point from anything
    else the model might produce; a column legitimately named
    something like `x" or pg_sleep(999) --` (unusual, but a valid
    Postgres identifier if quoted at creation) would, under naive
    f'"{name}"' interpolation, close the identifier early and splice
    an arbitrary boolean expression into the query - a single SELECT
    statement, so it would NOT be caught by assert_select_only's
    statement-type/forbidden-node AST check, which guards against
    non-SELECT statements, not against identifier injection within an
    otherwise-valid SELECT.

    The standard SQL fix is doubling any embedded double-quote so it
    is treated as a literal character of the identifier rather than a
    terminator - this makes it impossible to break out of the quoted
    identifier regardless of content.
    """
    return '"' + name.replace('"', '""') + '"'


class QueryResult(Protocol):
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    duration_ms: float


@dataclass
class SelectResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    duration_ms: float
    row_count: int


def assert_select_only(sql: str) -> None:
    """AST-level guard: exactly one statement, and it must be a SELECT/WITH.

    This is deliberately not a string/regex check (NFR-201) - a check
    like `"insert" not in sql.lower()` is trivially defeated by a CTE
    named "insert_summary" or a comment. Parsing the statement into an
    AST and checking its node type is not.
    """
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as exc:  # noqa: BLE001 - surface parser errors as governance rejections
        raise NotReadOnlyError(f"Could not parse SQL as a valid statement: {exc}") from exc

    if len(statements) != 1 or statements[0] is None:
        raise NotReadOnlyError("Exactly one SQL statement is allowed per call.")

    root = statements[0]
    allowed_root_types = (sqlglot.exp.Select, sqlglot.exp.Union, sqlglot.exp.With)
    if not isinstance(root, allowed_root_types):
        raise NotReadOnlyError(
            f"Only SELECT/WITH/UNION statements are permitted; got {type(root).__name__}."
        )

    # Reject any write/DDL expression appearing anywhere in the tree,
    # e.g. a data-modifying CTE such as `WITH x AS (DELETE FROM ... RETURNING *) SELECT * FROM x`.
    forbidden_types = (
        sqlglot.exp.Insert,
        sqlglot.exp.Update,
        sqlglot.exp.Delete,
        sqlglot.exp.Drop,
        sqlglot.exp.Create,
        sqlglot.exp.Alter,
        sqlglot.exp.TruncateTable,
        sqlglot.exp.Merge,
        sqlglot.exp.Grant,
    )
    for node in root.walk():
        if isinstance(node, forbidden_types):
            raise NotReadOnlyError(
                f"Statement contains a forbidden {type(node).__name__} operation."
            )


class DBAdapter:
    """Postgres implementation. Construct one per MCP server process."""

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or settings.dsn()

    def run_select(self, sql: str, params: dict[str, Any] | None = None,
                   row_limit: int | None = None) -> SelectResult:
        assert_select_only(sql)
        limit = row_limit or settings.max_rows

        started = time.monotonic()
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")
                cur.execute(sql, params or {})
                columns = [desc.name for desc in cur.description] if cur.description else []
                rows = cur.fetchmany(limit + 1)
                truncated = len(rows) > limit
                if truncated:
                    rows = rows[:limit]
        duration_ms = (time.monotonic() - started) * 1000
        return SelectResult(
            columns=columns,
            rows=rows,
            truncated=truncated,
            duration_ms=duration_ms,
            row_count=len(rows),
        )

    def check_role_privileges(self) -> dict[str, Any]:
        """FR-102: verify the connected role cannot write. Warn, don't trust, if it can."""
        sql = """
            select
                has_database_privilege(current_user, current_database(), 'CREATE') as can_create_db,
                (select bool_or(has_table_privilege(current_user, c.oid, 'INSERT'))
                     from pg_class c join pg_namespace n on n.oid = c.relnamespace
                     where c.relkind = 'r' and n.nspname not in ('pg_catalog','information_schema')) as can_insert_any,
                (select bool_or(has_table_privilege(current_user, c.oid, 'UPDATE'))
                     from pg_class c join pg_namespace n on n.oid = c.relnamespace
                     where c.relkind = 'r' and n.nspname not in ('pg_catalog','information_schema')) as can_update_any,
                (select bool_or(has_table_privilege(current_user, c.oid, 'DELETE'))
                     from pg_class c join pg_namespace n on n.oid = c.relnamespace
                     where c.relkind = 'r' and n.nspname not in ('pg_catalog','information_schema')) as can_delete_any
        """
        result = self.run_select(sql)
        return result.rows[0] if result.rows else {}
