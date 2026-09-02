"""Rendering helpers for the audit results: scorecard, findings table,
governance summary, and the downloadable Markdown report (FR-143).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from app.ui.charts import dimension_bar_chart, gauge, severity_donut, table_composite_chart

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_BADGE = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}


def render_scorecard(findings: dict[str, Any]) -> None:
    scorecard = findings.get("scorecard", {})
    database_score = scorecard.get("database_score", 0)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.plotly_chart(gauge(database_score), width='stretch')
    with col2:
        st.plotly_chart(dimension_bar_chart(scorecard), width='stretch')

    if scorecard.get("tables"):
        st.plotly_chart(table_composite_chart(scorecard), width='stretch')


def render_findings(findings: dict[str, Any]) -> None:
    all_findings = findings.get("findings", [])
    st.subheader(f"Findings ({len(all_findings)})")

    if not all_findings:
        st.success("No defects found in the audited scope.")
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        st.plotly_chart(severity_donut(all_findings), width='stretch')

    sorted_findings = sorted(all_findings, key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "low"), 9))
    with col2:
        for f in sorted_findings:
            badge = _SEVERITY_BADGE.get(f.get("severity", "low"), "⚪")
            location = f.get("table", "?")
            if f.get("column"):
                location += f".{f['column']}"
            with st.expander(f"{badge} [{f.get('severity','?').upper()}] {location} - {f.get('dimension','?')}"):
                st.write(f.get("description", ""))
                evidence = f.get("evidence")
                if evidence:
                    st.json(evidence)


def render_governance_summary(findings: dict[str, Any]) -> None:
    gov = findings.get("governance_summary", {})
    pii_cols = gov.get("pii_columns_detected", [])
    st.subheader(f"Governance: PII columns detected ({len(pii_cols)})")
    if pii_cols:
        st.table(pii_cols)
    else:
        st.write("None detected in the audited scope.")

    not_audited = findings.get("tables_not_audited", [])
    if not_audited:
        st.warning(
            "Not fully audited within the tool-call budget: " + ", ".join(not_audited)
        )


def build_markdown_report(findings: dict[str, Any], run_id: str, model: str, rubric_version: str) -> str:
    """FR-143: a self-contained Markdown report suitable for handing to
    an auditor without further editing - no dependency on the running
    Streamlit session to interpret it."""
    scorecard = findings.get("scorecard", {})
    all_findings = sorted(
        findings.get("findings", []),
        key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "low"), 9),
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Data Quality & Governance Audit Report",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Generated:** {generated_at}",
        f"- **Model:** {model}",
        f"- **Rubric version:** {rubric_version}",
        f"- **Scope:** {findings.get('scope', {})}",
        f"- **Tables audited:** {', '.join(findings.get('tables_audited', [])) or '(none)'}",
    ]
    if findings.get("tables_not_audited"):
        lines.append(f"- **Tables NOT audited (budget exhausted):** {', '.join(findings['tables_not_audited'])}")

    lines += [
        "",
        "## Scorecard",
        "",
        f"**Database score: {scorecard.get('database_score', 'n/a')}/100**",
        "",
        "| Table | Completeness | Validity | Uniqueness | Consistency | Timeliness | Composite |",
        "|---|---|---|---|---|---|---|",
    ]
    for table, dims in scorecard.get("tables", {}).items():
        lines.append(
            f"| {table} | {dims.get('completeness','-')} | {dims.get('validity','-')} | "
            f"{dims.get('uniqueness','-')} | {dims.get('consistency','-')} | "
            f"{dims.get('timeliness','-')} | **{dims.get('composite','-')}** |"
        )

    lines += ["", f"## Findings ({len(all_findings)})", ""]
    if not all_findings:
        lines.append("No defects found in the audited scope.")
    for f in all_findings:
        location = f.get("table", "?")
        if f.get("column"):
            location += f".{f['column']}"
        lines += [
            f"### [{f.get('severity','?').upper()}] {location} - {f.get('dimension','?')}",
            "",
            f.get("description", ""),
            "",
            f"Evidence: `{f.get('evidence', {})}`",
            "",
        ]

    gov = findings.get("governance_summary", {})
    lines += ["## Governance summary", "", f"PII columns detected: {len(gov.get('pii_columns_detected', []))}", ""]
    for pii in gov.get("pii_columns_detected", []):
        lines.append(f"- `{pii.get('table')}.{pii.get('column')}` - category: {pii.get('category')}")
    if gov.get("overrides_applied"):
        lines += ["", "Governance overrides applied:"]
        for o in gov["overrides_applied"]:
            lines.append(f"- {o}")

    lines += [
        "",
        "---",
        "_Raw PII values are never included in this report or in the audit log; "
        "PII findings are reported as column-level classifications only._",
    ]
    return "\n".join(lines)
