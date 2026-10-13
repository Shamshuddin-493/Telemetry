from fastapi import FastAPI
from app import models
from app.database import engine
from app.routers import clients, events, analytics

models.Base.metadata.create_all(bind=engine)

app=FastAPI(title="Telemetry Gateway API", description="High-throughput multi-tenant telemetry ingestion gateway")

app.include_router(clients.router)
app.include_router(events.router)
app.include_router(analytics.router)
