"""Plotly chart builders for the audit dashboard.

Kept separate from app.py so the chart/color choices can be reviewed
and adjusted without touching the page flow. Palette is deliberately
neutral (no brand colors baked in) and colorblind-safe:
green/amber/red mapped to score bands, not to arbitrary categorical
hues.
"""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

_SEVERITY_COLORS = {
    "critical": "#B3261E",
    "high": "#D9730D",
    "medium": "#B8860B",
    "low": "#5B6470",
}

_SCORE_COLORSCALE = [
    [0.0, "#B3261E"],
    [0.5, "#D9730D"],
    [0.8, "#2E7D32"],
    [1.0, "#2E7D32"],
]


def _score_color(score: float) -> str:
    if score >= 80:
        return "#2E7D32"
    if score >= 60:
        return "#D9730D"
    return "#B3261E"


def dimension_bar_chart(scorecard: dict[str, Any]) -> go.Figure:
    """One bar per rubric dimension, averaged across all audited tables."""
    tables = scorecard.get("tables", {})
    dimensions = ["completeness", "validity", "uniqueness", "consistency", "timeliness"]
    averages = []
    for dim in dimensions:
        values = [t.get(dim) for t in tables.values() if isinstance(t.get(dim), (int, float))]
        averages.append(sum(values) / len(values) if values else 0)

    fig = go.Figure(
        go.Bar(
            x=[d.capitalize() for d in dimensions],
            y=averages,
            marker_color=[_score_color(v) for v in averages],
            text=[f"{v:.0f}" for v in averages],
            textposition="outside",
        )
    )
    fig.update_layout(
        yaxis=dict(range=[0, 100], title="Score"),
        xaxis=dict(title=None),
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        showlegend=False,
    )
    return fig


def table_composite_chart(scorecard: dict[str, Any]) -> go.Figure:
    """Horizontal bar of composite score per audited table."""
    tables = scorecard.get("tables", {})
    names = list(tables.keys())
    composites = [tables[n].get("composite", 0) for n in names]
    order = sorted(range(len(names)), key=lambda i: composites[i])
    names = [names[i] for i in order]
    composites = [composites[i] for i in order]

    fig = go.Figure(
        go.Bar(
            x=composites,
            y=names,
            orientation="h",
            marker_color=[_score_color(v) for v in composites],
            text=[f"{v:.0f}" for v in composites],
            textposition="outside",
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 100], title="Composite score"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=max(220, 36 * len(names)),
    )
    return fig


def severity_donut(findings: list[dict[str, Any]]) -> go.Figure:
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        sev = f.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

    labels = [k.capitalize() for k, v in counts.items() if v > 0]
    values = [v for v in counts.values() if v > 0]
    colors = [_SEVERITY_COLORS[k] for k, v in counts.items() if v > 0]

    if not values:
        fig = go.Figure()
        fig.add_annotation(text="No findings", showarrow=False, font=dict(size=14))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55, marker_colors=colors))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    return fig


def gauge(score: float, title: str = "Database score") -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": _score_color(score)},
                "steps": [
                    {"range": [0, 60], "color": "#F4E3E1"},
                    {"range": [60, 80], "color": "#F6EBD9"},
                    {"range": [80, 100], "color": "#E3EFE3"},
                ],
            },
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    return fig
