"""Integration tests against a real, disposable Postgres instance.

Unlike the rest of tests/, these need a live database - they exist to
catch exactly the class of bug that unit tests (which don't touch
Postgres at all) cannot: DEF-003 (information_schema.table_constraints
silently returns nothing for a non-owner role - PK/FK detection was
completely broken under the real least-privilege audit role until
fixed) and DEF-004 (a NULL query parameter used in two different
comparisons caused psycopg's AmbiguousParameter error) were both found
by running the real tools against a real `dq_audit_reader`-equivalent
role, not by reading the code.

Auto-skipped when DATABASE_URL isn't set (the default for a plain
`pytest tests/` run) - see db/README.md and docker-compose.yml to spin
up the target this file expects: a Postgres reachable at
DATABASE_URL, seeded via `db/seed/00_provision_role.sql` +
`db/seed/*.sql`, with DATABASE_URL/PG* pointing at the `dq_audit_reader`
role those scripts create (not the admin role that seeds them - see
db/README.md "Eval seeding role vs. the audit role").
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.getenv("DATABASE_URL") or os.getenv("PGHOST")),
    reason="No live Postgres configured (DATABASE_URL/PGHOST unset) - see db/README.md",
)


def test_inspect_schema_detects_primary_key_under_readonly_role() -> None:
    """DEF-003 regression test: PK/FK detection must work for a role
    that only has SELECT, not ownership, on the audited tables."""
    from mcp_server.tools.schema_tools import inspect_schema

    result = inspect_schema("eval_nulls_and_dupes")
    customers = next(t for t in result["tables"] if t["table_name"] == "customers")
    id_column = next(c for c in customers["columns"] if c["column_name"] == "id")
    assert id_column["is_primary_key"] is True


def test_check_referential_integrity_finds_the_seeded_orphan() -> None:
    """DEF-003 + DEF-004 regression test: FK listing must see the
    constraint under a non-owner role, and the table=None case must
    not raise psycopg.errors.AmbiguousParameter."""
    from mcp_server.tools.integrity_tools import check_referential_integrity

    result = check_referential_integrity("eval_orphaned_fk")
    assert result["foreign_keys_checked"] == 1
    assert len(result["orphaned_fk_findings"]) == 1
    finding = result["orphaned_fk_findings"][0]
    assert finding["table"] == "orders"
    assert finding["column"] == "customer_id"
    assert finding["orphan_count"] == 1


def test_profile_table_and_check_duplicates_match_golden_counts() -> None:
    from mcp_server.tools.integrity_tools import check_duplicates
    from mcp_server.tools.profiling_tools import profile_table

    profiles = profile_table(
        "eval_nulls_and_dupes", "customers", ["full_name", "signup_date", "email"]
    )["column_profiles"]
    by_column = {p["column"]: p for p in profiles}
    assert by_column["full_name"]["null_rows"] == 2
    assert by_column["signup_date"]["null_rows"] == 1
    assert by_column["email"]["null_rows"] == 0

    dupes = check_duplicates("eval_nulls_and_dupes", "customers", ["email"])
    assert dupes["duplicate_key_count"] == 1


def test_detect_pii_flags_both_name_hinted_and_pattern_only_columns() -> None:
    from mcp_server.tools.pii_tools import detect_pii

    result = detect_pii("eval_pii_column", "support_tickets")
    by_column = {f["column"]: f for f in result["pii_findings"]}
    assert by_column["customer_email"]["category"] == "email"
    assert by_column["notes"]["category"] in ("phone", "email")  # value-pattern-only, no name hint


def test_run_readonly_query_masks_pii_and_never_leaks_raw_values() -> None:
    from mcp_server.tools.query_tools import run_readonly_query

    result = run_readonly_query(
        "select customer_email, notes from eval_pii_column.support_tickets",
        schema="eval_pii_column",
    )
    assert result["pii_columns_masked"]  # something got classified
    raw_transcript = str(result)
    known_raw_values = [
        "grace.green@example.test", "heidi.hill@example.test", "555-010-1111", "555-010-2222",
    ]
    for value in known_raw_values:
        assert value not in raw_transcript


def test_schema_allowlist_rejects_out_of_scope_schema(monkeypatch) -> None:
    from dataclasses import replace

    from mcp_server.tools import governance as governance_module
    from mcp_server.tools.governance import SchemaNotAllowedError
    from mcp_server.tools.schema_tools import inspect_schema

    isolated = replace(governance_module.settings, allowed_schemas=("eval_stale_data",))
    monkeypatch.setattr(governance_module, "settings", isolated)

    with pytest.raises(SchemaNotAllowedError):
        inspect_schema("eval_pii_column")
