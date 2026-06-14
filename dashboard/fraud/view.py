"""Fraud dashboard — Fraud Rate, Fraud Loss, Model Performance."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_inr, kpi_card, kpi_row, panel, style_fig)


def layout(days: int = 30):
    fd = data.fraud_daily(days)
    fs = data.fraud_scores(days)

    if fd.empty:
        rate = loss = caught = 0.0
    else:
        rate = fd["fraud_txns"].sum() / max(fd["txns"].sum(), 1) * 100
        loss = fd["fraud_loss"].sum()
        caught = fd["fraud_txns"].sum()

    cards = kpi_row([
        kpi_card("Fraud Rate", f"{rate:.3f}%", f"last {days} days", COLORS["bad"]),
        kpi_card("Fraud Loss", fmt_inr(loss), "flagged amount", COLORS["warn"]),
        kpi_card("Fraud Txns", f"{int(caught):,}", "labelled", COLORS["series"][3]),
        kpi_card("Model", "PR-AUC in MLflow", "champion: fraud_detector", COLORS["good"]),
    ])

    children = [cards]
    if not fd.empty:
        f = go.Figure()
        f.add_bar(x=fd["date"], y=fd["fraud_txns"], name="Fraud txns", marker_color=COLORS["bad"])
        f.add_scatter(x=fd["date"], y=fd["fraud_rate"] * 100, name="Fraud rate %",
                      yaxis="y2", mode="lines+markers", line=dict(color=COLORS["warn"]))
        f.update_layout(title="Fraud Trend",
                        yaxis2=dict(overlaying="y", side="right", showgrid=False))
        children.append(panel("Fraud Trend", dcc.Graph(figure=style_fig(f))))

        loss_fig = go.Figure(go.Scatter(x=fd["date"], y=fd["fraud_loss"], fill="tozeroy",
                                        line=dict(color=COLORS["warn"])))
        loss_fig.update_layout(title="Daily Fraud Loss (₹)")

        if not fs.empty:
            perf = go.Figure(go.Bar(x=fs["risk_level"], y=fs["scored"],
                                    marker_color=COLORS["series"]))
            perf.update_layout(title="Scoring volume by risk band")
        else:
            perf = go.Figure(); perf.update_layout(title="Model scoring (no scores yet)")
        children.append(html.Div(style={"display": "flex", "gap": "16px"}, children=[
            html.Div(panel("Fraud Loss", dcc.Graph(figure=style_fig(loss_fig))), style={"flex": 1}),
            html.Div(panel("Model Performance", dcc.Graph(figure=style_fig(perf))), style={"flex": 1}),
        ]))
    else:
        children.append(panel("Fraud", empty_note()))
    return html.Div(children)
