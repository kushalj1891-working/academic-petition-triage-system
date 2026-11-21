# Runbook

## Start and verify
1. Install Docker Desktop with Compose v2.
2. Copy `.env.example` to `.env` if custom configuration is needed. Defaults need no secret.
3. Run `docker compose up --build -d`.
4. Verify `http://localhost:8000/health`; submit a synthetic petition at `http://localhost:8000/` or `POST /v1/runs`; poll the returned status URL.
5. Prometheus: `http://localhost:9090`; Grafana: `http://localhost:3000` (demo login admin/admin; change before shared use).
6. Stop with `docker compose down`; persisted run database and Redis data remain in named volumes. `docker compose down -v` deletes demo state.

## Incident response
### Redis unavailable / submissions fail
Symptoms: `/health` returns 503 or submissions return 503. Confirm `docker compose ps` and Redis logs; restore Redis with `docker compose restart redis`, then check health and retry a synthetic request. Failed submissions are marked failed rather than silently accepted.

### Worker/index failure
Symptoms: status stays queued/running or becomes failed; worker logs contain exception. Check worker and Redis health, confirm corpus file is mounted in the image, run `python -m app.ingest` in the worker container if rebuilding the vector index is needed, then restart worker. Failed runs explicitly have no confident recommendation; rerun only with synthetic inputs.

## Incident log (development)
2026-11-14: Initial PDF text extraction command was unavailable in the host image. Confirmed the PDF page count and rendered the specification pages to inspect the requirements visually. No source PDF was changed. Recovery: used the available PDF renderer and read the pages directly before implementing; no OCR or metrics were fabricated.
