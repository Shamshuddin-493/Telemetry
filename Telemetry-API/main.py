from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List
import models
from models import TelmetryEvent
from schemas import EventCreate, EventResponse
from database import engine,get_db

models.Base.metadata.create_all(bind=engine)

app=FastAPI(title="Telemetry Gateway API")

@app.post("/events", response_model=EventResponse, status_code=201)
def track_event(event:EventCreate, db:Session = Depends(get_db)):
    db_event=TelmetryEvent(
        user_id=event.user_id,
        event_type=event.event_type,
        event_metadata=event.event_metadata
    )

    if event.timestamp:
        db_event.timestamp=event.timestamp

    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.get("/events", response_model= List[EventResponse])
def get_recent_events(limit:int=10, db: Session= Depends(get_db)):
    events= db.query(TelmetryEvent).order_by(TelmetryEvent.timestamp.desc()).limit(limit).all()
    return events