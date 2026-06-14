"""Watermark CDC operator: Postgres OLTP -> ClickHouse warehouse.

Reads every row past the persisted ``(wm, id)`` cursor for a registered source,
in ``(wm, id)`` order so a same-timestamp boundary is never skipped or
double-loaded, projects it to the target fact/dimension shape, bulk-inserts via
JSONEachRow, and only then advances the cursor — so a mid-run failure re-reads
the slice rather than losing it (at-least-once; the dimension targets are
ReplacingMergeTree and the facts are keyed, so a replayed slice is idempotent on
merge / dedupe at read time).

Pulls in bounded pages (``batch_size``) until the source is drained or
``max_batches`` is hit, keeping memory flat on a large backlog. The number of
rows loaded is pushed to XCom for the data-quality / alerting tasks downstream.
"""
from __future__ import annotations

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

from operators import clients
from operators.cdc_queries import CDC_SOURCES


class PostgresToClickHouseOperator(BaseOperator):
    ui_color = "#2b6cb0"
    template_fields = ("source",)

    @apply_defaults
    def __init__(self, source: str, batch_size: int = 20_000,
                 max_batches: int = 1000, **kwargs):
        super().__init__(**kwargs)
        self.source = source            # may be a template (e.g. backfill param)
        self.batch_size = batch_size
        self.max_batches = max_batches

    def execute(self, context) -> int:
        if self.source not in CDC_SOURCES:    # validated post-templating
            raise ValueError(f"unknown CDC source '{self.source}'; "
                             f"known: {sorted(CDC_SOURCES)}")
        spec = CDC_SOURCES[self.source]
        wm, last_id = clients.get_watermark(self.source)
        self.log.info("CDC %s starting from cursor wm=%s id=%s -> %s",
                      self.source, wm, last_id, spec.ch_table)

        total = 0
        for _ in range(self.max_batches):
            sql = (f"{spec.sql} WHERE ({spec.wm} > %(wm)s::timestamptz) "
                   f"OR ({spec.wm} = %(wm)s::timestamptz AND {spec.idc} > %(id)s) "
                   f"ORDER BY {spec.wm}, {spec.idc} LIMIT %(limit)s")
            rows = clients.pg_fetch(sql, {"wm": wm, "id": last_id, "limit": self.batch_size})
            if not rows:
                break

            ch_rows, slice_wm, slice_id = [], wm, last_id
            for r in rows:
                rid = int(r.pop("_id"))
                raw_wm = r.pop("_wm")
                slice_wm = (raw_wm.strftime("%Y-%m-%d %H:%M:%S.%f")
                            if hasattr(raw_wm, "strftime") else str(raw_wm))
                slice_id = rid
                ch_rows.append(spec.map(r))

            clients.ch_insert_rows(spec.ch_table, ch_rows)
            clients.set_watermark(self.source, slice_wm, slice_id)  # advance only after insert
            wm, last_id = slice_wm, slice_id
            total += len(ch_rows)
            self.log.info("CDC %s loaded %s rows (running total %s); cursor wm=%s id=%s",
                          self.source, len(ch_rows), total, wm, last_id)

            if len(rows) < self.batch_size:
                break

        self.log.info("CDC %s done: %s rows loaded into %s", self.source, total, spec.ch_table)
        context["ti"].xcom_push(key="rows_loaded", value=total)
        return total
