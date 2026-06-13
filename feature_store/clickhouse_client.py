"""Dependency-light ClickHouse HTTP client (stdlib urllib only).

query()   -> list[dict] (FORMAT JSONEachRow)
execute() -> None       (DDL / INSERT ... SELECT)
Auth via X-ClickHouse-User/Key headers parsed from the CH_URL userinfo.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from config import CH_URL


def _endpoint() -> tuple[str, dict]:
    u = urllib.parse.urlparse(CH_URL)
    base = f"{u.scheme}://{u.hostname}:{u.port or 8123}/"
    headers = {}
    if u.username:
        headers["X-ClickHouse-User"] = urllib.parse.unquote(u.username)
    if u.password:
        headers["X-ClickHouse-Key"] = urllib.parse.unquote(u.password)
    return base, headers


def execute(sql: str, settings: dict | None = None) -> None:
    base, headers = _endpoint()
    params = {"default_format": "JSONEachRow"}
    if settings:
        params.update(settings)
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=sql.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        resp.read()


def query(sql: str) -> list[dict]:
    base, headers = _endpoint()
    url = base + "?" + urllib.parse.urlencode({"default_format": "JSONEachRow"})
    req = urllib.request.Request(url, data=sql.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]
