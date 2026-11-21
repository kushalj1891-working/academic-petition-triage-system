"""LangGraph multi-agent workflow; regulation analyst and verification officer have distinct responsibilities."""
import re, time, uuid
from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.config import PROMPT_VERSION, MAX_STEPS
from app.observability import event, AGENT_STEPS, TOKENS, COST, TOOL_RETRIES
from app.retrieval import tool_search, tool_clause, tool_field
from app.tracing import traced

class State(TypedDict, total=False):
    run_id:str; petition:dict; category:str; passages:list; modifier:list; verification:dict; result:dict; steps:int; retry_count:int; started:float

@traced("intake_classification")
def classify(s:State):
    p=s['petition']; kind=p['petition_type']; AGENT_STEPS.labels("intake","field_lookup").inc(); tool_field("petition_id",p)
    if kind not in {"attendance","re_evaluation","re_registration","medical_leave","grade_grievance"}:
        return {"category":kind,"result":human(s,"outside supported corpus"),"steps":s.get('steps',0)+1}
    return {"category":kind,"steps":s.get('steps',0)+1}

@traced("regulation_analysis")
def analyze(s:State):
    started=time.perf_counter()
    p=s['petition']; kind=s['category']; query=p['text']
    if kind=="attendance": query += " minimum attendance eligibility examination semester" 
    AGENT_STEPS.labels("regulation_analyst","corpus_search").inc(); base=tool_search(query,category="attendance" if kind=="attendance" else kind)
    # Critical cross-reference: always perform a second derived query for modifiers, independent of base query ranking.
    modifier=[]
    if kind=="attendance":
        AGENT_STEPS.labels("regulation_analyst","corpus_search").inc()
        modifier=tool_search("attendance shortage condonation medical reasons discretion authority",category="attendance_modifier")
    event("retrieval_step",run_id=s['run_id'],agent="regulation_analyst",prompt_version=PROMPT_VERSION,base_query=query,base_clause_ids=[d['clause_id'] for d in base],modifier_query="attendance shortage condonation medical reasons discretion authority" if kind=="attendance" else None,modifier_clause_ids=[d['clause_id'] for d in modifier],step_latency_ms=round((time.perf_counter()-started)*1000,2),estimated_cost_usd=0.0)
    return {"passages":base,"modifier":modifier,"steps":s.get('steps',0)+1}

