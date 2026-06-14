"""Data access for the dashboards — queries ClickHouse and returns pandas
DataFrames. Stdlib HTTP client (no driver). Every query is wrapped so a
missing/empty table yields an empty frame rather than a 500, so pages always
render.

Most panels read the **live** `fact_transactions` directly (the stream the
generator feeds), aggregating with the fields the live event carries: amount,
is_success, fraud_label, payment_method, channel, mcc, merchant_id,
response_code. Business economics (MDR, GST, net settlement) are computed
in-query with standard Indian rates, since the heavy enrichment columns are
only populated for batch-loaded history.

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

GST = 0.18  # GST on payment fees

# Method-aware blended MDR (fraction of amount). Computed in-query so revenue is
# meaningful even though live events don't carry mdr_amount.
MDR = ("multiIf(payment_method='credit_card',0.0180,"
       "payment_method='emi',0.0200,"
       "payment_method='wallet',0.0150,"
       "payment_method='netbanking',0.0120,"
       "payment_method='debit_card',0.0090,"
       "0.0040)")  # upi / qr / default


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


def _one(df: pd.DataFrame, defaults: dict) -> dict:
    if df.empty:
        return dict(defaults)
    r = df.iloc[0]
    return {k: (float(r[k]) if r.get(k) is not None else v) for k, v in defaults.items()}


# ------------------------------------------------------------------ realtime
# Driven by `ingested_at` (when rows land), so these tick live with the stream.
def realtime_pulse(minutes: int = 5) -> dict:
    df = q(f"""SELECT count() txns, sum(amount) tpv,
                      avg(is_success) success_rate, sum(fraud_label) fraud
               FROM {CH_DB}.fact_transactions
               WHERE ingested_at >= now() - INTERVAL {minutes} MINUTE""",
           ["txns", "tpv", "success_rate", "fraud"])
    return {**_one(df, {"tpv": 0.0, "success_rate": 0.0}),
            "txns": int(_one(df, {"txns": 0})["txns"]),
            "fraud": int(_one(df, {"fraud": 0})["fraud"])}


def ingest_trend(minutes: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(toStartOfMinute(ingested_at)) minute,
                        count() txns, round(sum(amount)) tpv
                 FROM {CH_DB}.fact_transactions
                 WHERE ingested_at >= now() - INTERVAL {minutes} MINUTE
                 GROUP BY minute ORDER BY minute""", ["txns", "tpv"])


def recent_transactions(limit: int = 12) -> pd.DataFrame:
    return q(f"""SELECT formatDateTime(ingested_at,'%H:%i:%S') time, merchant_id,
                        round(amount,2) amount, payment_method method,
                        if(is_success=1,'✓','✗') ok, fraud_label fraud
                 FROM {CH_DB}.fact_transactions
                 ORDER BY ingested_at DESC LIMIT {limit}""", ["amount", "fraud"])


# ----------------------------------------------------------------- executive
def exec_summary(days: int = 30) -> dict:
    df = q(f"""SELECT count() txns, sum(amount) tpv,
                      sum(amount*{MDR}) revenue,
                      avg(is_success) success_rate,
                      countIf(is_success=0) declined,
                      uniqExact(merchant_id) merchants,
                      avg(amount) avg_ticket
               FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}""",
           ["txns", "tpv", "revenue", "success_rate", "declined", "merchants", "avg_ticket"])
    d = _one(df, {"tpv": 0.0, "revenue": 0.0, "success_rate": 0.0,
                  "avg_ticket": 0.0})
    d["txns"] = int(_one(df, {"txns": 0})["txns"])
    d["declined"] = int(_one(df, {"declined": 0})["declined"])
    d["merchants"] = int(_one(df, {"merchants": 0})["merchants"])
    return d


def exec_timeseries(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date, count() transactions,
                        round(sum(amount)) tpv, round(sum(amount*{MDR})) revenue,
                        round(avg(is_success),4) success_rate
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY event_date ORDER BY event_date""",
             ["transactions", "tpv", "revenue", "success_rate"])


def method_mix(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT payment_method, count() txns, round(sum(amount)) volume
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY payment_method ORDER BY volume DESC""", ["txns", "volume"])


def hourly_volume(hours: int = 24) -> pd.DataFrame:
    return q(f"""SELECT toString(toStartOfHour(event_time)) hour, count() txns,
                        round(sum(amount)) tpv
                 FROM {CH_DB}.fact_transactions
                 WHERE event_time >= now() - INTERVAL {hours} HOUR
                 GROUP BY hour ORDER BY hour""", ["txns", "tpv"])


# ------------------------------------------------------------------ merchant
def merchant_summary(days: int = 30) -> dict:
    df = q(f"""SELECT uniqExact(merchant_id) active,
                      uniqExactIf(merchant_id, event_date=today()) active_today,
                      round(avg(amount)) avg_ticket,
                      round(sum(amount)) tpv
               FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}""",
           ["active", "active_today", "avg_ticket", "tpv"])
    d = _one(df, {"avg_ticket": 0.0, "tpv": 0.0})
    d["active"] = int(_one(df, {"active": 0})["active"])
    d["active_today"] = int(_one(df, {"active_today": 0})["active_today"])
    # merchants whose first-ever transaction is today (newly live)
    nf = q(f"""SELECT count() n FROM (
                 SELECT merchant_id, min(event_date) f
                 FROM {CH_DB}.fact_transactions GROUP BY merchant_id
                 HAVING f = today())""", ["n"])
    d["new_today"] = int(_one(nf, {"n": 0})["n"])
    return d


