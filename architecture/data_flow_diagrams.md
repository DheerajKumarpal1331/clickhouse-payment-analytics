# Data Flow Diagrams (DFD)

> Classic structured-analysis DFDs: Level 0 (context), Level 1 (major
> processes + data stores), and Level 2 detail for the two hardest flows
> (transaction processing, fraud scoring). External entities are rounded;
> processes are numbered; data stores are `[ ]`.

---

## Level 0 — Context diagram

The platform as a single process and who/what it exchanges data with.

```mermaid
flowchart LR
    CUST([Customer]) -->|payment| SYS
    MERCH([Merchant]) -->|onboarding, refunds,<br/>support tickets| SYS
    SYS -->|auth response, receipt| CUST
    SYS -->|settlements, reports,<br/>dashboards| MERCH

    ACQ([Acquirer / Networks / NPCI]) <-->|auth, clearing| SYS
    BANK([Sponsor Bank]) <-->|payouts, statements| SYS
    OPS([Internal Users:<br/>risk, ops, finance, support]) <-->|investigate, monitor| SYS

    SYS[["Payment Analytics Platform"]]
```

---

## Level 1 — Major processes and data stores

```mermaid
flowchart TD
    POS([POS / App / E-com]) --> P1

    P1[1.0 Accept &amp; Authorize<br/>Payment] --> D1["[ PostgreSQL OLTP ]"]
    P1 --> P2[2.0 Publish Events]
    P2 --> D2["[ Kafka topics ]"]
    D2 --> P3[3.0 Stream Ingest<br/>+ DLQ]
    P3 --> D3["[ ClickHouse facts ]"]
    P3 -.bad events.-> D7["[ dead_letter_events ]"]

    D3 --> P4[4.0 Aggregate<br/>Materialized Views]
    P4 --> D4["[ agg_* / mv_* ]"]

    D4 --> P5[5.0 Compute Features]
    P5 --> D5["[ Feature Store<br/>offline + online ]"]

    D5 --> P6[6.0 Train &amp; Register<br/>Models]
    P6 --> D6["[ MLflow registry ]"]

    P1 --> P7{{7.0 Score Fraud<br/>&lt;100ms}}
    D5 --> P7
    D6 --> P7
    P7 --> D3

    D4 --> P8[8.0 Serve Dashboards]
    P8 --> USERS([Business Users])

    P9[9.0 Orchestrate<br/>Airflow DAGs] --> P4
    P9 --> P5
    P9 --> P6
    P9 --> P10[10.0 Data Quality]
    P10 --> D8["[ dq_results ]"]

    P11[11.0 Settlement Engine] --> D1
    D3 --> P11
    P11 --> BANK([Sponsor Bank])
```

**Data stores**

| ID | Store | Engine |
|---|---|---|
| D1 | PostgreSQL OLTP | system of record |
| D2 | Kafka topics | event log |
| D3 | ClickHouse facts | OLAP |
| D4 | MV aggregates | OLAP derived |
| D5 | Feature store | offline + online |
| D6 | MLflow registry | model artifacts |
| D7 | Dead-letter events | quarantine |
| D8 | DQ results | scorecard |

---

## Level 2 — Process 1.0: Accept & Authorize Payment

```mermaid
flowchart TD
    IN([instrument + amount]) --> A1[1.1 Validate request<br/>+ idempotency check]
    A1 --> A2[1.2 Rules pre-check<br/>blacklist / velocity / ticket limit]
    A2 -->|blocked| RJ([decline + alert])
    A2 -->|pass| A3[1.3 Route by BIN / VPA]
    A3 --> A4[1.4 Forward to acquirer<br/>ISO 8583 0100]
    A4 --> EXT([Acquirer / Network / Issuer])
    EXT --> A5[1.5 Receive auth response]
    A5 --> A6[1.6 Capture<br/>compute fees sp_compute_fees]
    A6 --> W1["[ transaction_header + children ]"]
    A6 --> A7[1.7 Emit transaction_event]
    A7 --> W2["[ Kafka transaction_events ]"]
    A6 --> OUT([receipt / auth code])
```

Key data written: `transaction_header` (state machine), `authorization_records`,
`capture_records`, `transaction_fees`, `transaction_taxes`, then the published
`TransactionEvent`.

---

## Level 2 — Process 7.0: Score Fraud (< 100 ms)

```mermaid
flowchart TD
    EV([transaction event]) --> F1[7.1 Rules layer<br/>hard blocks]
    F1 -->|fail| BLK([block + open fraud_alert])
    F1 -->|pass| F2[7.2 Fetch online features<br/>single-key CH read]
    F2 --> R1["[ online_features /<br/>agg_velocity_5m ]"]
    F2 --> F3[7.3 Model predict_proba<br/>+ SHAP reason codes]
    F3 --> M1["[ MLflow model ]"]
    F3 --> F4[7.4 Band via dim_risk_levels]
    F4 --> DEC([allow / step-up / block])
    F4 --> F5[7.5 Async persist score]
    F5 --> W3["[ fraud_scores /<br/>fact_fraud_events ]"]
```

The synchronous path is 7.1 → 7.4 (returns the decision); 7.5 is fire-and-forget
so the write never counts against the latency budget. Confirmed outcomes (and
later chargebacks) loop back as labels into Process 6.0.

---

## Notes on flow semantics

- **Solid arrows** = synchronous request/response or in-line data write.
- **Dashed arrows** = async / error / feedback paths.
- The **hot path** (1.0 → 7.0) never depends on Airflow (9.0) or the MV layer
  being current — it reads pre-computed online features, so analytics lag never
  affects authorization.
- The **analytical path** (2.0 → 3.0 → 4.0 → 8.0) is eventually consistent with
  OLTP, lagging by seconds under normal stream load.
