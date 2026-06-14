"""Plotly Dash analytics platform — 5 dashboards over the ClickHouse marts.

Multi-page app with a sidebar. A dcc.Interval drives live auto-refresh: every
tick re-renders the active page (re-querying ClickHouse), so the dashboard
streams instead of sitting still. A top bar carries a live clock + LIVE pulse,
the time-window selector, and the refresh-rate control. `server` is the WSGI
handle for gunicorn (docker/dashboard/startup.sh runs `gunicorn dashboard.app:server`).
"""
from __future__ import annotations

import datetime as dt

import dash
from dash import Input, Output, dcc, html

from dashboard.theme import COLORS
from dashboard.executive import view as executive
from dashboard.merchant import view as merchant
from dashboard.fraud import view as fraud
from dashboard.settlement import view as settlement
from dashboard.support import view as support

PAGES = {
    "/": ("Executive", "📊", executive.layout),
    "/merchant": ("Merchant", "🏪", merchant.layout),
    "/fraud": ("Fraud & Risk", "🛡️", fraud.layout),
    "/settlement": ("Settlement", "🏦", settlement.layout),
    "/support": ("Support", "🎧", support.layout),
}

REFRESH_OPTS = [("Off", 0), ("5s", 5_000), ("10s", 10_000), ("30s", 30_000)]
WINDOW_OPTS = [("7d", 7), ("30d", 30), ("90d", 90)]

app = dash.Dash(__name__, title="Payment Analytics", suppress_callback_exceptions=True,
                update_title=None)
server = app.server  # gunicorn entrypoint


def _nav(active: str):
    links = []
    for path, (label, icon, _) in PAGES.items():
        is_active = path == active
        links.append(dcc.Link(f"{icon}  {label}", href=path, style={
            "display": "block", "padding": "11px 16px",
            "color": COLORS["text"] if is_active else COLORS["muted"],
            "background": ("linear-gradient(90deg,rgba(79,140,255,0.25),rgba(79,140,255,0.05))"
                           if is_active else "transparent"),
            "borderLeft": f"3px solid {COLORS['accent'] if is_active else 'transparent'}",
            "borderRadius": "0 8px 8px 0", "marginBottom": "3px",
            "textDecoration": "none", "fontWeight": "600", "fontSize": "14px"}))
    return html.Div(style={
        "width": "212px", "background": COLORS["panel"], "padding": "18px 12px",
        "height": "100vh", "position": "fixed", "boxSizing": "border-box",
        "borderRight": f"1px solid {COLORS['border']}"}, children=[
        html.Div([html.Span("💳", style={"fontSize": "22px"}),
                  html.Span(" Payments", style={"fontWeight": "800", "fontSize": "19px"})],
                 style={"color": COLORS["text"], "marginBottom": "22px", "paddingLeft": "6px"}),
        *links,
        html.Div("ClickHouse marts · live stream",
                 style={"color": COLORS["muted"], "fontSize": "11px",
                        "position": "absolute", "bottom": "18px", "left": "16px"}),
    ])


def _pill(children, **style):
    base = {"display": "flex", "alignItems": "center", "gap": "8px",
            "background": COLORS["panel"], "border": f"1px solid {COLORS['border']}",
            "borderRadius": "10px", "padding": "6px 12px"}
    return html.Div(children, style={**base, **style})


def _topbar():
    # Persistent shell — the window/refresh controls and clock MUST live in the
    # static layout so the callbacks that depend on them resolve at first load.
    live_dot = html.Span(className="live-dot", style={
        "width": "9px", "height": "9px", "borderRadius": "50%",
        "background": COLORS["good"], "display": "inline-block",
        "boxShadow": f"0 0 0 0 {COLORS['good']}"})
    return html.Div(style={"display": "flex", "alignItems": "center", "gap": "14px",
                           "marginBottom": "18px", "flexWrap": "wrap"}, children=[
        html.H1(id="page-title", style={"color": COLORS["text"], "margin": 0,
                                        "fontSize": "26px", "fontWeight": "800"}),
        _pill([live_dot, html.Span("LIVE", style={"color": COLORS["good"], "fontWeight": "700",
                                                  "fontSize": "12px", "letterSpacing": "1px"})]),
        html.Div(id="clock", style={"color": COLORS["muted"], "fontSize": "13px"}),
        html.Div(style={"marginLeft": "auto", "display": "flex", "gap": "10px"}, children=[
            _pill([html.Span("Window", style={"color": COLORS["muted"], "fontSize": "12px"}),
                   dcc.Dropdown(id="window", clearable=False,
                                options=[{"label": l, "value": v} for l, v in WINDOW_OPTS],
                                value=30, style={"width": "90px"}, className="ctl")]),
            _pill([html.Span("Refresh", style={"color": COLORS["muted"], "fontSize": "12px"}),
                   dcc.Dropdown(id="refresh", clearable=False,
                                options=[{"label": l, "value": v} for l, v in REFRESH_OPTS],
                                value=10_000, style={"width": "90px"}, className="ctl")]),
        ]),
    ])


app.layout = html.Div(style={"background": COLORS["bg"], "minHeight": "100vh",
                             "fontFamily": "Inter, system-ui, sans-serif"}, children=[
    dcc.Location(id="url"),
    dcc.Interval(id="tick", interval=10_000),
    html.Div(id="sidebar"),
    html.Div(style={"marginLeft": "212px", "padding": "22px 26px"}, children=[
        _topbar(),
        dcc.Loading(html.Div(id="page"), type="default", color=COLORS["accent"]),
    ]),
])


@app.callback(Output("tick", "interval"), Output("tick", "disabled"), Input("refresh", "value"))
def _set_refresh(ms):
    ms = int(ms or 0)
    return (ms or 10_000), ms == 0


@app.callback(Output("clock", "children"), Input("tick", "n_intervals"))
def _clock(_):
    return "updated " + dt.datetime.now().strftime("%H:%M:%S")


@app.callback(Output("page", "children"), Output("page-title", "children"),
              Output("sidebar", "children"),
              Input("url", "pathname"), Input("window", "value"),
              Input("tick", "n_intervals"))
def route(pathname, window, _tick):
    label, _icon, render = PAGES.get(pathname or "/", PAGES["/"])
    days = int(window or 30)
    try:
        body = render(days)
    except Exception as e:  # never blank-screen the dashboard
        body = html.Div(f"data error: {e}", style={"color": COLORS["bad"]})
    return body, label, _nav(pathname or "/")


# Live-dot pulse + dropdown dark styling (Dash serves anything under assets/, but
# inlining keeps the dashboard a single deployable module).
app.index_string = """<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>
{%favicon%}{%css%}<style>
@keyframes pulse {0%{box-shadow:0 0 0 0 rgba(45,212,167,.6)}70%{box-shadow:0 0 0 8px rgba(45,212,167,0)}100%{box-shadow:0 0 0 0 rgba(45,212,167,0)}}
.live-dot{animation:pulse 1.6s infinite}
.ctl .Select-control,.ctl .Select-menu-outer,.ctl div[class*="control"],.ctl div[class*="menu"]{background:#141b27!important;border-color:#222d3d!important;color:#e8eef6!important}
.ctl div[class*="singleValue"],.ctl div[class*="option"]{color:#e8eef6!important}
body{margin:0}::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-thumb{background:#222d3d;border-radius:6px}
</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
