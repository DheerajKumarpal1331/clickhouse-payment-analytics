"""Shared look & feel: palette, KPI card component, figure styling."""
from __future__ import annotations

from dash import html

COLORS = {
    "bg": "#0f1419", "panel": "#1a2332", "text": "#e6edf3", "muted": "#8b98a5",
    "accent": "#3b82f6", "good": "#22c55e", "warn": "#f59e0b", "bad": "#ef4444",
    "series": ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#14b8a6"],
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


def kpi_card(title: str, value: str, sub: str = "", color: str = None) -> html.Div:
    return html.Div(
        style={"background": COLORS["panel"], "borderRadius": "12px", "padding": "18px 20px",
               "flex": "1", "minWidth": "180px",
               "borderLeft": f"4px solid {color or COLORS['accent']}"},
        children=[
            html.Div(title, style={"color": COLORS["muted"], "fontSize": "13px",
                                   "textTransform": "uppercase", "letterSpacing": "0.5px"}),
            html.Div(value, style={"color": COLORS["text"], "fontSize": "30px",
                                   "fontWeight": "700", "marginTop": "6px"}),
            html.Div(sub, style={"color": COLORS["muted"], "fontSize": "12px", "marginTop": "4px"}),
        ],
    )


def style_fig(fig, height: int = 320):
    fig.update_layout(
        template="plotly_dark", height=height,
        paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
        margin=dict(l=40, r=20, t=40, b=40),
        font=dict(color=COLORS["text"], size=12),
        colorway=COLORS["series"], title_font_size=15,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(gridcolor="#2a3441"); fig.update_yaxes(gridcolor="#2a3441")
    return fig


def panel(title: str, *children) -> html.Div:
    return html.Div(
        style={"background": COLORS["panel"], "borderRadius": "12px", "padding": "16px",
               "marginTop": "16px"},
        children=[html.H3(title, style={"color": COLORS["text"], "fontSize": "16px",
                                        "margin": "0 0 8px 0"}), *children])


def kpi_row(cards) -> html.Div:
    return html.Div(cards, style={"display": "flex", "gap": "14px", "flexWrap": "wrap"})


def empty_note(msg="No data yet — run the pipeline / seed the warehouse.") -> html.Div:
    return html.Div(msg, style={"color": COLORS["muted"], "padding": "12px"})
