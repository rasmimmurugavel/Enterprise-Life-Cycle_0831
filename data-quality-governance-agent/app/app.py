"""Data Quality & Governance Agent - Streamlit dashboard (HLD §2.1).

Run with:  streamlit run app/app.py

Three actions map directly to the architecture diagram in the project
brief: Inspect Schema, Run Audit, and (added for auditability, BR-06)
an Audit Log viewer that reads the governance layer's append-only log
directly, independent of what the agent chooses to report.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run app/app.py` to find the `app` and `mcp_server`
# packages regardless of the invocation's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone  # noqa: E402

import streamlit as st  # noqa: E402

from app.agent import AgentRunError, ToolCallEvent, inspect_schema, run_audit  # noqa: E402
from app.config import settings as agent_settings  # noqa: E402
from app.ui.scorecard import (  # noqa: E402
    build_markdown_report,
    render_findings,
    render_governance_summary,
    render_scorecard,
)
from mcp_server.config import settings as db_settings  # noqa: E402
from mcp_server.tools.audit_log import read_recent  # noqa: E402

st.set_page_config(page_title="Data Quality & Governance Agent", page_icon="🛡️", layout="wide")

for key, default in {
    "schema_result": None,
    "audit_result": None,
    "rubric_version": "v1.0.0",
}.items():
    st.session_state.setdefault(key, default)


def _sidebar() -> None:
    st.sidebar.title("🛡️ Data Quality & Governance Agent")
    st.sidebar.caption("Streamlit + Claude + MCP, audit-ready by design")

    st.sidebar.subheader("Connection")
    st.sidebar.code(db_settings.redacted_target(), language=None)
    st.sidebar.write(
        f"Allowed schemas: `{', '.join(db_settings.allowed_schemas) or '(all visible to role)'}`"
    )
    st.sidebar.write(f"Row cap per call: `{db_settings.max_rows}`")
    st.sidebar.write(f"Statement timeout: `{db_settings.statement_timeout_ms} ms`")

    st.sidebar.subheader("Agent")
    st.sidebar.write(f"Model: `{agent_settings.anthropic_model}`")
    st.sidebar.write(f"Max tool calls / run: `{agent_settings.max_tool_calls}`")
    st.sidebar.write(f"Rubric version: `{st.session_state['rubric_version']}`")

    if not agent_settings.is_configured():
        st.sidebar.error("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")


def _progress_status(container, events: list[ToolCallEvent]):
    def _on_progress(event: ToolCallEvent) -> None:
        events.append(event)
        icon = "⚠️" if event.is_error else "✅"
        container.write(f"{icon} `{event.tool_name}({event.arguments})` → {event.result_summary}")

    return _on_progress


def _schema_tab() -> None:
    st.header("Inspect Schema")
    st.caption("Lists tables, columns, types, PK/FK visible to the configured role - no data is read.")

    if st.button("🔍 Inspect Schema", type="primary"):
        events: list[ToolCallEvent] = []
        with st.status("Inspecting schema...", expanded=True) as status:
            try:
                result = inspect_schema(on_progress=_progress_status(status, events))
                st.session_state["schema_result"] = result.findings
                status.update(label="Schema inspection complete", state="complete")
            except AgentRunError as exc:
                status.update(label="Schema inspection failed", state="error")
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001 - surface any transport/DB error to the user
                status.update(label="Schema inspection failed", state="error")
                st.error(f"Unexpected error: {exc}")

    schema_result = st.session_state.get("schema_result")
    if schema_result:
        for schema_entry in schema_result.get("schemas", []):
            st.subheader(f"Schema: `{schema_entry.get('schema')}`")
            for table in schema_entry.get("tables", []):
                with st.expander(f"📋 {table.get('table_name')} ({len(table.get('columns', []))} columns)"):
                    st.table(
                        [
                            {
                                "column": c.get("column_name"),
                                "type": c.get("data_type"),
                                "nullable": c.get("nullable"),
                                "pk": c.get("is_primary_key"),
                                "fk": (
                                    f"{c['foreign_key']['ref_table']}.{c['foreign_key']['ref_column']}"
                                    if c.get("foreign_key")
                                    else ""
                                ),
                            }
                            for c in table.get("columns", [])
                        ]
                    )


def _audit_tab() -> None:
    st.header("Run Audit")
    st.caption(
        "Runs the full data-quality baseline plus whatever the agent decides to investigate "
        "further, bounded by the tool-call budget in the sidebar."
    )

    schema_result = st.session_state.get("schema_result")
    table_options: list[str] = []
    if schema_result:
        for schema_entry in schema_result.get("schemas", []):
            for table in schema_entry.get("tables", []):
                table_options.append(f"{schema_entry.get('schema')}.{table.get('table_name')}")

    col1, col2 = st.columns([2, 1])
    with col1:
        if table_options:
            selected = st.multiselect(
                "Scope (leave empty to audit every table visible to the role)",
                options=table_options,
            )
        else:
            selected = []
            st.info("Run **Inspect Schema** first to scope the audit to specific tables, "
                     "or run a full-database audit directly below.")
    with col2:
        max_calls = st.number_input(
            "Tool-call budget", min_value=5, max_value=200, value=agent_settings.max_tool_calls, step=5
        )

    if st.button("▶️ Run Audit", type="primary"):
        if selected:
            scope_description = f"Audit exactly these tables: {', '.join(selected)}"
        else:
            scope_description = (
                f"Audit all tables in the allowed schema(s): "
                f"{', '.join(db_settings.allowed_schemas) or '(all schemas visible to the role)'}"
            )

        events: list[ToolCallEvent] = []
        with st.status("Running audit...", expanded=True) as status:
            try:
                result = run_audit(
                    scope_description, max_tool_calls=int(max_calls),
                    on_progress=_progress_status(status, events),
                )
                st.session_state["audit_result"] = result
                label = "Audit complete" if result.stopped_reason == "completed" else "Audit stopped (budget reached)"
                status.update(label=label, state="complete")
            except AgentRunError as exc:
                status.update(label="Audit failed", state="error")
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                status.update(label="Audit failed", state="error")
                st.error(f"Unexpected error: {exc}")

    audit_result = st.session_state.get("audit_result")
    if audit_result:
        findings = audit_result.findings
        if audit_result.stopped_reason != "completed":
            st.warning(
                "The agent reached its tool-call budget before finishing. "
                "Tables it did not get to are listed below - re-run with a higher budget "
                "or a narrower scope to cover them."
            )

        render_scorecard(findings)
        render_findings(findings)
        render_governance_summary(findings)

        report_md = build_markdown_report(
            findings,
            run_id=audit_result.run_id,
            model=agent_settings.anthropic_model,
            rubric_version=st.session_state["rubric_version"],
        )
        st.download_button(
            "⬇️ Download audit report (Markdown)",
            data=report_md,
            file_name=f"dq_audit_{audit_result.run_id}.md",
            mime="text/markdown",
        )


def _audit_log_tab() -> None:
    st.header("Audit Log")
    st.caption(
        "Every tool call the agent has made, read directly from the append-only log - "
        "independent of what made it into a findings report (BR-06)."
    )

    col1, col2 = st.columns(2)
    with col1:
        tool_filter = st.text_input("Filter by tool name (optional)")
    with col2:
        limit = st.number_input("Max entries", min_value=10, max_value=5000, value=200, step=10)

    entries = read_recent(limit=int(limit), tool=tool_filter or None)
    if not entries:
        st.info("No audit log entries yet - run a schema inspection or audit first.")
        return

    st.write(f"Showing {len(entries)} most recent entries (log path: `{db_settings.audit_log_path}`)")
    st.dataframe(
        [
            {
                "timestamp": e.get("timestamp"),
                "tool": e.get("tool"),
                "status": e.get("status"),
                "row_count": e.get("row_count"),
                "truncated": e.get("truncated"),
                "duration_ms": e.get("duration_ms"),
                "run_id": e.get("run_id"),
            }
            for e in reversed(entries)
        ],
        width='stretch',
    )


def main() -> None:
    _sidebar()
    st.title("Data Quality & Governance Agent")
    st.caption(
        f"Session started {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} - "
        "read-only, PII-masked, fully audit-logged."
    )

    tab_schema, tab_audit, tab_log = st.tabs(["📋 Schema Browser", "🛡️ Run Audit", "🧾 Audit Log"])
    with tab_schema:
        _schema_tab()
    with tab_audit:
        _audit_tab()
    with tab_log:
        _audit_log_tab()


if __name__ == "__main__":
    main()
