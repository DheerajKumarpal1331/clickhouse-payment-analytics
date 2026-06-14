"""Postgres access for the merchant service (lazy psycopg2 connection pool,
RealDictCursor -> list[dict]). Parameterized queries only."""
from __future__ import annotations

from api.common.config import PG_DSN

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        import psycopg2.pool
        _pool = psycopg2.pool.SimpleConnectionPool(1, 8, dsn=PG_DSN)
    return _pool


def query(sql: str, params: tuple | None = None) -> list[dict]:
    import psycopg2.extras
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall() if cur.description else []
        conn.commit()
        return [dict(r) for r in rows]
    finally:
        pool.putconn(conn)


def query_one(sql: str, params: tuple | None = None) -> dict:
    rows = query(sql, params)
    return rows[0] if rows else {}
