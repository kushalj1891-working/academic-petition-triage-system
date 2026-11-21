"""Deterministic offline smoke/evaluation runner. Reports observed values; does not invent before-change metrics."""
import json, sys, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.agents import run_triage

cases=json.loads((ROOT/'evals/scenarios.json').read_text())
seen=[]
for c in cases:
    if c.get('expected')=='schema_reject':
        from app.schemas import Petition
        try: Petition(**{**c['input'],'petition_id':'EVAL'}) ; ok=False
        except Exception: ok=True
        seen.append({"id":c['id'],"pass":ok,"actual":"schema_reject" if ok else "accepted"}); continue
    inp={"petition_id":"EVAL-"+c['id'],**c['input']}; out=run_triage(str(uuid.uuid4()),inp)
    clauses=[x['clause_id'] for x in out.get('citations',[])]
    ok=out['route']==c['expected_route'] and set(c['expected_clauses']).issubset(set(clauses))
    seen.append({"id":c['id'],"pass":ok,"actual_route":out['route'],"citations":clauses,"latency_ms":out['metrics']['latency_ms']})
summary={"scenario_count":len(seen),"passed":sum(x['pass'] for x in seen),"failed":sum(not x['pass'] for x in seen),"metrics":"Observed by this run; no pre-change baseline exists.","results":seen}
out=ROOT/'evals'/'latest-results.json'; out.write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
