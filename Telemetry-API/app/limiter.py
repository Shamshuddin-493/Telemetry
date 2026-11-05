from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_api_key_or_ip(request: Request) -> str:
    """Extracts client API key from headers, falling back to client IP."""
    api_key = request.headers.get("X-API-KEY")
    if api_key:
        return api_key
    return get_remote_address(request)

# Default in-memory limiter (can be pointed to Redis later via storage_uri)
limiter = Limiter(key_func=get_api_key_or_ip)