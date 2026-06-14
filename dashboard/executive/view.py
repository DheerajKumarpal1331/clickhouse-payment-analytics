"""Executive dashboard — live realtime strip + headline economics (TPV, revenue,
approval rate, merchants) and trends over the selected window. All live off
fact_transactions; revenue is method-aware MDR."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, data_table, empty_note, fmt_inr, fmt_num,
                             grid, kpi_card, kpi_row, panel, style_fig)


def _realtime_strip():
    p = data.realtime_pulse(5)
    trend = data.ingest_trend(30)
    recent = data.recent_transactions(11)

    pulse = kpi_row([
        kpi_card("Ingested · 5 min", fmt_num(p["txns"]), "rows landing now", COLORS["accent"]),
        kpi_card("Live TPV · 5 min", fmt_inr(p["tpv"]), "value streamed", COLORS["good"]),
        kpi_card("Approval Rate", f"{p['success_rate']*100:.1f}%", "rolling 5 min", COLORS["cyan"]),
        kpi_card("Fraud Flagged", fmt_num(p["fraud"]), "last 5 min",
                 COLORS["bad"] if p["fraud"] else COLORS["violet"]),
    ])

    area = go.Figure()
    if not trend.empty:
        area.add_scatter(x=trend["minute"], y=trend["txns"], mode="lines",
                         line=dict(color=COLORS["accent"], width=2.5, shape="spline"),
                         fill="tozeroy", fillcolor="rgba(79,140,255,0.15)", name="txns/min")
    area.update_layout(title="Ingest rate — transactions per minute (last 30 min)")
    style_fig(area, 300)

    cond = [
        {"if": {"filter_query": "{ok} = ✗", "column_id": "ok"},
         "color": COLORS["bad"], "fontWeight": "700"},
        {"if": {"filter_query": "{ok} = ✓", "column_id": "ok"}, "color": COLORS["good"]},
        {"if": {"filter_query": "{fraud} = 1", "column_id": "fraud"},
         "color": COLORS["bad"], "fontWeight": "700"},
    ]
    feed = (data_table(recent, ["time", "merchant_id", "amount", "method", "ok", "fraud"], cond)
            if not recent.empty else empty_note("waiting for live transactions…"))

    return grid([
        panel("Live Ingest", dcc.Graph(figure=area, config={"displayModeBar": False})),
        panel("Latest Transactions", feed),
    ], template="1.6fr 1fr")


def layout(days: int = 30):
    rt = _realtime_strip()
    k = data.exec_summary(days)
    ts = data.exec_timeseries(days)
    mix = data.method_mix(days)

    cards = kpi_row([
        kpi_card("Total Payment Volume", fmt_inr(k["tpv"]), f"last {days} days",
                 COLORS["accent"], spark=list(ts["tpv"]) if not ts.empty else []),
        kpi_card("Revenue · MDR", fmt_inr(k["revenue"]), "est. fees earned",
                 COLORS["good"], spark=list(ts["revenue"]) if not ts.empty else []),
        kpi_card("Approval Rate", f"{k['success_rate']*100:.1f}%",
                 f"{fmt_num(k['declined'])} declined", COLORS["cyan"]),
        kpi_card("Avg Ticket", fmt_inr(k["avg_ticket"]), f"{fmt_num(k['txns'])} txns",
                 COLORS["violet"]),
        kpi_card("Active Merchants", f"{k['merchants']:,}", "transacting", COLORS["warn"]),
    ])

    body = [rt, html.Div(cards, style={"marginTop": "16px"})]

    if ts.empty:
        return html.Div(body + [panel("Trends", empty_note())])

    vol = go.Figure()
    vol.add_bar(x=ts["date"], y=ts["tpv"], name="TPV", marker_color=COLORS["accent"],
                marker_line_width=0, opacity=0.85)
    vol.add_scatter(x=ts["date"], y=ts["transactions"], name="Txns", yaxis="y2",
                    mode="lines", line=dict(color=COLORS["good"], width=2.5, shape="spline"))
    vol.update_layout(title="Daily TPV & Transactions",
                      yaxis2=dict(overlaying="y", side="right", showgrid=False))
    style_fig(vol, 340)

    rev = go.Figure()
    rev.add_bar(x=ts["date"], y=ts["revenue"], marker_color=COLORS["good"], name="Revenue")
    rev.update_layout(title="Daily Revenue (MDR, ₹)"); style_fig(rev, 300)

    sr = go.Figure()
    sr.add_scatter(x=ts["date"], y=ts["success_rate"] * 100, mode="lines",
                   line=dict(color=COLORS["cyan"], width=2.5, shape="spline"),
                   fill="tozeroy", fillcolor="rgba(34,211,238,0.12)", name="Approval %")
    sr.update_layout(title="Approval Rate (%)"); style_fig(sr, 300)
    sr.update_yaxes(range=[80, 100])

    mixfig = go.Figure()
    if not mix.empty:
        mixfig.add_pie(labels=mix["payment_method"], values=mix["volume"], hole=0.62,
                       marker=dict(colors=COLORS["series"]),
                       textinfo="label+percent", textposition="outside")
    mixfig.update_layout(title="Volume by Payment Method", showlegend=False)
    style_fig(mixfig, 300)

    return html.Div(body + [
        panel("Volume & Transactions", dcc.Graph(figure=vol, config={"displayModeBar": False})),
        grid([
            panel("Revenue", dcc.Graph(figure=rev, config={"displayModeBar": False})),
            panel("Approval Rate", dcc.Graph(figure=sr, config={"displayModeBar": False})),
            panel("Method Mix", dcc.Graph(figure=mixfig, config={"displayModeBar": False})),
        ], template="1fr 1fr 1fr"),
    ])
