import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from db.database import get_db
from models.lead import Lead
from models.lead_event import LeadEvent
from models.error import ErrorLog
from models.schemas import (
    LeadCreate, LeadResponse, LeadQueueRequest,
    LeadLogRequest, LeadEventRequest, ErrorLogRequest,
)
from services.n8n_trigger import trigger_n8n

router = APIRouter()


@router.post("/leads", status_code=202, response_model=LeadResponse)
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead_id = str(uuid.uuid4())
    lead = Lead(
        id=lead_id,
        name=payload.name,
        email=payload.email,
        company=payload.company,
        source=payload.source,
        message=payload.message,
        status="received",
        enrichment_status="pending",
    )
    db.add(lead)
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type="received",
        payload={"source": payload.source},
    ))
    await db.commit()

    await trigger_n8n({
        "lead_id": lead_id,
        "name": payload.name,
        "email": payload.email,
        "company": payload.company,
        "source": payload.source,
        "message": payload.message,
    })
    return LeadResponse(lead_id=lead_id)


@router.post("/leads/{lead_id}/queue", status_code=200)
async def queue_lead(
    lead_id: str,
    payload: LeadQueueRequest,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Lead).where(Lead.id == lead_id).values(status="queued")
    )
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type="queued",
        payload={"tier": payload.tier, "score": payload.score},
    ))
    await db.commit()
    return {"status": "queued"}


@router.post("/leads/{lead_id}/log", status_code=200)
async def log_lead(
    lead_id: str,
    payload: LeadLogRequest,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Lead).where(Lead.id == lead_id).values(status="logged")
    )
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type="disqualified",
        payload={"tier": payload.tier, "score": payload.score},
    ))
    await db.commit()
    return {"status": "logged"}


@router.post("/leads/{lead_id}/events", status_code=200)
async def log_event(
    lead_id: str,
    payload: LeadEventRequest,
    db: AsyncSession = Depends(get_db),
):
    db.add(LeadEvent(
        lead_id=lead_id,
        event_type=payload.event_type,
        payload=payload.payload,
    ))
    await db.commit()
    return {"status": "logged"}


@router.post("/errors", status_code=200)
async def log_error(
    payload: ErrorLogRequest,
    db: AsyncSession = Depends(get_db),
):
    db.add(ErrorLog(
        lead_id=payload.lead_id,
        source=payload.source,
        error_message=payload.error_message,
        payload=payload.payload,
    ))
    await db.commit()
    return {"status": "logged"}
