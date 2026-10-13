from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.dependencies import get_current_client
from app.models import Client, TelemetryEvent
from app.schemas import (
    EventCreate,
    EventResponse,
    EventAcceptedResponse,
    EventBatchCreate,
    EventBatchResponse,
    PaginatedEventsResponse,
)

router = APIRouter(prefix="/events", tags=["Events"])

# --- Background Worker Function ---
def write_event_to_db(client_id: int, event_data: EventCreate):
    db: Session = SessionLocal()
    try:
        db_event = TelemetryEvent(
            client_id=client_id,
            user_id=event_data.user_id,
            event_type=event_data.event_type,
            event_metadata=event_data.event_metadata,
        )
        if event_data.timestamp:
            db_event.timestamp = event_data.timestamp
        db.add(db_event)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error persisting background event: {e}")
    finally:
        db.close()

# --- 1. Decoupled Ingestion Route (202 Accepted) ---
@router.post(
    "/events",
    response_model=EventAcceptedResponse,
    status_code=202
)
def track_event(
    event: EventCreate,
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_current_client)
):
    # Delegate the database I/O to background tasks
    background_tasks.add_task(write_event_to_db, client.id, event)
    return EventAcceptedResponse()

# --- 2. Filtered & Paginated Events Retrieval ---
@router.get("/events", response_model=PaginatedEventsResponse, status_code=200)
def get_events(
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    user_id: Optional[str] = Query(None, description="Filter by user identifier"),
    start_time: Optional[datetime] = Query(None, description="Filter events after this ISO datetime"),
    end_time: Optional[datetime] = Query(None, description="Filter events before this ISO datetime"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    query = db.query(TelemetryEvent).filter(TelemetryEvent.client_id == client.id)

    # Dynamic query filters
    if event_type:
        query = query.filter(TelemetryEvent.event_type == event_type)
    if user_id:
        query = query.filter(TelemetryEvent.user_id == user_id)
    if start_time:
        query = query.filter(TelemetryEvent.timestamp >= start_time)
    if end_time:
        query = query.filter(TelemetryEvent.timestamp <= end_time)

    total_count = query.count()
    db_items = query.order_by(TelemetryEvent.timestamp.desc()).offset(offset).limit(limit).all()

    items= [EventResponse.model_validate(event) for event in db_items]

    return PaginatedEventsResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        items=items
    )

# --- 3. Batch Ingestion Route ---
@router.post("/events/batch", response_model=EventBatchResponse, status_code=201)
def track_events_batch(
    batch: EventBatchCreate,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    db_events = []
    for event in batch.events:
        item = TelemetryEvent(
            client_id=client.id,
            user_id=event.user_id,
            event_type=event.event_type,
            event_metadata=event.event_metadata
        )
        if event.timestamp:
            item.timestamp = event.timestamp
        db_events.append(item)

    # Bulk insert in a single transaction
    db.add_all(db_events)
    db.commit()

    return EventBatchResponse(
        ingested_count=len(db_events),
        client_id=client.id
    )