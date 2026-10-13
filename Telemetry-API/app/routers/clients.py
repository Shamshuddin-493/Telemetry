import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client
from app.schemas import ClientCreate, ClientResponse

router = APIRouter(prefix="/clients", tags=["Clients"])

# ---1. Client Onboarding Route ---
@router.post('/clients',response_model=ClientResponse, status_code=201)
def register_client(client_data: ClientCreate, db: Session= Depends(get_db)):
    existing_client=db.query(Client).filter(Client.name == client_data.name).first()
    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="Client with this name already exists"
        )

    # Generating a crytographically secure random API KEY
    generated_key=f'tel_{secrets.token_urlsafe(32)}'

    db_client=Client(
        name=client_data.name,
        api_key=generated_key
    )

    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

# ---2. Clients Retrieval---
@router.get('/clients', response_model=list[ClientResponse], status_code=200)
def get_clients(limit:int=10, db:Session=Depends(get_db)):
    clients=db.query(Client).order_by(Client.created_at.desc()).limit(limit).all()
    return clients