"""Settlement dashboard — Settlement TAT, Failed Settlements."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_inr, kpi_card, kpi_row, panel, style_fig)


def layout(days: int = 30):
    sd = data.settlement_daily(days)

    if sd.empty:
        avg_tat = failed = net = 0.0
    else:
        avg_tat = sd["tat"].mean()
        failed = sd["failed_batches"].sum()
        net = sd["net"].sum()

    cards = kpi_row([
        kpi_card("Avg Settlement TAT", f"{avg_tat:.0f} min", "cycle close → paid", COLORS["accent"]),
        kpi_card("Failed Settlements", f"{int(failed):,}", f"last {days} days",
                 COLORS["bad"] if failed else COLORS["good"]),
        kpi_card("Net Settled", fmt_inr(net), "to merchants", COLORS["good"]),
    ])

    children = [cards]
    if not sd.empty:
        tat = go.Figure(go.Scatter(x=sd["date"], y=sd["tat"], mode="lines+markers",
                                   line=dict(color=COLORS["accent"]), name="TAT (min)"))
        tat.update_layout(title="Settlement TAT (minutes)")

        fail = go.Figure()
        fail.add_bar(x=sd["date"], y=sd["failed_batches"], name="Failed", marker_color=COLORS["bad"])
        fail.add_scatter(x=sd["date"], y=sd["net"], name="Net settled (₹)", yaxis="y2",
                         mode="lines", line=dict(color=COLORS["good"]))
        fail.update_layout(title="Failed batches & Net settled",
                           yaxis2=dict(overlaying="y", side="right", showgrid=False))
        children.append(html.Div(style={"display": "flex", "gap": "16px"}, children=[
            html.Div(panel("Turnaround", dcc.Graph(figure=style_fig(tat))), style={"flex": 1}),
            html.Div(panel("Failures & Volume", dcc.Graph(figure=style_fig(fail))), style={"flex": 1}),
        ]))
    else:
        children.append(panel("Settlement", empty_note()))
    return html.Div(children)
