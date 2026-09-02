"""Unit tests for PII detection and masking (FR-130/131, NFR-204).
No database connection required."""
from __future__ import annotations

from mcp_server.tools.pii import classify_columns, column_name_hint, mask_row, mask_value, scan_values


def test_column_name_hint_matches_common_patterns() -> None:
    assert column_name_hint("customer_email") == "email"
    assert column_name_hint("phone_number") == "phone"
    assert column_name_hint("ssn") == "ssn_or_national_id"
    assert column_name_hint("full_name") == "name"
    assert column_name_hint("order_total") is None


def test_scan_values_detects_email_pattern_above_threshold() -> None:
    values = ["a@example.test", "b@example.test", "not an email", "c@example.test"]
    matches = scan_values(values)
    categories = {m.category for m in matches}
    assert "email" in categories


def test_scan_values_ignores_rare_matches_below_threshold() -> None:
    # 1 email-shaped value out of 100 plain strings is well below the
    # default 5% threshold - should not be flagged.
    values = ["plain text"] * 99 + ["a@example.test"]
    matches = scan_values(values)
    assert matches == []


def test_classify_columns_prefers_name_hint_but_falls_back_to_value_pattern() -> None:
    rows = [
        {"customer_email": "a@example.test", "notes": "call 555-010-1111"},
        {"customer_email": "b@example.test", "notes": "call 555-010-2222"},
        {"customer_email": "c@example.test", "notes": "no issue"},
    ]
    classified = classify_columns(["customer_email", "notes"], rows)
    assert classified["customer_email"] == "email"  # via name hint
    assert classified["notes"] == "phone"  # via value pattern only, no name hint


def test_mask_row_never_leaks_original_value() -> None:
    row = {"id": 1, "email": "jane.doe@example.test", "notes": "vip"}
    masked = mask_row(row, {"email": "email"})
    assert masked["email"] != row["email"]
    assert "jane.doe" not in masked["email"]
    assert masked["notes"] == "vip"  # untouched, not classified as PII
    assert masked["id"] == 1


def test_mask_value_handles_none_and_short_strings() -> None:
    assert mask_value(None) == "NULL"
    assert mask_value("") == ""
    assert mask_value("ab") == "**"


def test_mask_value_email_keeps_shape_not_content() -> None:
    masked = mask_value("jane.doe@example.test", category="email")
    assert masked.startswith("j")
    assert "jane.doe" not in masked
    assert "example.test" not in masked
