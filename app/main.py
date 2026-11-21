import json
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import make_asgi_app
from redis.asyncio import Redis

from app.config import REDIS_URL, RATE_LIMIT_PER_MINUTE
from app.schemas import Petition
from app.storage import (
    create_run,
    get_run,
    add_feedback,
    feedback_summary,
    quarantine_record,
)
from app.observability import event, REQUESTS, QUEUE_DEPTH


app = FastAPI(
    title="Academic Petition Triage",
    version="1.0.0",
    description=(
        "Evidence-grounded decision support. "
        "A human examination officer makes all final decisions."
    ),
)
app.mount("/metrics", make_asgi_app())

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from app.tracing import configure_tracing

    configure_tracing("petition-api")
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass

redis = Redis.from_url(REDIS_URL, decode_responses=True)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    qid = str(uuid.uuid4())

    try:
        body = await request.json()
    except Exception:
        body = {"unreadable_body": True}

    errors = [
        {
            "field": ".".join(map(str, error.get("loc", []))),
            "code": error.get("type"),
            "message": error.get("msg"),
        }
        for error in exc.errors()
    ]

    quarantine_record(qid, body, errors)
    event("request_quarantined", correlation_id=qid, errors=errors)

    return JSONResponse(
        status_code=422,
        content={
            "detail": "request rejected at ingestion boundary",
            "quarantine_id": qid,
            "field_errors": errors,
        },
    )


@app.get("/")
async def home():
    return FileResponse("app/static/index.html")


@app.middleware("http")
async def limits(request: Request, call_next):
    # Rate-limit new petition submissions only.
    # Status polling and health/metrics reads do not consume the submission limit.
    if request.method != "POST" or request.url.path != "/v1/runs":
        return await call_next(request)

    key = "rl:" + (request.client.host if request.client else "unknown")
    count = await redis.incr(key)

    if count == 1:
        await redis.expire(key, 60)

    if count > RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded"},
        )

    return await call_next(request)


@app.get("/health")
async def health():
    try:
        await redis.ping()
        return {"status": "ok", "queue": "ok"}
    except Exception as exc:
        raise HTTPException(503, "queue unavailable") from exc


@app.post("/v1/runs", status_code=202)
async def submit(petition: Petition):
    run_id = str(uuid.uuid4())
    data = petition.model_dump()
    create_run(run_id, data)

    try:
        await redis.rpush(
            "triage:queue",
            json.dumps({"run_id": run_id, "petition": data}),
        )
        QUEUE_DEPTH.set(await redis.llen("triage:queue"))
        REQUESTS.labels("queued").inc()
        event("run_submitted", run_id=run_id, petition_id=data["petition_id"])
    except Exception as exc:
        from app.storage import update_run

        update_run(
            run_id,
            "failed",
            {
                "status": "failed",
                "escalation_reason": "queue unavailable",
            },
        )
        raise HTTPException(503, "queue unavailable") from exc

    return {
        "run_id": run_id,
        "status": "queued",
        "status_url": f"/v1/runs/{run_id}",
    }


@app.get("/v1/runs/{run_id}")
async def status(run_id: str):
    row = get_run(run_id)

    if not row:
        raise HTTPException(404, "run not found")

    return {
        "run_id": run_id,
        "status": row["status"],
        "result": row["result"],
        "created_at": row["created_at"],
    }


@app.post("/v1/runs/{run_id}/feedback")
async def feedback(run_id: str, body: dict):
    if not get_run(run_id):
        raise HTTPException(404, "run not found")

    if not isinstance(body.get("satisfactory"), bool):
        raise HTTPException(422, "satisfactory must be boolean")

    add_feedback(
        run_id,
        body["satisfactory"],
        str(body.get("reason", ""))[:500],
    )

    return {
        "accepted": True,
        "aggregate": feedback_summary(),
    }


@app.get("/v1/feedback/summary")
async def feedback_stats():
    return feedback_summary()


@app.get("/v1/corpus")
async def corpus_info():
    from app.retrieval import load_docs

    return {
        "source": "University of Delhi Ordinance VII",
        "documents": len(load_docs()),
        "index_mode": (
            "FAISS when optional embedding dependencies are installed; "
            "lexical fallback otherwise"
        ),
    }