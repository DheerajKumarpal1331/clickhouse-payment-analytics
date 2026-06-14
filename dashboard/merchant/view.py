"""Merchant dashboard — live acquiring view: active & newly-onboarded merchants,
top performers by volume, channel mix, and daily active trend. All live off
fact_transactions (fed by the transaction + merchant-onboarding generators)."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, data_table, empty_note, fmt_inr, fmt_num,
                             grid, kpi_card, kpi_row, panel, style_fig)


def layout(days: int = 30):
    s = data.merchant_summary(days)
    top = data.top_merchants(days, 10)
    daily = data.merchant_daily_active(days)
    chan = data.channel_mix(days)

    cards = kpi_row([
        kpi_card("Active Merchants", f"{s['active']:,}", f"last {days} days", COLORS["accent"]),
        kpi_card("Active Today", f"{s['active_today']:,}", "transacting today", COLORS["cyan"]),
        kpi_card("New Merchants", f"{s['new_today']:,}", "first txn today", COLORS["good"]),
        kpi_card("Avg Ticket", fmt_inr(s["avg_ticket"]), "per transaction", COLORS["violet"]),
    ])

    body = [cards]

    lead = go.Figure()
    if not top.empty:
        lead.add_bar(y=top["merchant_id"][::-1], x=top["tpv"][::-1], orientation="h",
                     marker_color=COLORS["accent"], marker_line_width=0)
        lead.update_layout(title="Top Merchants by TPV (₹)")
    style_fig(lead, 360)

    chanfig = go.Figure()
    if not chan.empty:
        chanfig.add_pie(labels=chan["channel"], values=chan["volume"], hole=0.6,
                        marker=dict(colors=COLORS["series"]), textinfo="label+percent")
    chanfig.update_layout(title="Volume by Channel", showlegend=False)
    style_fig(chanfig, 360)

    body.append(grid([
        panel("Merchant Leaderboard", dcc.Graph(figure=lead, config={"displayModeBar": False})),
        panel("Channel Mix", dcc.Graph(figure=chanfig, config={"displayModeBar": False})),
    ], template="1.5fr 1fr"))

    if not daily.empty:
        act = go.Figure()
        act.add_bar(x=daily["date"], y=daily["merchants"], name="Active merchants",
                    marker_color=COLORS["good"], opacity=0.85, marker_line_width=0)
        act.add_scatter(x=daily["date"], y=daily["txns"], name="Txns", yaxis="y2",
                        mode="lines", line=dict(color=COLORS["accent"], width=2.5, shape="spline"))
        act.update_layout(title="Daily Active Merchants & Transactions",
                          yaxis2=dict(overlaying="y", side="right", showgrid=False))
        style_fig(act, 320)
        body.append(panel("Activity Trend",
                          dcc.Graph(figure=act, config={"displayModeBar": False})))

    if not top.empty:
        tbl = top.copy()
        tbl["tpv"] = tbl["tpv"].map(fmt_inr)
        tbl["txns"] = tbl["txns"].map(fmt_num)
        tbl["success"] = tbl["success"].map(lambda v: f"{v:.1f}%")
        body.append(panel("Top Merchants — detail",
                          data_table(tbl, ["merchant_id", "txns", "tpv", "success"])))
    else:
        body.append(panel("Merchants", empty_note()))

    return html.Div(body)
