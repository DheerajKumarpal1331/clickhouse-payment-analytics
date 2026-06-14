"""Merchant dashboard — Merchant Growth, RFM segmentation, Churn Risk."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, kpi_card, kpi_row, panel, style_fig)

# A merchant is churn-risk if it hasn't transacted in this many days.
CHURN_DAYS = 14


def layout(days: int = 30):
    growth = data.merchant_growth()
    rfm = data.merchant_rfm()

    total = len(rfm) if not rfm.empty else 0
    champions = int((rfm["segment"] == "Champions").sum()) if not rfm.empty else 0
    at_risk = int((rfm["recency"] > CHURN_DAYS).sum()) if not rfm.empty else 0
    churn_pct = (at_risk / total * 100) if total else 0

    cards = kpi_row([
        kpi_card("Merchants Analyzed", f"{total:,}", "with activity", COLORS["accent"]),
        kpi_card("Champions (RFM)", f"{champions:,}", "high R+F", COLORS["good"]),
        kpi_card("Churn Risk", f"{at_risk:,}", f"no txns >{CHURN_DAYS}d", COLORS["bad"]),
        kpi_card("Churn Rate", f"{churn_pct:.1f}%", "of active base", COLORS["warn"]),
    ])

    children = [cards]

    if not growth.empty:
        g = go.Figure()
        g.add_bar(x=growth["month"], y=growth["active_merchants"], name="Active merchants",
                  marker_color=COLORS["accent"])
        g.update_layout(title="Merchant Growth (active per month)")
        children.append(panel("Merchant Growth", dcc.Graph(figure=style_fig(g))))

    if not rfm.empty:
        seg = rfm["segment"].value_counts().reset_index()
        seg.columns = ["segment", "count"]
        sfig = go.Figure(go.Bar(x=seg["segment"], y=seg["count"],
                                marker_color=COLORS["series"]))
        sfig.update_layout(title="RFM Segments")

        scat = go.Figure(go.Scatter(
            x=rfm["frequency"], y=rfm["monetary"], mode="markers",
            marker=dict(size=8, color=rfm["recency"], colorscale="Viridis_r",
                        showscale=True, colorbar=dict(title="Recency(d)")),
            text=rfm["segment"]))
        scat.update_layout(title="Frequency vs Monetary (color = recency)",
                           xaxis_title="Frequency (txns)", yaxis_title="Monetary (₹)")
        children.append(html.Div(style={"display": "flex", "gap": "16px"}, children=[
            html.Div(panel("Segments", dcc.Graph(figure=style_fig(sfig))), style={"flex": 1}),
            html.Div(panel("RFM Scatter", dcc.Graph(figure=style_fig(scat))), style={"flex": 1}),
        ]))
    else:
        children.append(panel("RFM", empty_note()))

    return html.Div(children)
