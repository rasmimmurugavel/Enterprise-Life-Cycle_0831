"""Unit tests for the read-only AST guard and identifier quoting
(NFR-201, DEF-001 / EC-001). No database connection required - these
test the SQL-text-level logic in isolation."""
from __future__ import annotations

import pytest
import sqlglot
from sqlglot import exp

from mcp_server.tools.db import NotReadOnlyError, assert_select_only, quote_ident


@pytest.mark.parametrize(
    "sql",
    [
        "select 1",
        "select * from t",
        "with x as (select 1) select * from x",
        "select 1 union select 2",
    ],
)
def test_accepts_select_like_statements(sql: str) -> None:
    assert_select_only(sql)  # must not raise


@pytest.mark.parametrize(
    "sql",
    [
        "select 1; select 2",  # multi-statement
        "delete from t",
        "insert into t values (1)",
        "drop table t",
        "update t set x = 1",
        "truncate table t",
        "with x as (delete from t returning *) select * from x",  # DML hidden in a CTE
        "select from where",  # unparseable
    ],
)
def test_rejects_non_select_or_hidden_dml(sql: str) -> None:
    with pytest.raises(NotReadOnlyError):
        assert_select_only(sql)


def test_quote_ident_escapes_embedded_quotes() -> None:
    assert quote_ident("simple") == '"simple"'
    assert quote_ident('has"quote') == '"has""quote"'


def test_quote_ident_neutralizes_injection() -> None:
    """DEF-001 / EC-001: a naive f'"{name}"' interpolation lets a
    maliciously-named column splice an expression into the query.
    quote_ident must make that impossible - the whole payload should
    collapse into a single literal Identifier, not executable syntax."""
    malicious_column = 'x" or pg_sleep(999) --'

    naive_sql = f'select "{malicious_column}" from t'
    parsed_naive = sqlglot.parse_one(naive_sql, read="postgres")
    # Prove the vulnerability is real: the naive version actually
    # contains an injected function call, not just a weird column name.
    assert any(
        isinstance(node, exp.Anonymous) and node.this.lower() == "pg_sleep"
        for node in parsed_naive.walk()
    )

    safe_sql = f"select {quote_ident(malicious_column)} from t"
    assert_select_only(safe_sql)  # must not raise - it's still one valid SELECT
    parsed_safe = sqlglot.parse_one(safe_sql, read="postgres")
    column = parsed_safe.expressions[0]
    assert isinstance(column, exp.Column)
    assert column.this.this == malicious_column  # entire payload is one literal identifier
    # No function call anywhere in the safely-quoted version.
    assert not any(isinstance(node, exp.Anonymous) for node in parsed_safe.walk())
