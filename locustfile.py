from locust import HttpUser, task, between
import uuid, time

class PetitionUser(HttpUser):
    wait_time=between(0.2,1.0)
    @task
    def submit_and_poll(self):
        body={"petition_id":"LOAD-"+uuid.uuid4().hex[:8],"petition_type":"attendance","text":"Synthetic serious illness attendance shortfall; please review the regulation and medical condonation clause.","attendance_percent":62,"medical_documented":True,"semester":"I"}
        response=self.client.post("/v1/runs",json=body)
        if response.status_code!=202: return
        url=response.json()["status_url"]
        for _ in range(30):
            r=self.client.get(url)
            if r.status_code==200 and r.json().get("status") in ("needs_human","completed","failed"): break
            time.sleep(0.25)
