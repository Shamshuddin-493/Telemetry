from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Client

API_KEY_HEADER = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def get_current_client(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db)
) -> Client:
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key missing in 'X-API-KEY' header",
        )
    stmt = select(Client).where(Client.api_key == api_key)
    result= await db.execute(stmt)
    client= result.scalar_one_or_none()
    if not client:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key",
        )
    return client