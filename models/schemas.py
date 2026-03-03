from pydantic import BaseModel, EmailStr
from typing import Optional


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    company: str
    source: str
    message: Optional[str] = None


class LeadResponse(BaseModel):
    lead_id: str
    status: str = "received"


class LeadQueueRequest(BaseModel):
    tier: str
    score: int
    reasoning: str


class LeadLogRequest(BaseModel):
    tier: str
    score: int


class LeadEventRequest(BaseModel):
    event_type: str
    payload: Optional[dict] = None


class ErrorLogRequest(BaseModel):
    lead_id: Optional[str] = None
    source: str
    error_message: str
    payload: Optional[dict] = None


class MetricsResponse(BaseModel):
    leads_today: int
    leads_this_week: int
    tier_a: int
    tier_b: int
    tier_c: int
    avg_processing_time_seconds: float
    error_rate: float
