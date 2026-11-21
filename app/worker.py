import asyncio, json, logging, time
from redis.asyncio import Redis
from app.config import REDIS_URL
from app.storage import update_run
from app.agents import run_triage
from app.observability import event, RUN_SECONDS, REQUESTS, QUEUE_DEPTH
from app.tracing import configure_tracing, traced

async def main():
    configure_tracing(); r=Redis.from_url(REDIS_URL,decode_responses=True); logging.basicConfig(level=logging.INFO)
    while True:
        item=await r.blpop("triage:queue",timeout=5)
        if not item: continue
        _,raw=item; job=json.loads(raw); run_id=job['run_id']; started=time.perf_counter(); update_run(run_id,"running")
        try:
            result=await asyncio.wait_for(asyncio.to_thread(run_triage,run_id,job['petition']),timeout=60); update_run(run_id,result['status'],result)
            REQUESTS.labels(result['status']).inc(); event("run_completed",run_id=run_id,status=result['status'],route=result['route'],latency_ms=result['metrics'].get('latency_ms'))
        except Exception as exc:
            update_run(run_id,"failed",{"run_id":run_id,"status":"failed","category":job['petition']['petition_type'],"route":"refer_to_committee","rationale":"Processing failed; no recommendation is available.","citations":[],"escalation_reason":"worker failure; human review required","prompt_version":"triage-v1","metrics":{}})
            REQUESTS.labels("failed").inc(); event("run_failed",run_id=run_id,error=type(exc).__name__)
        RUN_SECONDS.observe(time.perf_counter()-started); QUEUE_DEPTH.set(await r.llen("triage:queue"))

if __name__=="__main__": asyncio.run(main())
