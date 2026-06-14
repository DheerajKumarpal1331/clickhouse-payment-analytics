"""Dependency-light store clients + watermark state shared by the operators and
sensors. ClickHouse over its HTTP interface via stdlib ``urllib`` (same pattern
as ml/clickhouse_client.py and dashboard/data.py); Postgres via ``psycopg2``,
which ships in the Airflow image (the metadata DB uses it).

Connection settings come from env (``CH_URL`` / ``PG_DSN``, injected by
docker-compose) with an Airflow Variable override, so a deployment can retarget
a DAG without an image rebuild.

Watermarks are persisted as Airflow Variables (one JSON blob per source table),
keeping the CDC cursor visible in the UI and durable across restarts. The cursor
is ``(wm, id)`` ordered exactly like the streaming producer's so same-timestamp
rows are never skipped or double-loaded at the slice boundary.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from airflow.models import Variable

EPOCH = "1970-01-01 00:00:00"
_WM_PREFIX = "cdc_watermark__"


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def _setting(var_key: str, env_key: str, default: str) -> str:
    """Airflow Variable wins, then env, then default."""
    return Variable.get(var_key, default_var=os.environ.get(env_key, default))


def ch_url() -> str:
    return _setting("ch_url", "CH_URL", "http://analytics:analytics_secret@clickhouse:8123")


def pg_dsn() -> str:
    return _setting("pg_dsn", "PG_DSN",
                    "postgresql://payments:payments_secret@postgres:5432/payments")


# --------------------------------------------------------------------------- #
# ClickHouse (stdlib HTTP)
# --------------------------------------------------------------------------- #
def _ch_endpoint() -> tuple[str, dict]:
    u = urllib.parse.urlparse(ch_url())
    base = f"{u.scheme}://{u.hostname}:{u.port or 8123}/"
    headers = {}
    if u.username:
        headers["X-ClickHouse-User"] = urllib.parse.unquote(u.username)
    if u.password:
        headers["X-ClickHouse-Key"] = urllib.parse.unquote(u.password)
    return base, headers


def ch_execute(sql: str, timeout: int = 600) -> None:
    """Run a statement that returns no rows (DDL, INSERT ... SELECT, OPTIMIZE)."""
    base, headers = _ch_endpoint()
    req = urllib.request.Request(base, data=sql.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def ch_query(sql: str, timeout: int = 600) -> list[dict]:
    """Run a SELECT, returning rows as dicts (JSONEachRow)."""
    base, headers = _ch_endpoint()
    url = base + "?" + urllib.parse.urlencode({"default_format": "JSONEachRow"})
    req = urllib.request.Request(url, data=sql.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def ch_scalar(sql: str, timeout: int = 600):
    """Run a SELECT expected to return a single value; None if no rows."""
    rows = ch_query(sql, timeout=timeout)
    if not rows:
        return None
    return next(iter(rows[0].values()))


def ch_insert_rows(table: str, rows: list[dict], timeout: int = 600) -> int:
    """Bulk-insert dict rows as JSONEachRow. Unlisted columns take their DDL
    defaults, so a partial projection is fine."""
    if not rows:
        return 0
    payload = (f"INSERT INTO {table} FORMAT JSONEachRow\n"
               + "\n".join(json.dumps(r, default=str) for r in rows))
    base, headers = _ch_endpoint()
    req = urllib.request.Request(base, data=payload.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout):
        pass
    return len(rows)


# --------------------------------------------------------------------------- #
# Postgres (psycopg2, RealDictCursor)
# --------------------------------------------------------------------------- #
def pg_fetch(sql: str, params: dict | None = None) -> list[dict]:
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(pg_dsn())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or {})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# watermark state (Airflow Variables)
# --------------------------------------------------------------------------- #
def get_watermark(source: str) -> tuple[str, int]:
    raw = Variable.get(_WM_PREFIX + source, default_var=None)
    if not raw:
        return EPOCH, 0
    c = json.loads(raw)
    return c.get("wm", EPOCH), int(c.get("id", 0))


def set_watermark(source: str, wm: str, last_id: int) -> None:
    Variable.set(_WM_PREFIX + source, json.dumps({"wm": wm, "id": int(last_id)}))


def reset_watermark(source: str, wm: str = EPOCH, last_id: int = 0) -> None:
    """Rewind a cursor — used by the backfill DAG to re-load a window."""
    set_watermark(source, wm, last_id)
