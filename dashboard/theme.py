"""Shared look & feel: palette, KPI cards (with trend deltas + sparklines),
figure styling, and layout primitives. Dark, high-contrast, dashboard-grade.
"""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

COLORS = {
    "bg": "#0b0f17", "panel": "#141b27", "panel2": "#1b2433",
    "text": "#e8eef6", "muted": "#7d8aa0", "border": "#222d3d",
    "accent": "#4f8cff", "good": "#2dd4a7", "warn": "#fbbf24", "bad": "#f87171",
    "violet": "#a78bfa", "cyan": "#22d3ee", "pink": "#f472b6",
    "series": ["#4f8cff", "#2dd4a7", "#fbbf24", "#a78bfa", "#f87171", "#22d3ee", "#f472b6"],
}


def fmt_inr(v: float) -> str:
    v = float(v or 0)
    if v >= 1e7:
        return f"₹{v/1e7:.2f} Cr"
    if v >= 1e5:
        return f"₹{v/1e5:.2f} L"
    if v >= 1e3:
        return f"₹{v/1e3:.1f} K"
    return f"₹{v:.0f}"


def fmt_num(v: float) -> str:
    v = float(v or 0)
    return f"{v/1e6:.2f}M" if v >= 1e6 else f"{v/1e3:.1f}K" if v >= 1e3 else f"{v:.0f}"


def _spark(values, color) -> dcc.Graph:
    fig = go.Figure(go.Scatter(
        y=list(values), mode="lines", line=dict(color=color, width=2, shape="spline"),
        fill="tozeroy", fillcolor="rgba(79,140,255,0.10)", hoverinfo="skip"))
    fig.update_layout(
        height=42, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "42px"})


def kpi_card(title: str, value: str, sub: str = "", color: str = None,
             delta: float = None, spark=None) -> html.Div:
    """A KPI card. Optional `delta` (% change) renders a colored trend chip and
    optional `spark` (iterable) renders a sparkline footer."""
    color = color or COLORS["accent"]
    head = [html.Span(title, style={"color": COLORS["muted"], "fontSize": "12px",
                                    "textTransform": "uppercase", "letterSpacing": "0.6px",
                                    "fontWeight": "600"})]
    if delta is not None:
        up = delta >= 0
        head.append(html.Span(
            f"{'▲' if up else '▼'} {abs(delta):.1f}%",
            style={"marginLeft": "auto", "fontSize": "12px", "fontWeight": "700",
                   "color": COLORS["good"] if up else COLORS["bad"],
                   "background": ("rgba(45,212,167,0.12)" if up else "rgba(248,113,113,0.12)"),
                   "borderRadius": "6px", "padding": "2px 7px"}))
    body = [
        html.Div(head, style={"display": "flex", "alignItems": "center"}),
        html.Div(value, style={"color": COLORS["text"], "fontSize": "30px",
                               "fontWeight": "800", "marginTop": "8px", "lineHeight": "1.1"}),
        html.Div(sub, style={"color": COLORS["muted"], "fontSize": "12px", "marginTop": "4px"}),
    ]
    if spark is not None and len(list(spark)):
        body.append(html.Div(_spark(spark, color), style={"marginTop": "8px"}))
    return html.Div(
        style={"background": f"linear-gradient(180deg,{COLORS['panel2']},{COLORS['panel']})",
               "borderRadius": "14px", "padding": "16px 18px", "flex": "1", "minWidth": "190px",
               "border": f"1px solid {COLORS['border']}", "borderTop": f"3px solid {color}",
               "boxShadow": "0 1px 3px rgba(0,0,0,0.3)"},
        children=body)


def style_fig(fig, height: int = 320):
    fig.update_layout(
        template="plotly_dark", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=44, r=20, t=44, b=40),
        font=dict(color=COLORS["text"], size=12, family="Inter, system-ui, sans-serif"),
        colorway=COLORS["series"], title_font_size=15, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=COLORS["border"], zeroline=False)
    fig.update_yaxes(gridcolor=COLORS["border"], zeroline=False)
    return fig


def panel(title: str, *children, **kw) -> html.Div:
    return html.Div(
        style={"background": COLORS["panel"], "borderRadius": "14px", "padding": "16px 18px",
               "marginTop": "16px", "border": f"1px solid {COLORS['border']}", **kw.get("style", {})},
        children=[html.Div(title, style={"color": COLORS["text"], "fontSize": "15px",
                                         "fontWeight": "700", "margin": "0 0 6px 0"}), *children])


def kpi_row(cards) -> html.Div:
    # responsive: cards share the row evenly and wrap on narrow screens
    return html.Div(cards, style={
        "display": "grid", "gap": "14px",
        "gridTemplateColumns": f"repeat({len(cards)}, minmax(0, 1fr))"})


def grid(children, template="1fr 1fr", gap: int = 16) -> html.Div:
    """Aligned CSS-grid row. `template` is a grid-template-columns string."""
    return html.Div(children, style={"display": "grid", "gap": f"{gap}px",
                                     "gridTemplateColumns": template, "marginTop": "16px"})


def data_table(df, columns, conditional=None, page_size=None):
    """A consistently-styled dark table from a DataFrame."""
    from dash import dash_table
    return dash_table.DataTable(
        data=df.to_dict("records") if df is not None and not df.empty else [],
        columns=[{"name": c.replace("_", " ").title(), "id": c} for c in columns],
        page_size=page_size or 100,
        style_as_list_view=True,
        style_header={"backgroundColor": COLORS["panel2"], "color": COLORS["muted"],
                      "fontWeight": "700", "border": "none", "textTransform": "uppercase",
                      "fontSize": "11px", "letterSpacing": "0.4px"},
        style_cell={"backgroundColor": COLORS["panel"], "color": COLORS["text"],
                    "border": f"1px solid {COLORS['border']}", "fontSize": "13px",
                    "fontFamily": "Inter, system-ui, sans-serif", "padding": "8px 12px",
                    "textAlign": "left"},
        style_data_conditional=conditional or [])


def empty_note(msg="No data yet — run the pipeline / seed the warehouse.") -> html.Div:
    return html.Div(msg, style={"color": COLORS["muted"], "padding": "12px"})
