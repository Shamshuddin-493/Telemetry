import secrets
from datetime import datetime
from typing import Optional
from fastapi import FastAPI,HTTPException, Depends, Security, BackgroundTasks, Query, status
from fastapi.security import APIKeyHeader
from sqlalchemy import func
from sqlalchemy.orm import Session
import models
from models import Client, TelemetryEvent
from schemas import (ClientCreate,ClientResponse,EventCreate, EventResponse, EventAcceptedResponse, EventBatchCreate, EventBatchResponse, PaginatedEventsResponse, EventTypeSummary, AnalyticsSummary)
from database import engine, SessionLocal, get_db

models.Base.metadata.create_all(bind=engine)

app=FastAPI(title="Telemetry Gateway API")

API_KEY_HEADER= APIKeyHeader(name="X-API-KEY", auto_error=False)

def get_current_client(api_key:str= Security(API_KEY_HEADER),db:Session= Depends(get_db)):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key missing in 'X-API-Key' header"
        )
    client=db.query(Client).filter(Client.api_key == api_key).first()
    if not client:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return client

# --- Background Worker Function ---
def write_event_to_db(client_id: int, event_data: EventCreate):
    """Executes outside the HTTP request lifecycle in a separate thread/session."""
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
        # In production, replace with structured logger
        print(f"Error persisting background telemetry event: {e}")
    finally:
        db.close()

# ---1. Client Onboarding Route ---
@app.post('/clients',response_model=ClientResponse, status_code=201)
def register_client(client_data: ClientCreate, db: Session= Depends(get_db)):
    existing_client=db.query(Client).filter(Client.name == client_data.name).first()
    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="Client with this name already exists"
        )

    # Generating a crytographically secure random API KEY
    generated_key=f'tel_{secrets.token_urlsafe(32)}'

    db_client=Client(
        name=client_data.name,
        api_key=generated_key
    )

    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

# ---2. Clients Retrieval---
@app.get('/clients', response_model=list[ClientResponse], status_code=200)
def get_clients(limit:int=10, db:Session=Depends(get_db)):
    clients=db.query(Client).order_by(Client.created_at.desc()).limit(limit).all()
    return clients


# --- 3. Decoupled Ingestion Route (202 Accepted) ---
@app.post(
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

# --- 4. Filtered & Paginated Events Retrieval ---
@app.get("/events", response_model=PaginatedEventsResponse, status_code=200)
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

# --- 5. Batch Ingestion Route ---
@app.post("/events/batch", response_model=EventBatchResponse, status_code=201)
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

# --- 6. For Client-side analytical summary ---
@app.get('/analytics/summary', response_model=AnalyticsSummary, status_code=200)
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