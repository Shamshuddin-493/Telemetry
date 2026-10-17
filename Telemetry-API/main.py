from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from app.audit import dispatch_audit
from app.middleware import AutoAuditMiddleware
from app.routers import clients, events, analytics

app= FastAPI(
    title="Telemetry Gateway API", description="High-throughput multi-tenant telemetry ingestion gateway"
)

app.state.limiter= limiter
# Part of the 10%: Rate limit breaches caught before endpoint execution
def rate_limit_custom_handler(request: Request, exc: Exception) -> Response:
    dispatch_audit(
        action="RATE_LIMIT_EXCEEDED",
        status="WARNING",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"path": request.url.path, "detail": str(exc)},
    )
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
app.add_exception_handler(RateLimitExceeded, rate_limit_custom_handler)
app.add_middleware(AutoAuditMiddleware)

app.include_router(clients.router)
app.include_router(events.router)
app.include_router(analytics.router)

# BASE_DIR points to the directory containing main.py (Telemetry-API)
BASE_DIR = Path(__file__).resolve().parent
# STATIC_DIR points to the parent directory's static folder
STATIC_DIR = BASE_DIR.parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    if not INDEX_FILE.exists():
        return JSONResponse(status_code=404, content={"detail": f"File not found at {INDEX_FILE}"})
    return FileResponse(INDEX_FILE)

@app.get('/health', tags=["Health"])
def health_check():
    return {'status': 'ok'}