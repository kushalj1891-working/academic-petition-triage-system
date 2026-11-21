# Academic Regulation and Student Petition Triage Service

Local, evidence-grounded decision support for synthetic academic petitions. The demonstrator uses University of Delhi Ordinance VII clauses for attendance. It never issues an official decision; all discretionary and uncertain cases route to a human.

## Start

Prerequisite: Docker Desktop with Compose v2.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Open <http://localhost:8000/>. Submit the included sample synthetic medical attendance case, then watch the result and clause citations. API docs are at <http://localhost:8000/docs>. Health: <http://localhost:8000/health>. Metrics: <http://localhost:8000/metrics>. Prometheus: <http://localhost:9090>. Grafana: <http://localhost:3000> (anonymous read-only access for this local demo). Jaeger traces: <http://localhost:16686>.

Example:

```powershell
$p = @{petition_id='SYN-01';petition_type='attendance';text='Serious illness caused attendance shortage; medical certificate is available. Please review the attendance rule.';attendance_percent=62;medical_documented=$true;semester='I'} | ConvertTo-Json
$run = Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/runs -ContentType application/json -Body $p
Invoke-RestMethod "http://localhost:8000$($run.status_url)"
```

## Services and commands

Compose starts six services: the FastAPI API, asynchronous Redis queue, separate agent-worker, Prometheus, Grafana, and Jaeger. SQLite run/feedback records and Redis state use named volumes. Three worker instances can be started with `docker compose up -d --scale agent-worker=3`; compare throughput and p95 at `/metrics` and in Locust. Run the optional stub load generator with `locust -f locustfile.py --host http://localhost:8000`.

To use vector embeddings, set an approved free local model identifier in `EMBEDDING_MODEL` in your local `.env`, then rebuild with `docker compose run --rm agent-worker python -m app.ingest`. Without that runtime configuration, the checked-in corpus uses a deterministic lexical fallback. Run the deterministic offline scenario evaluation in an environment with project dependencies installed: `python evals/run_eval.py`; output is written to `evals/latest-results.json`. No measured performance or quality baseline is claimed in advance.

Stop with `docker compose down`. `docker compose down -v` deletes local demo data.

## Data and safety

Only synthetic petitions. Never enter real student identifiers, academic records, or medical information. Sources and scope are in [docs/corpus-sources.md](docs/corpus-sources.md); coverage, known gaps, and unmeasured items are in [docs/limitations.md](docs/limitations.md). See [docs/runbook.md](docs/runbook.md) for recovery steps and incident notes; [docs/architecture.md](docs/architecture.md) for topology.

## Project map

```text
app/                 API, graph agents, retrieval, worker, SQLite and metrics
data/corpus.json     Curated sourced DU Ordinance VII clause excerpts
evals/               20 scenarios, prompt versions, evaluation runner
docs/                Architecture, corpus provenance, runbook, known limitations
monitoring/           Prometheus scrape configuration
grafana/              Datasource provisioning
report/                IEEE-style report source
outputs/               Final report PDF
Dockerfile             Shared API/worker image
docker-compose.yml     Five-service local stack
locustfile.py          Stub-provider load test profile
```
