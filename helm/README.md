# Helm chart (Phase 13)

`helm/payment-analytics` packages the whole platform as one values-driven chart —
the same topology as the [raw k8s manifests](../k8s/), but parameterised so a
single `-f values.yaml` tailors it per environment.

## Install

```bash
# build & push the app images the chart references (api / dashboard / mlflow):
#   docker build -t <registry>/payment-analytics/api:latest -f docker/api/Dockerfile .
helm install payments ./helm/payment-analytics \
  --namespace payments --create-namespace \
  --set image.registry=<registry> \
  --set secrets.postgresPassword=... --set secrets.clickhousePassword=...

helm template payments ./helm/payment-analytics   # render without applying
helm lint ./helm/payment-analytics                 # validate
```

## What `values.yaml` controls

| Key | Effect |
|---|---|
| `image.registry` / `image.tag` | where the built `api`/`dashboard`/`mlflow` images come from |
| `secrets.create` / `secrets.existingSecret` | chart-managed Secret vs. an externally-managed one (Vault / External Secrets) |
| `postgres/clickhouse/kafka.enabled` | toggle each stateful store (off when using managed services) |
| `postgres/clickhouse.storage`, `*.resources` | PVC sizes and requests/limits |
| `apis[]` | list of FastAPI services; each gets a Deployment + Service, env wired from secret/config, optional `hpa` |
| `dashboard.enabled`, `airflow.enabled`, `monitoring.enabled` | optional tiers |
| `ingress.enabled` / `className` / `hostSuffix` | external routing |

The `apis` list is the heart of it — the fraud API carries an `hpa` block
(3→12 pods at 65% CPU) because it is the latency-critical hot path; the others
run fixed replicas. Adding a service is a list entry, not a new template.

## Production

Set `secrets.create=false` with `secrets.existingSecret`, point `image.registry`
at your registry, and disable the bundled stores (`postgres/clickhouse/kafka.enabled=false`)
in favour of managed services / operators — see the
[deployment guide](../deployment/README.md).
