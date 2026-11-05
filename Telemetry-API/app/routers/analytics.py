from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_client
from app.models import Client, TelemetryEvent
from app.schemas import AnalyticsSummary, EventTypeSummary

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# --- 6. For Client-side analytical summary ---
@router.get('/summary', response_model=AnalyticsSummary, status_code=200)
async def get_analytics_summary(client:Client= Depends(get_current_client), db:AsyncSession= Depends(get_db)):
    total_stmt = select(func.count(TelemetryEvent.id)).where(TelemetryEvent.client_id == client.id)
    total_events = (await db.execute(total_stmt)).scalar() or 0

    unique_stmt = select(func.count(func.distinct(TelemetryEvent.user_id))).where(TelemetryEvent.client_id == client.id)
    unique_users = (await db.execute(unique_stmt)).scalar() or 0

    breakdown_stmt = (
        select(TelemetryEvent.event_type, func.count(TelemetryEvent.id).label("event_count"))
        .where(TelemetryEvent.client_id == client.id)
        .group_by(TelemetryEvent.event_type)
    )
    breakdown_res = await db.execute(breakdown_stmt)
    breakdown = [EventTypeSummary(event_type=row.event_type, count=row.event_count) for row in breakdown_res.all()]

    return AnalyticsSummary(
        total_events=total_events,
        unique_users=unique_users,
        breakdown=breakdown,
    )