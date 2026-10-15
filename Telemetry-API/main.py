from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from app.routers import clients, events, analytics
from pathlib import Path

app= FastAPI(
    title="Telemetry Gateway API", description="High-throughput multi-tenant telemetry ingestion gateway"
)

app.state.limiter= limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore[arg-type]

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