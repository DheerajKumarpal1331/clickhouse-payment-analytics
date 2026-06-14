"""Executive dashboard — TPV, Revenue, Active Merchants, Transactions."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_inr, fmt_num, kpi_card,
                             kpi_row, panel, style_fig)


def layout(days: int = 30):
    k = data.exec_kpis(days)
    ts = data.exec_timeseries(days)
    mix = data.method_mix(days)

    cards = kpi_row([
        kpi_card("Total Payment Volume", fmt_inr(k["tpv"]), f"last {days} days", COLORS["accent"]),
        kpi_card("Revenue (MDR)", fmt_inr(k["revenue"]), "fees earned", COLORS["good"]),
        kpi_card("Transactions", fmt_num(k["transactions"]), "count", COLORS["series"][3]),
        kpi_card("Active Merchants", f"{k['active_merchants']:,}", "transacting", COLORS["warn"]),
    ])

    if ts.empty:
        return html.Div([cards, panel("Trends", empty_note())])

    vol = go.Figure()
    vol.add_bar(x=ts["date"], y=ts["tpv"], name="TPV", marker_color=COLORS["accent"])
    vol.add_scatter(x=ts["date"], y=ts["transactions"], name="Txns", yaxis="y2",
                    mode="lines+markers", line=dict(color=COLORS["good"]))
    vol.update_layout(title="Daily TPV & Transactions",
                      yaxis2=dict(overlaying="y", side="right", showgrid=False))
    style_fig(vol)

    sr = go.Figure()
    sr.add_scatter(x=ts["date"], y=ts["success_rate"] * 100, mode="lines+markers",
                   line=dict(color=COLORS["good"]), name="Success %")
    sr.update_layout(title="Success Rate (%)"); style_fig(sr, 280)
    sr.update_yaxes(range=[80, 100])

    mixfig = go.Figure()
    if not mix.empty:
        mixfig.add_pie(labels=mix["payment_method"], values=mix["volume"], hole=0.5)
    mixfig.update_layout(title="Volume by Payment Method"); style_fig(mixfig, 280)

    return html.Div([
        cards,
        panel("Volume & Transactions", dcc.Graph(figure=vol)),
        html.Div(style={"display": "flex", "gap": "16px"}, children=[
            html.Div(panel("Success Rate", dcc.Graph(figure=sr)), style={"flex": 1}),
            html.Div(panel("Method Mix", dcc.Graph(figure=mixfig)), style={"flex": 1}),
        ]),
    ])
