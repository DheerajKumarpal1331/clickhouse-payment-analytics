"""Settlement dashboard — T+1 settlement economics computed from successful
transactions: gross captured, fees (MDR + GST), net payable to merchants, and
today's pending payout. Live off fact_transactions."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_inr, grid, kpi_card,
                             kpi_row, panel, style_fig)


def layout(days: int = 30):
    s = data.settlement_summary(days)
    trend = data.settlement_trend(days)
    by_method = data.settlement_by_method(days)

    take_rate = (s["fees"] / s["gross"] * 100) if s["gross"] else 0.0
    cards = kpi_row([
        kpi_card("Gross Captured", fmt_inr(s["gross"]), f"successful, last {days}d", COLORS["accent"]),
        kpi_card("Net Payable", fmt_inr(s["net"]), "to merchants (T+1)", COLORS["good"]),
        kpi_card("Fees (MDR+GST)", fmt_inr(s["fees"]), f"take rate {take_rate:.2f}%", COLORS["warn"]),
        kpi_card("Pending Today", fmt_inr(s["pending"]), "settles next cycle", COLORS["violet"]),
    ])

    body = [cards]

    if trend.empty:
        return html.Div(body + [panel("Settlement", empty_note())])

    flow = go.Figure()
    flow.add_bar(x=trend["date"], y=trend["net"], name="Net to merchants",
                 marker_color=COLORS["good"], marker_line_width=0)
    flow.add_bar(x=trend["date"], y=trend["fees"], name="Fees retained",
                 marker_color=COLORS["warn"], marker_line_width=0)
    flow.update_layout(title="Daily Settlement — net payable vs fees", barmode="stack")
    style_fig(flow, 340)
    body.append(panel("Settlement Flow", dcc.Graph(figure=flow, config={"displayModeBar": False})))

    gross = go.Figure()
    gross.add_scatter(x=trend["date"], y=trend["gross"], mode="lines",
                      line=dict(color=COLORS["accent"], width=2.5, shape="spline"),
                      fill="tozeroy", fillcolor="rgba(79,140,255,0.12)", name="gross")
    gross.update_layout(title="Daily Gross Captured (₹)"); style_fig(gross, 300)

    meth = go.Figure()
    if not by_method.empty:
        meth.add_bar(x=by_method["payment_method"], y=by_method["gross"], name="Gross",
                     marker_color=COLORS["accent"], marker_line_width=0)
        meth.add_bar(x=by_method["payment_method"], y=by_method["fees"], name="Fees",
                     marker_color=COLORS["warn"], marker_line_width=0)
    meth.update_layout(title="Gross vs Fees by Method", barmode="group")
    style_fig(meth, 300)

    body.append(grid([
        panel("Gross Trend", dcc.Graph(figure=gross, config={"displayModeBar": False})),
        panel("By Method", dcc.Graph(figure=meth, config={"displayModeBar": False})),
    ], template="1fr 1fr"))

    return html.Div(body)
