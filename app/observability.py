import json, logging, time, uuid
from prometheus_client import Counter, Histogram, Gauge

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger=logging.getLogger("petition_triage")
REQUESTS=Counter("triage_requests_total","Triage requests",["status"])
RUN_SECONDS=Histogram("triage_run_seconds","End-to-end run duration")
AGENT_STEPS=Counter("triage_agent_steps_total","Agent steps",["agent","tool"])
TOKENS=Counter("triage_tokens_total","Estimated tokens",["kind"])
COST=Counter("triage_cost_usd_total","Estimated model cost USD")
QUEUE_DEPTH=Gauge("triage_queue_depth","Redis queue depth")
TOOL_RETRIES=Counter("triage_tool_retries_total","Bounded retrieval recovery attempts")
PROCESS_UPTIME=Gauge("triage_process_uptime_seconds","Process uptime in seconds")
_PROCESS_STARTED=time.time()
PROCESS_UPTIME.set_function(lambda:max(0,time.time()-_PROCESS_STARTED))

def event(name, **fields):
    cid=fields.pop("correlation_id",fields.get("run_id",str(uuid.uuid4())))
    logger.info(json.dumps({"timestamp":time.time(),"event":name,"correlation_id":cid,"event_name":name,**fields},default=str))
