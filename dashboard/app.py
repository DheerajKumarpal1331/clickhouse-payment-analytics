"""Plotly Dash analytics platform — 5 dashboards over the ClickHouse marts.

Multi-page app with a sidebar; each page's layout() queries fresh data on
navigation. `server` is the WSGI handle for gunicorn
(docker/dashboard/startup.sh runs `gunicorn dashboard.app:server`).
"""
from __future__ import annotations

import dash
from dash import Input, Output, dcc, html

from dashboard.theme import COLORS
from dashboard.executive import view as executive
from dashboard.merchant import view as merchant
from dashboard.fraud import view as fraud
from dashboard.settlement import view as settlement
from dashboard.support import view as support

PAGES = {
    "/": ("Executive", executive.layout),
    "/merchant": ("Merchant", merchant.layout),
    "/fraud": ("Fraud & Risk", fraud.layout),
    "/settlement": ("Settlement", settlement.layout),
    "/support": ("Support", support.layout),
}

app = dash.Dash(__name__, title="Payment Analytics", suppress_callback_exceptions=True,
                update_title=None)
server = app.server  # gunicorn entrypoint


def _nav(active: str):
    links = []
    for path, (label, _) in PAGES.items():
        is_active = path == active
        links.append(dcc.Link(label, href=path, style={
            "display": "block", "padding": "12px 18px", "color": COLORS["text"] if is_active else COLORS["muted"],
            "background": COLORS["accent"] if is_active else "transparent",
            "borderRadius": "8px", "marginBottom": "4px", "textDecoration": "none", "fontWeight": "600"}))
    return html.Div(style={
        "width": "210px", "background": COLORS["panel"], "padding": "18px",
        "height": "100vh", "position": "fixed", "boxSizing": "border-box"}, children=[
        html.Div("💳 Payments", style={"color": COLORS["text"], "fontSize": "20px",
                                       "fontWeight": "800", "marginBottom": "20px"}),
        *links,
        html.Div("ClickHouse marts · live", style={"color": COLORS["muted"], "fontSize": "11px",
                                                   "position": "absolute", "bottom": "18px"}),
    ])


app.layout = html.Div(style={"background": COLORS["bg"], "minHeight": "100vh",
                             "fontFamily": "Inter, system-ui, sans-serif"}, children=[
    dcc.Location(id="url"),
    html.Div(id="sidebar"),
    html.Div(id="page", style={"marginLeft": "210px", "padding": "24px"}),
])


@app.callback(Output("page", "children"), Output("sidebar", "children"),
              Input("url", "pathname"), Input("url", "search"))
def route(pathname, search):
    label, render = PAGES.get(pathname or "/", PAGES["/"])
    days = 30
    if search and "days=" in search:
        try:
            days = int(search.split("days=")[1].split("&")[0])
        except ValueError:
            pass
    header = html.H1(label, style={"color": COLORS["text"], "margin": "0 0 16px 0"})
    try:
        body = render(days)
    except Exception as e:  # never blank-screen the dashboard
        body = html.Div(f"data error: {e}", style={"color": COLORS["bad"]})
    return html.Div([header, body]), _nav(pathname or "/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
