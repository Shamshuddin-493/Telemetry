from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, get_db
from app.dependencies import get_current_client
from app.limiter import limiter
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
async def write_event_to_db(client_id: int, event_data: EventCreate):
    async with AsyncSessionLocal() as db:
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
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Error persisting background event: {e}")

# --- 1. Decoupled Ingestion Route (202 Accepted) ---
@router.post(
    "",
    response_model=EventAcceptedResponse,
    status_code=202
)
# @limiter.limit("120/minute")
async def track_event(
    request: Request,
    event: EventCreate,
    background_tasks: BackgroundTasks,
    client: Client = Depends(get_current_client)
):
    # Delegate the database I/O to background tasks
    background_tasks.add_task(write_event_to_db, client.id, event)
    return EventAcceptedResponse()


# --- 2. Batch Ingestion Route ---
@router.post("/batch", response_model=EventBatchResponse, status_code=201)
# @limiter.limit("30/minute")
async def track_events_batch(
    request: Request,
    batch: EventBatchCreate,
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
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
    await db.commit()

    return EventBatchResponse(
        ingested_count=len(db_events),
        client_id=client.id
    )

# --- 3. Filtered & Paginated Events Retrieval ---
@router.get("", response_model=PaginatedEventsResponse, status_code=200)
# @limiter.limit("10/minute")
async def get_events(
    request: Request,
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    user_id: Optional[str] = Query(None, description="Filter by user identifier"),
    start_time: Optional[datetime] = Query(None, description="Filter events after this ISO datetime"),
    end_time: Optional[datetime] = Query(None, description="Filter events before this ISO datetime"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TelemetryEvent).where(TelemetryEvent.client_id == client.id)
    count_stmt = select(func.count(TelemetryEvent.id)).where(TelemetryEvent.client_id == client.id)

    if event_type:
        stmt = stmt.where(TelemetryEvent.event_type == event_type)
        count_stmt = count_stmt.where(TelemetryEvent.event_type == event_type)
    if user_id:
        stmt = stmt.where(TelemetryEvent.user_id == user_id)
        count_stmt = count_stmt.where(TelemetryEvent.user_id == user_id)
    if start_time:
        stmt = stmt.where(TelemetryEvent.timestamp >= start_time)
        count_stmt = count_stmt.where(TelemetryEvent.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(TelemetryEvent.timestamp <= end_time)
        count_stmt = count_stmt.where(TelemetryEvent.timestamp <= end_time)

    # Execute count
    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar() or 0

    # Execute paginated query
    query = stmt.order_by(TelemetryEvent.timestamp.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    db_items = result.scalars().all()
    items = [EventResponse.model_validate(item) for item in db_items]

    return PaginatedEventsResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        items=items,
    )