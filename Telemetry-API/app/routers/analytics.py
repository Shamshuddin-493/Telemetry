from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_client
from app.models import Client, TelemetryEvent
from app.schemas import AnalyticsSummary, EventTypeSummary

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# --- 6. For Client-side analytical summary ---
@router.get('/analytics/summary', response_model=AnalyticsSummary, status_code=200)
def get_analytics_summary(client:Client= Depends(get_current_client), db:Session= Depends(get_db)):
    total_events= db.query(func.count(TelemetryEvent.id)).filter(TelemetryEvent.client_id == client.id).scalar() or 0

    unique_users=db.query(func.count(func.distinct(TelemetryEvent.user_id))).filter(TelemetryEvent.client_id == client.id).scalar() or 0

    breakdown_query=db.query(TelemetryEvent.event_type,func.count(TelemetryEvent.id).label("event_count")).filter(TelemetryEvent.client_id == client.id).group_by(TelemetryEvent.event_type).all()

    breakdown=[EventTypeSummary(event_type=row.event_type, count=row.event_count) for row in breakdown_query]

    return AnalyticsSummary(
        total_events=total_events,
        unique_users=unique_users,
        breakdown=breakdown
        )