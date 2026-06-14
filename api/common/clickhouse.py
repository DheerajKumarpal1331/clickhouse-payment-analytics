"""ClickHouse HTTP client (stdlib urllib) for the analytics + fraud services."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from api.common.config import CH_URL


def _endpoint() -> tuple[str, dict]:
    u = urllib.parse.urlparse(CH_URL)
    base = f"{u.scheme}://{u.hostname}:{u.port or 8123}/"
    headers = {}
    if u.username:
        headers["X-ClickHouse-User"] = urllib.parse.unquote(u.username)
    if u.password:
        headers["X-ClickHouse-Key"] = urllib.parse.unquote(u.password)
    return base, headers


def query(sql: str) -> list[dict]:
    base, headers = _endpoint()
    url = base + "?" + urllib.parse.urlencode({"default_format": "JSONEachRow"})
    req = urllib.request.Request(url, data=sql.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def query_one(sql: str) -> dict:
    rows = query(sql)
    return rows[0] if rows else {}
