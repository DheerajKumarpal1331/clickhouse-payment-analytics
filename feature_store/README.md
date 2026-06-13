# Feature Store (Phase 6)

Computes ML features in ClickHouse and serves them two ways: **online** (latest
vector per entity, ~1ms lookup for the fraud API) and **offline** (point-in-time
history for leakage-free training). Features are computed **server-side** via
`INSERT … SELECT` — no data round-trips through Python.

## Features

| Entity | Features |
|---|---|
| **merchant** | `transaction_velocity` (txns/last-hr), `success_rate`, `refund_rate`, `chargeback_ratio` |
| **customer** | `avg_ticket_size`, `transaction_frequency`, `merchant_diversity` |
| **device** | `device_velocity`, `location_changes` (distinct cities/24h), `failure_rate` |

## Layout

```
feature_store/
├── definitions.py        # registry: entity -> features + online/offline SQL
├── clickhouse_client.py  # stdlib-only HTTP client (query / execute)
├── pipelines/            # per-entity SQL builders (merchant/customer/device)
├── online/               # materialize.py (-> online_features) + serving.py (lookup)
├── offline/              # materialize.py (daily snapshots) + training_set.py (ASOF PIT)
└── refresh.py            # entrypoint: --once | --loop, --mode online|offline|both
```

Backing tables live in `clickhouse/features/` (Phase 5): `online_features`
(ReplacingMergeTree, latest-per-entity) and `offline_features` (MergeTree,
append-only with `feature_time`).

## Run

```bash
pip install -r feature_store/requirements.txt          # only prometheus-client
export CH_URL=http://analytics:analytics_secret@localhost:8123

python -m feature_store.refresh --once                 # one online+offline pass
python -m feature_store.refresh --loop                 # continuous (+ /metrics :9000)
```

Containerized: the `feature-store` service (compose `ml` profile) runs
`python -m feature_store.refresh --loop`. Schedule the offline pass from Airflow
so a real PIT history accumulates.

## Serving (read path)

```python
from feature_store.online import get_online_features
get_online_features("merchant", "M0000042")
# {'transaction_velocity': 3.0, 'success_rate': 0.94, 'refund_rate': 0.01, 'chargeback_ratio': 0.0}
```

## Training (point-in-time)

`offline/training_set.py` builds the **ASOF LEFT JOIN** (`feature_time <=
label_time`) so each training row only sees features known before its label —
the leakage guard. `point_in_time(entity_type, id, as_of)` does the same for a
single lookup.
