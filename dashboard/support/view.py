"""Support dashboard — SLA compliance, Ticket Volume."""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from dashboard import data
from dashboard.theme import (COLORS, empty_note, kpi_card, kpi_row, panel, style_fig)


def layout(days: int = 30):
    sd = data.support_daily(days)
    bc = data.support_by_category(days)

    if sd.empty:
        total = breached = 0
        sla = 100.0
    else:
        total = int(sd["tickets"].sum())
        breached = int(sd["breached"].sum())
        sla = (1 - breached / total) * 100 if total else 100.0

    cards = kpi_row([
        kpi_card("Ticket Volume", f"{total:,}", f"last {days} days", COLORS["accent"]),
        kpi_card("SLA Compliance", f"{sla:.1f}%", "resolved in target",
                 COLORS["good"] if sla >= 90 else COLORS["warn"]),
        kpi_card("SLA Breaches", f"{breached:,}", "missed target",
                 COLORS["bad"] if breached else COLORS["good"]),
    ])

    children = [cards]
    if not sd.empty:
        vol = go.Figure()
        vol.add_bar(x=sd["date"], y=sd["tickets"], name="Tickets", marker_color=COLORS["accent"])
        vol.add_bar(x=sd["date"], y=sd["breached"], name="Breached", marker_color=COLORS["bad"])
        vol.update_layout(title="Ticket Volume & SLA Breaches", barmode="overlay")
        children.append(panel("Ticket Volume", dcc.Graph(figure=style_fig(vol))))

        if not bc.empty:
            cat = go.Figure(go.Bar(x=bc["category"], y=bc["tickets"], marker_color=COLORS["series"]))
            cat.update_layout(title="Tickets by Category")
            children.append(panel("By Category", dcc.Graph(figure=style_fig(cat))))
    else:
        children.append(panel("Support",
                              empty_note("No support events yet — stream support_events / seed fact_support_events.")))
    return html.Div(children)
