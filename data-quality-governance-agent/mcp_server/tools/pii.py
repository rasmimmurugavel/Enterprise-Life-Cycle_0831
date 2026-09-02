"""PII detection and masking (FR-130/131, NFR-204).

This module is the enforcement point for "no unmasked PII ever
reaches the LLM". It is deliberately independent of the agent/prompt
layer: masking happens here, in the governance middleware, before a
tool result is serialized - a prompt instruction telling Claude "don't
repeat PII" is not a control, this is.

Two detectors, both cheap and dependency-light by default:
  1. Column-name heuristics - fast, catches the common cases
     (email, ssn, phone, dob, name, address, card number) even when
     the column is currently empty or all-null.
  2. Value-pattern regexes - catches PII-shaped data in columns whose
     name gives no hint (e.g. a generically-named `notes` or `value`
     column that happens to contain emails).

`presidio-analyzer` (listed in requirements.txt) can be swapped in as
a third, higher-recall detector for production use; the interface
(`scan_values` returning `PIIMatch` objects) is designed so that swap
does not touch any caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from mcp_server.config import settings

# --- Column-name heuristics -------------------------------------------------

_NAME_HINTS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"e[-_]?mail", re.I),
    "phone": re.compile(r"phone|mobile|cell", re.I),
    "ssn_or_national_id": re.compile(r"ssn|national[-_]?id|passport|tax[-_]?id", re.I),
    "name": re.compile(r"(^|_)(first|last|full|middle)?[-_]?name($|_)", re.I),
    "address": re.compile(r"address|street|zip|postal", re.I),
    "dob": re.compile(r"dob|birth[-_]?date|date[-_]?of[-_]?birth", re.I),
    "card_number": re.compile(r"card[-_]?(num|no|number)|pan\b", re.I),
    "ip_address": re.compile(r"ip[-_]?address", re.I),
}

# --- Value-pattern regexes ---------------------------------------------------

_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ssn_or_national_id": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
    "card_number": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}


@dataclass
class PIIMatch:
    category: str
    hit_rate: float  # fraction of sampled non-null values that matched


def column_name_hint(column_name: str) -> str | None:
    """Return a PII category if the column name itself suggests PII."""
    for category, pattern in _NAME_HINTS.items():
        if pattern.search(column_name):
            return category
    return None


def scan_values(values: list[str]) -> list[PIIMatch]:
    """Scan a sample of stringified values and return categories whose
    hit rate exceeds settings.pii_flag_threshold."""
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return []
    matches: list[PIIMatch] = []
    for category, pattern in _VALUE_PATTERNS.items():
        hits = sum(1 for v in non_null if pattern.search(str(v)))
        rate = hits / len(non_null)
        if rate >= settings.pii_flag_threshold:
            matches.append(PIIMatch(category=category, hit_rate=round(rate, 4)))
    return matches


def mask_value(value: object, category: str | None = None) -> str:
    """Mask a single value for display/audit purposes. Never returns the
    original value. Category-aware masking keeps enough shape to be
    useful (e.g. domain of an email) without being reversible to PII."""
    if value is None:
        return "NULL"
    text = str(value)
    if not text:
        return ""

    if category == "email" and "@" in text:
        local, _, domain = text.partition("@")
        return f"{local[:1]}***@{'*' * max(len(domain) - 4, 1)}{domain[-3:] if len(domain) > 3 else ''}"
    if category in ("ssn_or_national_id", "card_number"):
        digits = re.sub(r"\D", "", text)
        return f"***{digits[-4:]}" if len(digits) >= 4 else "****"
    if category == "phone":
        digits = re.sub(r"\D", "", text)
        return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "****"

    # Generic fallback: keep length signal only, mask content.
    if len(text) <= 2:
        return "*" * len(text)
    return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"


def mask_row(row: dict[str, object], pii_columns: dict[str, str]) -> dict[str, object]:
    """Return a copy of `row` with every column in `pii_columns`
    (column_name -> category) masked. Non-PII columns pass through
    unchanged."""
    masked = dict(row)
    for column, category in pii_columns.items():
        if column in masked:
            masked[column] = mask_value(masked[column], category)
    return masked


def classify_columns(column_names: list[str], sample_rows: list[dict[str, object]]) -> dict[str, str]:
    """Combine name-hint and value-pattern detection into a single
    column -> category map to drive masking for an entire result set."""
    classified: dict[str, str] = {}

    for column in column_names:
        hint = column_name_hint(column)
        if hint:
            classified[column] = hint

    for column in column_names:
        if column in classified:
            continue
        values = [row.get(column) for row in sample_rows]
        matches = scan_values([str(v) for v in values if v is not None])
        if matches:
            best = max(matches, key=lambda m: m.hit_rate)
            classified[column] = best.category

    return classified
