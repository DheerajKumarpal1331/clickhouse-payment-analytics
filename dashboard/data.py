"""Data access for the dashboards — queries the ClickHouse marts/views (Phase 5)
and returns pandas DataFrames. Stdlib HTTP client (no driver). Every query is
wrapped so a missing/empty table yields an empty frame rather than a 500, so
pages always render.

ClickHouse serializes UInt64/Decimal as JSON strings to keep precision, so the
helpers coerce numeric columns explicitly.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")


def _endpoint() -> tuple[str, dict]:
    u = urllib.parse.urlparse(CH_URL)
    base = f"{u.scheme}://{u.hostname}:{u.port or 8123}/"
    headers = {}
    if u.username:
        headers["X-ClickHouse-User"] = urllib.parse.unquote(u.username)
    if u.password:
        headers["X-ClickHouse-Key"] = urllib.parse.unquote(u.password)
    return base, headers


def q(sql: str, numeric: list[str] | None = None) -> pd.DataFrame:
    try:
        base, headers = _endpoint()
        url = base + "?" + urllib.parse.urlencode({"default_format": "JSONEachRow"})
        req = urllib.request.Request(url, data=sql.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = [json.loads(l) for l in resp.read().decode().splitlines() if l.strip()]
        df = pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
    for c in (numeric or []):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ----------------------------------------------------------------- executive
def exec_kpis(days: int = 30) -> dict:
    df = q(f"""SELECT sum(transactions) t, sum(tpv) tpv, sum(revenue) rev,
                      max(active_merchants) am, sum(fraud_txns) fr
               FROM {CH_DB}.mart_executive_kpis WHERE event_date >= today()-{days}""",
           ["t", "tpv", "rev", "am", "fr"])
    if df.empty:
        return {"transactions": 0, "tpv": 0, "revenue": 0, "active_merchants": 0, "fraud_txns": 0}
    r = df.iloc[0]
    return {"transactions": int(r.t or 0), "tpv": float(r.tpv or 0), "revenue": float(r.rev or 0),
            "active_merchants": int(r.am or 0), "fraud_txns": int(r.fr or 0)}


def exec_timeseries(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date, transactions, round(tpv) tpv,
                        round(success_rate,4) success_rate, active_merchants
                 FROM {CH_DB}.mart_executive_kpis WHERE event_date >= today()-{days} ORDER BY event_date""",
             ["transactions", "tpv", "success_rate", "active_merchants"])


def method_mix(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT payment_method, sum(txns) txns, round(sum(volume)) volume
                 FROM {CH_DB}.mart_method_mix WHERE event_date >= today()-{days}
                 GROUP BY payment_method ORDER BY volume DESC""", ["txns", "volume"])


# ------------------------------------------------------------------ merchant
def merchant_growth() -> pd.DataFrame:
    return q(f"""SELECT toString(month) month, uniqExact(merchant_id) active_merchants,
                        sum(txns) txns FROM {CH_DB}.merchant_monthly_summary
                 GROUP BY month ORDER BY month""", ["active_merchants", "txns"])


def merchant_rfm() -> pd.DataFrame:
    df = q(f"""SELECT merchant_id, dateDiff('day', max(event_date), today()) recency,
                      sum(txns) frequency, sum(gross_amount) monetary
               FROM {CH_DB}.merchant_daily_summary GROUP BY merchant_id""",
           ["recency", "frequency", "monetary"])
    if df.empty:
        return df
    # RFM scoring (1-5 quintiles); recency reversed (recent = high score)
    for col, asc in (("recency", False), ("frequency", True), ("monetary", True)):
        try:
            df[col[0].upper()] = pd.qcut(df[col].rank(method="first"), 5,
                                         labels=[1, 2, 3, 4, 5] if asc else [5, 4, 3, 2, 1]).astype(int)
        except Exception:
            df[col[0].upper()] = 3
    df["rfm"] = df.R.astype(str) + df.F.astype(str) + df.M.astype(str)
    df["segment"] = df.apply(_rfm_segment, axis=1)
    return df


def _rfm_segment(r) -> str:
    if r.R >= 4 and r.F >= 4:
        return "Champions"
    if r.F >= 4:
        return "Loyal"
    if r.R >= 4:
        return "Recent"
    if r.R <= 2 and r.F <= 2:
        return "At Risk"
    return "Needs Attention"


# --------------------------------------------------------------------- fraud
def fraud_daily(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date, txns, fraud_txns, round(fraud_rate,4) fraud_rate,
                        round(fraud_loss) fraud_loss, round(decline_rate,4) decline_rate
                 FROM {CH_DB}.mart_fraud_daily WHERE event_date >= today()-{days} ORDER BY event_date""",
             ["txns", "fraud_txns", "fraud_rate", "fraud_loss", "decline_rate"])


def fraud_scores(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT risk_level, sum(scored) scored, round(avg(avg_score),4) avg_score
                 FROM {CH_DB}.mart_fraud_scores WHERE event_date >= today()-{days}
                 GROUP BY risk_level""", ["scored", "avg_score"])


# ---------------------------------------------------------------- settlement
def settlement_daily(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(cycle_date) date, txns, round(net_settled) net,
                        failed_batches, round(avg_tat_minutes) tat
                 FROM {CH_DB}.mart_settlement_daily WHERE cycle_date >= today()-{days} ORDER BY cycle_date""",
             ["txns", "net", "failed_batches", "tat"])


# ------------------------------------------------------------------- support
def support_daily(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(toDate(event_time)) date, count() tickets,
                        sumIf(1, sla_breached=1) breached, uniqExact(category) categories
                 FROM {CH_DB}.fact_support_events WHERE event_time >= today()-{days}
                 GROUP BY toDate(event_time) ORDER BY date""", ["tickets", "breached", "categories"])


def support_by_category(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT category, count() tickets, sumIf(1, sla_breached=1) breached
                 FROM {CH_DB}.fact_support_events WHERE event_time >= today()-{days}
                 GROUP BY category ORDER BY tickets DESC""", ["tickets", "breached"])
