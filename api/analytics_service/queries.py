"""Analytics reads over the ClickHouse marts (Phase 5). Each dashboard maps to
one or more mart views; KPIs are point reads off the daily rollups."""
from __future__ import annotations

from api.common import clickhouse as ch
from api.common.config import CH_DB

DB = CH_DB


def kpis(days: int) -> dict:
    """Headline platform KPIs over the last N days (Executive). The ratio is
    computed in an outer query so the summed columns aren't nested in another
    aggregate (ClickHouse ILLEGAL_AGGREGATION otherwise)."""
    return ch.query_one(f"""
        SELECT transactions, tpv, revenue, active_merchants, fraud_txns,
               round(fraud_txns / nullIf(transactions, 0), 5) AS fraud_rate
        FROM (
            SELECT sum(transactions)     AS transactions,
                   round(sum(tpv))       AS tpv,
                   round(sum(revenue))   AS revenue,
                   max(active_merchants) AS active_merchants,
                   sum(fraud_txns)       AS fraud_txns
            FROM {DB}.mart_executive_kpis
            WHERE event_date >= today() - {days}
        )
    """)


def timeseries(days: int) -> list[dict]:
    return ch.query(f"""
        SELECT toString(event_date) AS date, transactions, round(tpv) AS tpv,
               round(revenue) AS revenue, round(success_rate, 4) AS success_rate,
               active_merchants, fraud_txns
        FROM {DB}.mart_executive_kpis
        WHERE event_date >= today() - {days}
        ORDER BY event_date
    """)


DASHBOARDS = {
    "executive": lambda d: {
        "kpis": kpis(d), "timeseries": timeseries(d),
        "method_mix": ch.query(
            f"SELECT payment_method, sum(txns) AS txns, round(sum(volume)) AS volume "
            f"FROM {DB}.mart_method_mix WHERE event_date >= today()-{d} GROUP BY payment_method ORDER BY volume DESC"),
    },
    "fraud": lambda d: {
        "daily": ch.query(
            f"SELECT toString(event_date) AS date, txns, fraud_txns, round(fraud_rate,4) AS fraud_rate, "
            f"round(fraud_loss) AS fraud_loss, round(decline_rate,4) AS decline_rate "
            f"FROM {DB}.mart_fraud_daily WHERE event_date >= today()-{d} ORDER BY event_date"),
        "by_scenario": ch.query(f"SELECT * FROM {DB}.mart_fraud_by_scenario"),
        "scores": ch.query(f"SELECT toString(event_date) AS date, risk_level, scored, round(avg_score,4) AS avg_score "
                           f"FROM {DB}.mart_fraud_scores WHERE event_date >= today()-{d} ORDER BY event_date"),
    },
    "settlement": lambda d: {
        "daily": ch.query(
            f"SELECT toString(cycle_date) AS date, txns, round(gross_amount) AS gross, round(net_settled) AS net, "
            f"failed_batches, round(avg_tat_minutes) AS avg_tat_minutes, merchants_settled "
            f"FROM {DB}.mart_settlement_daily WHERE cycle_date >= today()-{d} ORDER BY cycle_date"),
    },
    "operations": lambda d: {
        "approval": ch.query(
            f"SELECT toString(event_hour) AS hour, payment_method, txns, round(approval_rate,4) AS approval_rate, "
            f"round(avg_auth_latency_ms) AS avg_auth_latency_ms FROM {DB}.mart_ops_approval "
            f"ORDER BY event_hour DESC LIMIT 100"),
        "declines": ch.query(f"SELECT response_code, response_message, declines FROM {DB}.mart_ops_declines LIMIT 20"),
    },
}