@traced("citation_verification")
def verify(s:State):
    passages=s.get('passages',[])+s.get('modifier',[]); cited=[]
    for d in passages:
        lookup=tool_clause(d['clause_id'])
        if lookup and lookup[0]['text']==d['text']: cited.append(d)
    valid=bool(s.get('passages')) and len(cited)==len(passages)
    p=s['petition']; kind=s['category']; escal=None; route="reject"; rationale="No supporting provision was retrieved; refer for manual review."
    if not valid: escal="retrieval or citation verification failed"
    elif kind=="attendance":
        required=next((d for d in cited if d['clause_id']=="VII(11)(a)"),None)
        cond=next((d for d in cited if d['clause_id']=="VII(11)(c)"),None)
        pct=p.get('attendance_percent')
        medical=p.get('medical_documented') is True
        # Duke's legacy ordinance clause expressly reserves authority to principal; no automated grant.
        if not required or pct is None: escal="attendance evidence or applicable base clause is missing"
        elif pct>=66.6667: route="grant_under_provision"; rationale="Reported attendance meets the two-thirds baseline in the cited clause, subject to confirmation of course, batch, and official records."
        elif medical and cond:
            route="refer_to_committee"; escal="medical hardship exclusion is discretionary and must be decided by the Principal"
            rationale="The base attendance rule is not met; the separately retrieved medical-hardship provision may allow a limited exclusion, but a human authority must decide each case."
        elif pct>=40:
            route="refer_to_committee"; escal="the clause permits a Principal's discretionary attendance exception; evidence and semester conditions require review"
            rationale="The reported attendance is below the baseline but in a range where the cited clause describes a discretionary route with conditions."
        else: rationale="Reported attendance is below the 40% floor stated for the discretionary ensuing-semester route, and no applicable medical exclusion was established."
    elif kind in {"re_evaluation","re_registration","medical_leave","grade_grievance"}:
        escal="petition type is outside the implemented DU attendance-focused corpus"
    if escal and route!="refer_to_committee": route="refer_to_committee"
    relevant=cited
    if kind=="attendance" and valid:
        relevant=[d for d in cited if d['clause_id']=="VII(11)(a)"]
        pct=p.get('attendance_percent')
        petition_text=p.get('text','').lower()
        medical_context=p.get('medical_documented') is True or any(term in petition_text for term in ("medical","illness","seriously ill","serious illness","accident"))
        if (pct is None or pct<66.6667) and medical_context:
            relevant.extend(d for d in cited if d['clause_id']=="VII(11)(c)")
        if any(term in petition_text for term in ("deadline","within five days","late application","application window")):
            relevant.extend(d for d in cited if d['clause_id']=="VII(11)(e)")
        if any(term in petition_text for term in ("one third","one-third","maximum exclusion","exclusion cap")):
            relevant.extend(d for d in cited if d['clause_id']=="VII(11)(f)")
    result={"run_id":s['run_id'],"status":"needs_human" if escal else "completed","category":kind,"route":route,"rationale":rationale,
            "citations":[{"document_id":d['document_id'],"clause_id":d['clause_id'],"title":d['title'],"text":d['text'],"source_url":d['source_url']} for d in relevant],
            "escalation_reason":escal,"prompt_version":PROMPT_VERSION,"metrics":{"agent_steps":s.get('steps',0)+1,"tool_calls":3+(1 if kind=="attendance" else 0),"estimated_prompt_tokens":0,"estimated_completion_tokens":0,"estimated_cost_usd":0.0}}
    event("verification",run_id=s['run_id'],verified=valid,citation_count=len(cited),route=route)
    return {"verification":{"valid":valid},"result":result,"retry_count":s.get('retry_count',0),"steps":s.get('steps',0)+1}

@traced("bounded_recovery_search")
def recovery_search(s:State):
    """One bounded, lexically different retrieval attempt after failed citation verification."""
    p=s['petition']; category=s['category'];
    AGENT_STEPS.labels("regulation_analyst","recovery_search").inc()
    TOOL_RETRIES.inc()
    base=tool_search(f"University of Delhi Ordinance VII {p.get('semester','')} attendance threshold clause",category="attendance" if category=="attendance" else category)
    modifier=tool_search("seriously ill accident medical certificates Principal exclude lectures decide merits",category="attendance_modifier") if category=="attendance" else []
    return {"passages":base,"modifier":modifier,"retry_count":s.get('retry_count',0)+1,"steps":s.get('steps',0)+1}

def human(s): return {"run_id":s['run_id'],"status":"needs_human","category":s.get('category','unknown'),"route":"refer_to_committee","rationale":"Human review required.","citations":[],"escalation_reason":"outside supported corpus","prompt_version":PROMPT_VERSION,"metrics":{"agent_steps":s.get('steps',0)+1}}

def build_graph():
    g=StateGraph(State); g.add_node("intake",classify); g.add_node("analyst",analyze); g.add_node("verification_officer",verify); g.add_node("recovery_search",recovery_search)
    g.set_entry_point("intake"); g.add_conditional_edges("intake",lambda s:"done" if s.get('result') else "analyst",{"done":END,"analyst":"analyst"})
    g.add_edge("analyst","verification_officer")
    g.add_conditional_edges("verification_officer",lambda s:"retry" if not s.get('verification',{}).get('valid') and s.get('retry_count',0)<1 else ("done" if s.get('result',{}).get('status')=='completed' else "human"),{"retry":"recovery_search","done":END,"human":"human_review"})
    g.add_edge("recovery_search","verification_officer")
    g.add_node("human_review",lambda s:{"result":s['result']}); g.add_edge("human_review",END)
    return g.compile()

def run_triage(run_id,petition):
    started=time.perf_counter(); result=build_graph().invoke({"run_id":run_id,"petition":petition,"steps":0,"retry_count":0,"started":started})['result']
    TOKENS.labels("prompt").inc(0); TOKENS.labels("completion").inc(0); COST.inc(0)
    result['metrics']['latency_ms']=round((time.perf_counter()-started)*1000,2); return result
