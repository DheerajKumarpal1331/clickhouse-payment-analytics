"""Minimal ClickHouse sink over the HTTP interface (stdlib only — no driver
dependency, so the consumer stays light and the wide fact schema is handled by
ClickHouse, not Python).

Inserts use `FORMAT JSONEachRow` with:
  - input_format_skip_unknown_fields=1  → tolerate event fields the table lacks
  - input_format_null_as_default=1      → nulls fall back to column defaults
  - date_time_input_format=best_effort  → parse 'YYYY-MM-DD HH:MM:SS' timestamps
So an OLTP-CDC event (narrow) and a gateway event (wide) both land in the same
table; missing columns take their DDL defaults.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

_SETTINGS = {
    "input_format_skip_unknown_fields": 1,
    "input_format_null_as_default": 1,
    "date_time_input_format": "best_effort",
}


class ClickHouseError(Exception):
    pass


class ClickHouseSink:
    def __init__(self, url: str, database: str):
        # url like http://user:pass@host:8123
        p = urllib.parse.urlparse(url)
        self.base = f"{p.scheme}://{p.hostname}:{p.port or 8123}"
        self.auth = (p.username or "default", p.password or "")
        self.database = database

    def _post(self, query: str, body: bytes) -> None:
        params = {"query": query, "database": self.database, **_SETTINGS}
        req = urllib.request.Request(f"{self.base}/?{urllib.parse.urlencode(params)}", data=body)
        cred = f"{self.auth[0]}:{self.auth[1]}"
        import base64
        req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except HTTPError as e:
            raise ClickHouseError(f"{e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except URLError as e:
            raise ClickHouseError(f"connect: {e}") from e
        except OSError as e:
            # ConnectionResetError / broken pipe — transient; let the consumer retry.
            raise ClickHouseError(f"socket: {e}") from e

    def insert(self, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        body = "\n".join(json.dumps(r, default=str) for r in rows).encode()
        self._post(f"INSERT INTO {self.database}.{table} FORMAT JSONEachRow", body)
        return len(rows)

    def ping(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base}/ping", timeout=5) as r:
                return r.read().strip() == b"Ok."
        except (HTTPError, URLError):
            return False
