# Kubernetes manifests (Phase 13)

Raw manifests for deploying the platform to a Kubernetes cluster, appliable with
`kubectl apply -k k8s/` (Kustomize). This is the self-hosted reference; the
[production notes](../deployment/README.md) call out where managed services /
operators replace these for scale.

## Layout (apply order)

| File | Resources |
|---|---|
| `00-namespace.yaml` | `payments` namespace |
| `01-config.yaml` | non-secret `ConfigMap` (hosts, ports, DB names) |
| `02-secret.example.yaml` | **template** — copy to `02-secret.yaml`, fill, never commit |
| `10-postgres.yaml` | Postgres `StatefulSet` + headless `Service` + PVC |
| `11-clickhouse.yaml` | ClickHouse `StatefulSet` + `Service` + PVC |
| `12-kafka.yaml` | ZooKeeper + Kafka `StatefulSet`s + `Service`s |
| `20-mlflow.yaml` | MLflow `Deployment` + `Service` |
| `30-apis.yaml` | fraud / merchant / analytics `Deployment`s + `Service`s + fraud `HPA` |
| `31-dashboard.yaml` | Plotly Dash `Deployment` + `Service` |
| `40-airflow.yaml` | Airflow web + scheduler (minimal; prod = official chart) |
| `50-monitoring.yaml` | Prometheus + Grafana `Deployment`s + `Service`s |
| `60-ingress.yaml` | host-based `Ingress` to APIs / dashboard / Grafana |

## Deploy

```bash
cp k8s/02-secret.example.yaml k8s/02-secret.yaml   # fill in real values (gitignored)
# build & push images your registry expects (payment-analytics/api, .../dashboard, .../mlflow):
#   docker build -t <registry>/payment-analytics/api:latest -f docker/api/Dockerfile .
kubectl apply -k k8s/
kubectl -n payments get pods,svc,hpa
```

The stateful stores (Postgres/ClickHouse/Kafka) use `volumeClaimTemplates`, so a
default `StorageClass` must exist. Schema/IaC (Postgres DDL, ClickHouse DDL,
Kafka topics) is applied with the same `postgres/apply.sh` / `clickhouse` /
topic-creation steps as Compose — run them as `Job`s or an init step against the
running services.

## Production swaps

- **Kafka** → Strimzi operator, 3 brokers, RF=3
- **ClickHouse** → Altinity operator, sharded + replicated
- **PostgreSQL** → managed (RDS / Cloud SQL) + read replicas
- **Airflow** → official Helm chart, `KubernetesExecutor`
- **Monitoring** → kube-prometheus-stack (Operator + ServiceMonitors)
- **Secrets** → External Secrets Operator / Sealed Secrets / Vault
- **TLS** → cert-manager on the Ingress

A values-driven [Helm chart](../helm/) packages the same topology.
