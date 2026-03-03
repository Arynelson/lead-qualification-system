from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone

from db.database import get_db
from models.lead import Lead
from models.ai_score import AIScore
from models.error import ErrorLog
from models.schemas import MetricsResponse

router = APIRouter()


async def get_metrics(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # Leads today
    result = await db.execute(
        select(func.count()).select_from(Lead).where(Lead.created_at >= today_start)
    )
    leads_today = result.scalar() or 0

    # Leads this week
    result = await db.execute(
        select(func.count()).select_from(Lead).where(Lead.created_at >= week_start)
    )
    leads_this_week = result.scalar() or 0

    # Tier counts from ai_scores
    result = await db.execute(
        select(AIScore.tier, func.count()).group_by(AIScore.tier)
    )
    tier_counts = {row[0]: row[1] for row in result.fetchall()}

    # Error count this week
    result = await db.execute(
        select(func.count()).select_from(ErrorLog).where(
            ErrorLog.created_at >= week_start
        )
    )
    error_count = result.scalar() or 0
    error_rate = round(error_count / leads_this_week, 4) if leads_this_week > 0 else 0.0

    return {
        "leads_today": leads_today,
        "leads_this_week": leads_this_week,
        "tier_a": tier_counts.get("A", 0),
        "tier_b": tier_counts.get("B", 0),
        "tier_c": tier_counts.get("C", 0),
        "avg_processing_time_seconds": 0.0,  # Requires event timestamp analysis
        "error_rate": error_rate,
    }


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(db: AsyncSession = Depends(get_db)):
    data = await get_metrics(db)
    return MetricsResponse(**data)