def top_merchants(days: int = 30, limit: int = 10) -> pd.DataFrame:
    return q(f"""SELECT merchant_id, count() txns, round(sum(amount)) tpv,
                        round(avg(is_success)*100,1) success
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY merchant_id ORDER BY tpv DESC LIMIT {limit}""",
             ["txns", "tpv", "success"])


def merchant_daily_active(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date, uniqExact(merchant_id) merchants,
                        count() txns
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY event_date ORDER BY event_date""", ["merchants", "txns"])


def channel_mix(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT channel, count() txns, round(sum(amount)) volume
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY channel ORDER BY volume DESC""", ["txns", "volume"])


# --------------------------------------------------------------------- fraud
def fraud_summary(days: int = 30) -> dict:
    df = q(f"""SELECT count() txns, sum(fraud_label) fraud,
                      sumIf(amount, fraud_label=1) fraud_loss,
                      countIf(is_success=0) declined,
                      avgIf(1, fraud_label=1) dummy
               FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}""",
           ["txns", "fraud", "fraud_loss", "declined"])
    txns = int(_one(df, {"txns": 0})["txns"])
    fraud = int(_one(df, {"fraud": 0})["fraud"])
    declined = int(_one(df, {"declined": 0})["declined"])
    loss = _one(df, {"fraud_loss": 0.0})["fraud_loss"]
    return {"txns": txns, "fraud": fraud, "fraud_loss": loss, "declined": declined,
            "fraud_rate": (fraud / txns * 100) if txns else 0.0,
            "decline_rate": (declined / txns * 100) if txns else 0.0}


def fraud_trend(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date, sum(fraud_label) fraud_txns,
                        round(sum(fraud_label)/count()*100,3) fraud_rate,
                        round(sumIf(amount, fraud_label=1)) fraud_loss
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY event_date ORDER BY event_date""",
             ["fraud_txns", "fraud_rate", "fraud_loss"])


def fraud_by_method(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT payment_method, sum(fraud_label) fraud,
                        round(sum(fraud_label)/count()*100,3) rate
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY payment_method ORDER BY fraud DESC""", ["fraud", "rate"])


def decline_reasons(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT response_code, count() declines
                 FROM {CH_DB}.fact_transactions
                 WHERE event_date >= today()-{days} AND is_success=0 AND response_code != ''
                 GROUP BY response_code ORDER BY declines DESC LIMIT 8""", ["declines"])


# ---------------------------------------------------------------- settlement
# Settlement economics computed from successful transactions (T+1 model):
# net to merchant = gross − (MDR + GST on MDR).
def settlement_summary(days: int = 30) -> dict:
    df = q(f"""SELECT round(sumIf(amount, is_success=1)) gross,
                      round(sumIf(amount*{MDR}, is_success=1)) mdr,
                      round(sumIf(amount*{MDR}*{GST}, is_success=1)) gst,
                      round(sumIf(amount, is_success=1 AND event_date=today())) pending
               FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}""",
           ["gross", "mdr", "gst", "pending"])
    d = _one(df, {"gross": 0.0, "mdr": 0.0, "gst": 0.0, "pending": 0.0})
    d["net"] = d["gross"] - d["mdr"] - d["gst"]
    d["fees"] = d["mdr"] + d["gst"]
    return d


def settlement_trend(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(event_date) date,
                        round(sumIf(amount, is_success=1)) gross,
                        round(sumIf(amount - amount*{MDR}*(1+{GST}), is_success=1)) net,
                        round(sumIf(amount*{MDR}*(1+{GST}), is_success=1)) fees
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY event_date ORDER BY event_date""", ["gross", "net", "fees"])


def settlement_by_method(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT payment_method,
                        round(sumIf(amount, is_success=1)) gross,
                        round(sumIf(amount*{MDR}*(1+{GST}), is_success=1)) fees
                 FROM {CH_DB}.fact_transactions WHERE event_date >= today()-{days}
                 GROUP BY payment_method ORDER BY gross DESC""", ["gross", "fees"])


# ------------------------------------------------------------------- support
def support_summary(days: int = 30) -> dict:
    df = q(f"""SELECT count() tickets, sumIf(1, sla_breached=1) breached,
                      uniqExact(category) categories
               FROM {CH_DB}.fact_support_events WHERE event_time >= today()-{days}""",
           ["tickets", "breached", "categories"])
    t = int(_one(df, {"tickets": 0})["tickets"])
    b = int(_one(df, {"breached": 0})["breached"])
    return {"tickets": t, "breached": b, "categories": int(_one(df, {"categories": 0})["categories"]),
            "sla": (1 - b / t) * 100 if t else 100.0}


def support_daily(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT toString(toDate(event_time)) date, count() tickets,
                        sumIf(1, sla_breached=1) breached
                 FROM {CH_DB}.fact_support_events WHERE event_time >= today()-{days}
                 GROUP BY toDate(event_time) ORDER BY date""", ["tickets", "breached"])


def support_by_category(days: int = 30) -> pd.DataFrame:
    return q(f"""SELECT category, count() tickets, sumIf(1, sla_breached=1) breached
                 FROM {CH_DB}.fact_support_events WHERE event_time >= today()-{days}
                 GROUP BY category ORDER BY tickets DESC""", ["tickets", "breached"])
