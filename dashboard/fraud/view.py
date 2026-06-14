"""Fraud & Risk dashboard — live fraud rate, blocked value, decline rate, and
breakdowns by method / decline reason. Driven by fact_transactions
(fraud_label, is_success, response_code)."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_inr, fmt_num, grid,
                             kpi_card, kpi_row, panel, style_fig)


def layout(days: int = 30):
    s = data.fraud_summary(days)
    trend = data.fraud_trend(days)
    by_method = data.fraud_by_method(days)
    declines = data.decline_reasons(days)

    cards = kpi_row([
        kpi_card("Fraud Rate", f"{s['fraud_rate']:.3f}%", f"last {days} days",
                 COLORS["bad"] if s["fraud_rate"] > 0.5 else COLORS["warn"]),
        kpi_card("Fraud Flagged", fmt_num(s["fraud"]), "labelled txns", COLORS["violet"]),
        kpi_card("Blocked Value", fmt_inr(s["fraud_loss"]), "flagged amount", COLORS["bad"]),
        kpi_card("Decline Rate", f"{s['decline_rate']:.1f}%",
                 f"{fmt_num(s['declined'])} declined", COLORS["warn"]),
    ])

    body = [cards]

    if trend.empty:
        return html.Div(body + [panel("Fraud", empty_note())])

    f = go.Figure()
    f.add_bar(x=trend["date"], y=trend["fraud_txns"], name="Fraud txns",
              marker_color=COLORS["bad"], opacity=0.85, marker_line_width=0)
    f.add_scatter(x=trend["date"], y=trend["fraud_rate"], name="Fraud rate %", yaxis="y2",
                  mode="lines", line=dict(color=COLORS["warn"], width=2.5, shape="spline"))
    f.update_layout(title="Fraud Trend — count & rate",
                    yaxis2=dict(overlaying="y", side="right", showgrid=False))
    style_fig(f, 340)
    body.append(panel("Fraud Trend", dcc.Graph(figure=f, config={"displayModeBar": False})))

    loss = go.Figure()
    loss.add_scatter(x=trend["date"], y=trend["fraud_loss"], fill="tozeroy",
                     line=dict(color=COLORS["bad"], width=2.5, shape="spline"),
                     fillcolor="rgba(248,113,113,0.12)", name="loss")
    loss.update_layout(title="Daily Blocked Value (₹)"); style_fig(loss, 300)

    meth = go.Figure()
    if not by_method.empty:
        meth.add_bar(x=by_method["payment_method"], y=by_method["fraud"],
                     marker_color=COLORS["violet"], marker_line_width=0)
    meth.update_layout(title="Fraud by Payment Method"); style_fig(meth, 300)

    dec = go.Figure()
    if not declines.empty:
        dec.add_bar(x=declines["response_code"], y=declines["declines"],
                    marker_color=COLORS["warn"], marker_line_width=0)
    dec.update_layout(title="Top Decline Reasons (response code)"); style_fig(dec, 300)

    body.append(grid([
        panel("Blocked Value", dcc.Graph(figure=loss, config={"displayModeBar": False})),
        panel("By Method", dcc.Graph(figure=meth, config={"displayModeBar": False})),
        panel("Decline Reasons", dcc.Graph(figure=dec, config={"displayModeBar": False})),
    ], template="1fr 1fr 1fr"))

    return html.Div(body)
