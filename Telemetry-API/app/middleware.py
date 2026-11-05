import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.audit import dispatch_audit

EXCLUDED_PATHS = {"/health", "/", "/favicon.ico"}

class AutoAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip static assets and internal ping routes
        if request.url.path in EXCLUDED_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Derive action from endpoint function name or HTTP method + path
        endpoint_func = request.scope.get("endpoint")
        if endpoint_func and hasattr(endpoint_func, "__name__"):
            action = endpoint_func.__name__.upper()
        else:
            action = f"{request.method}_{request.url.path.strip('/').replace('/', '_').upper()}"

        status = "SUCCESS" if response.status_code < 400 else ("WARNING" if response.status_code < 500 else "FAILURE")
        client_id = getattr(request.state, "client_id", None)

        dispatch_audit(
            action=action,
            status=status,
            client_id=client_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response