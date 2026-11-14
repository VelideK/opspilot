# OpsPilot

OpsPilot is a read-only service-monitoring MVP built with Python and FastAPI.
It periodically checks configured HTTP endpoints, exposes health and latency
metrics for Prometheus, and emits JSON logs for Grafana Loki. Grafana dashboards,
Docker Compose, Kubernetes manifests, and an AWS EKS Terraform scaffold are
included.

OpsPilot does not change infrastructure, restart services, or perform automatic
remediation.

## Stack

- **API and checks:** Python, FastAPI, `urllib`
- **Metrics and dashboards:** Prometheus, Grafana
- **Logs:** JSON logs, Grafana Alloy, Loki
- **Local runtime:** Docker, Docker Compose
- **Deployment scaffolding:** Kubernetes, Terraform, AWS EKS
- **Automation:** GitHub Actions, Python tests, Bash health-check script

## Run locally with Docker Compose

Requirements: Docker with the Compose plugin.

Create a local config (it is git-ignored) and set a Grafana password in the
current PowerShell session:

```powershell
Copy-Item opspilot.example.json opspilot.json
$env:GRAFANA_ADMIN_PASSWORD = "choose-a-local-password"
docker compose up --build -d
```

Services bind to loopback only:

- OpsPilot API: <http://localhost:8000/docs>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (user `admin`, password from the environment)
- Loki: <http://localhost:3100>

The Compose stack provisions Prometheus and Loki data sources and an OpsPilot
dashboard in Grafana. Grafana Alloy reads OpsPilot's JSON log file from a shared
volume and ships it to Loki. In Grafana Explore, a query such as
`{job="opspilot"}` shows the logs.

Stop the services with `docker compose down`. To also erase the local metrics,
logs, and dashboard data, use `docker compose down -v`.

## Run the API without Docker

Requirements: Python 3.10 or newer.

```powershell
python -m pip install -e ".[test]"
$env:OPSPILOT_CONFIG = "opspilot.example.json"
uvicorn opspilot.api:app --reload
```

The monitor checks all configured endpoints concurrently every 30 seconds. Set
`OPSPILOT_INTERVAL_SECONDS` to change the interval. Keep the service to one
process/replica: scheduling and metric state are in memory, so multiple workers
would run duplicate checks.

### API

- `GET /healthz` — liveness check
- `GET /readyz` — readiness check
- `GET /api/v1/checks` — configured check definitions
- `GET /api/v1/results` — most recent results
- `POST /api/v1/checks/run` — run checks immediately
- `GET /metrics` — Prometheus exposition format

Only 2xx responses are healthy. Network errors and non-2xx responses are
reported as unhealthy results; invalid configuration prevents the application
from starting.

The immediate-run endpoint is intended for trusted local or cluster use. Keep
the API behind a private network boundary; do not expose it directly to the
public internet.

## Configuration

Copy [opspilot.example.json](./opspilot.example.json) to `opspilot.json` and
replace its example endpoint. Each check needs a unique name and an `http` or
`https` URL. `timeout_seconds` is optional and defaults to 5.

Do not include credentials or secrets in URLs. OpsPilot is read-only and sends
HTTP GET requests to the endpoints you configure.

The CLI remains available for a one-time check:

```powershell
python -m opspilot --config opspilot.json
python -m opspilot --config opspilot.json --json
```

## Kubernetes

The [Kubernetes manifest](./k8s/opspilot.yaml) creates a namespace, a sample
ConfigMap, a single-replica Deployment, and an internal ClusterIP Service. It
includes startup, liveness, and readiness probes, resource bounds, a non-root
container security context, and Prometheus scrape annotations.

Build and publish the image to a registry reachable by your cluster, update the
image in the manifest, then deploy:

```powershell
kubectl apply -f k8s/opspilot.yaml
kubectl -n opspilot port-forward service/opspilot 8000:8000
```

The manifest deploys OpsPilot only; it assumes a Prometheus installation that
honors the scrape annotations. Configure log collection for your Kubernetes
cluster separately.

## AWS EKS with Terraform

The [Terraform scaffold](./infra/terraform) provisions a VPC, a single NAT
gateway, and an EKS cluster with a small managed node group. It is not a
zero-cost setup: EKS, EC2, and NAT gateway resources incur AWS charges.

From PowerShell:

```powershell
Copy-Item infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Edit `terraform.tfvars` before continuing:

- Set `cluster_version` to a Kubernetes version currently supported by EKS in
  the selected region.
- Replace the example documentation-only CIDR with your trusted client CIDR.
  Terraform rejects `0.0.0.0/0`.

Then run `terraform init` and inspect `terraform plan` from
`infra/terraform`. Apply only after reviewing the plan and AWS cost implications.
Use the standard AWS credential chain; never put access keys in Terraform
variables or commit a real `terraform.tfvars` file.

## Bash health check

With the API running, use Bash and `curl` to verify its liveness and readiness:

```bash
bash scripts/check-health.sh
```

Set `OPSPILOT_URL` to use a different base URL.

## Tests and CI

Install the test extra and run the standard-library test runner:

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
```

GitHub Actions runs the tests on Python 3.10, 3.11, and 3.12 and builds the
container image for pushes and pull requests. Deployment remains an explicit
operator action; AWS credentials and deployment secrets are not configured in
CI.

## Current limitations

- Checks are HTTP-only and do not support custom headers, authentication, or
  alert delivery.
- Results and metrics are held in process memory; there is no database or
  multi-instance coordination.
- The Compose observability stack is for local development. Production
  deployments need durable storage, access control, secrets management, and
  operational alerting.
