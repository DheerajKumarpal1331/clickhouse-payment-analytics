"""Support dashboard — ticket volume, SLA compliance and breach breakdown by
category. Reads fact_support_events."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, fmt_num, grid, kpi_card,
                             kpi_row, panel, style_fig)


def layout(days: int = 30):
    s = data.support_summary(days)
    daily = data.support_daily(days)
    by_cat = data.support_by_category(days)

    cards = kpi_row([
        kpi_card("Ticket Volume", fmt_num(s["tickets"]), f"last {days} days", COLORS["accent"]),
        kpi_card("SLA Compliance", f"{s['sla']:.1f}%", "resolved in target",
                 COLORS["good"] if s["sla"] >= 90 else COLORS["warn"]),
        kpi_card("SLA Breaches", fmt_num(s["breached"]), "missed target",
                 COLORS["bad"] if s["breached"] else COLORS["good"]),
        kpi_card("Categories", f"{s['categories']:,}", "distinct queues", COLORS["violet"]),
    ])

    body = [cards]

    if daily.empty:
        return html.Div(body + [panel("Support",
            empty_note("No support events yet — stream support_events / seed fact_support_events."))])

    vol = go.Figure()
    vol.add_bar(x=daily["date"], y=daily["tickets"], name="Tickets",
                marker_color=COLORS["accent"], marker_line_width=0, opacity=0.85)
    vol.add_bar(x=daily["date"], y=daily["breached"], name="SLA breached",
                marker_color=COLORS["bad"], marker_line_width=0)
    vol.update_layout(title="Ticket Volume & SLA Breaches", barmode="overlay")
    style_fig(vol, 340)
    body.append(panel("Ticket Volume", dcc.Graph(figure=vol, config={"displayModeBar": False})))

    cat = go.Figure()
    if not by_cat.empty:
        cat.add_bar(y=by_cat["category"][::-1], x=by_cat["tickets"][::-1], orientation="h",
                    marker_color=COLORS["accent"], marker_line_width=0, name="Tickets")
    cat.update_layout(title="Tickets by Category"); style_fig(cat, 360)

    sla = go.Figure()
    if not by_cat.empty:
        rate = (by_cat["breached"] / by_cat["tickets"].replace(0, 1) * 100)
        sla.add_bar(y=by_cat["category"][::-1], x=rate[::-1], orientation="h",
                    marker_color=COLORS["warn"], marker_line_width=0)
    sla.update_layout(title="Breach Rate by Category (%)"); style_fig(sla, 360)

    body.append(grid([
        panel("By Category", dcc.Graph(figure=cat, config={"displayModeBar": False})),
        panel("Breach Rate", dcc.Graph(figure=sla, config={"displayModeBar": False})),
    ], template="1fr 1fr"))

    return html.Div(body)
