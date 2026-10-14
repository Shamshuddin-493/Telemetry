import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.limiter import limiter
from app.models import Client
from app.schemas import ClientCreate, ClientResponse

router = APIRouter(prefix="/clients", tags=["Clients"])

# ---1. Client Onboarding Route ---
@router.post('',response_model=ClientResponse, status_code=201)
@limiter.limit("60/minute")
async def register_client(
    request: Request,
    client_data: ClientCreate, 
    db: AsyncSession= Depends(get_db)):
    stmt= select(Client).where(Client.name ==client_data.name)
    result= await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Client with this name already exists"
        )

    # Generating a crytographically secure random API KEY
    generated_key=f'tel_{secrets.token_urlsafe(32)}'

    client=Client(
        name=client_data.name, api_key=generated_key
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client

# ---2. Clients Retrieval---
@router.get('', response_model=list[ClientResponse], status_code=200)
@limiter.limit("120/minute")
async def get_clients(
    request: Request,
    limit:int=10, 
    db:AsyncSession=Depends(get_db)):
    stmt=select(Client).order_by(Client.created_at.desc()).limit(limit)
    result= await db.execute(stmt)
    return result.scalars().all()