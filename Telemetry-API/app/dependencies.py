from fastapi import HTTPException, Security, Depends, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client

API_KEY_HEADER = APIKeyHeader(name="X-API-KEY", auto_error=False)

def get_current_client(
    api_key: str = Security(API_KEY_HEADER),
    db: Session = Depends(get_db)
) -> Client:
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key missing in 'X-API-KEY' header",
        )
    client = db.query(Client).filter(Client.api_key == api_key).first()
    if not client:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key",
        )
    return client