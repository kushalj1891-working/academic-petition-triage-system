from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

PetitionType = Literal["attendance", "re_evaluation", "re_registration", "medical_leave", "grade_grievance", "other"]

class Petition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    petition_id: str = Field(min_length=1, max_length=64)
    petition_type: PetitionType
    text: str = Field(min_length=10, max_length=4000)
    attendance_percent: float | None = Field(default=None, ge=0, le=100)
    medical_documented: bool | None = None
    semester: str | None = Field(default=None, max_length=32)

class RunAccepted(BaseModel):
    run_id: str
    status: str

class Citation(BaseModel):
    document_id: str
    clause_id: str
    title: str
    text: str
    source_url: str

class TriageResult(BaseModel):
    run_id: str
    status: Literal["completed", "needs_human", "rejected", "failed"]
    category: str
    route: str
    rationale: str
    citations: list[Citation]
    escalation_reason: str | None = None
    prompt_version: str
    metrics: dict = {}
    created_at: datetime | None = None
