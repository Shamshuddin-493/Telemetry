from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from app.routers import clients, events, analytics

app= FastAPI(
    title="Telemetry Gateway API", description="High-throughput multi-tenant telemetry ingestion gateway"
)

app.state.limiter= limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore[arg-type]

app.include_router(clients.router)
app.include_router(events.router)
app.include_router(analytics.router)
