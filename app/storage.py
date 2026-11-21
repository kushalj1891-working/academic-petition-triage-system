import json, os, sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "./data/runs.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

def conn():
    c = sqlite3.connect(DB_PATH, timeout=10); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, petition_id TEXT, status TEXT, payload TEXT, result TEXT, created_at TEXT, updated_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, satisfactory INTEGER, reason TEXT, created_at TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS quarantine(id TEXT PRIMARY KEY, body TEXT, errors TEXT, created_at TEXT)")
    return c

def create_run(run_id, petition):
    now=datetime.now(timezone.utc).isoformat()
    with conn() as c: c.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?)",(run_id,petition['petition_id'],'queued',json.dumps(petition),None,now,now))

def update_run(run_id, status, result=None):
    now=datetime.now(timezone.utc).isoformat()
    with conn() as c: c.execute("UPDATE runs SET status=?, result=COALESCE(?,result), updated_at=? WHERE run_id=?",(status,json.dumps(result) if result else None,now,run_id))

def get_run(run_id):
    with conn() as c: row=c.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
    if not row: return None
    return {**dict(row),"payload":json.loads(row['payload']),"result":json.loads(row['result']) if row['result'] else None}

def add_feedback(run_id, satisfactory, reason):
    with conn() as c: c.execute("INSERT INTO feedback(run_id,satisfactory,reason,created_at) VALUES(?,?,?,?)",(run_id,int(satisfactory),reason,datetime.now(timezone.utc).isoformat()))

def feedback_summary():
    with conn() as c: return dict(c.execute("SELECT COUNT(*) total, COALESCE(AVG(satisfactory),0) satisfaction_rate FROM feedback").fetchone())

def quarantine_record(qid, body, errors):
    with conn() as c: c.execute("INSERT INTO quarantine VALUES(?,?,?,?)",(qid,json.dumps(body,default=str),json.dumps(errors,default=str),datetime.now(timezone.utc).isoformat()))
