# Plotly Dash Analytics (Phase 9)

Five enterprise dashboards over the ClickHouse marts (Phase 5), served as one
multi-page Dash app with a sidebar. Each page's `layout()` queries fresh data on
navigation; `dashboard/data.py` is a stdlib ClickHouse client that returns empty
frames on failure so pages never blank-screen.

| Page | Route | KPIs | Charts |
|---|---|---|---|
| **Executive** | `/` | TPV, Revenue (MDR), Transactions, Active Merchants | daily TPV+txns, success-rate, method mix |
| **Merchant** | `/merchant` | Merchant Growth, RFM, Churn Risk | growth, RFM segments, frequency×monetary scatter |
| **Fraud** | `/fraud` | Fraud Rate, Fraud Loss, Model Performance | fraud trend, daily loss, scoring by risk band |
| **Settlement** | `/settlement` | Settlement TAT, Failed Settlements | TAT trend, failures & net settled |
| **Support** | `/support` | SLA Compliance, Ticket Volume | volume+breaches, tickets by category |

Layout: `dashboard/{executive,merchant,fraud,settlement,support}/view.py`
(one `layout(days)` each), `data.py` (queries), `theme.py` (KPI cards, dark
styling), `app.py` (nav + routing, exposes `server` for gunicorn).

## Run

```bash
pip install -r dashboard/requirements.txt
export CH_URL=http://analytics:analytics_secret@localhost:8123
python -m dashboard.app                 # dev server on :8050
# prod: gunicorn dashboard.app:server --bind 0.0.0.0:8050
```

Containerized: `docker compose --profile apps up -d` → dashboard on **:8050**
(`docker/dashboard/Dockerfile` runs gunicorn). Reads the same marts the
Analytics API serves.

## Notes

- **RFM** is computed in `data.py` from `merchant_daily_summary` (recency =
  days since last activity, frequency = txns, monetary = gross) with quintile
  scoring → segments (Champions / Loyal / Recent / At Risk / Needs Attention).
- **Churn risk** = merchants with no transactions in the last 14 days.
- **Model Performance** on the Fraud page shows live scoring volume by risk
  band; the precision/recall/PR-AUC of each model version live in MLflow
  (Phase 7), linked from the ops runbook.
