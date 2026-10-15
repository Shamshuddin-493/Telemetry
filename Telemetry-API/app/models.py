from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column,relationship
from sqlalchemy import Integer,String,DateTime,JSON,ForeignKey, func
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class Client(Base):
    __tablename__="""clients"""

    id: Mapped[int]= mapped_column(primary_key=True, index=True)
    name: Mapped[str]= mapped_column(String(100), unique=True, index=True)
    api_key: Mapped[str]= mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), index=True)
    events: Mapped[list["TelemetryEvent"]]= relationship (back_populates="client", cascade="all, delete-orphan")

class TelemetryEvent(Base):      
    __tablename__="""telemetry_event"""
    
    id:Mapped[int] = mapped_column(Integer,primary_key=True, index=True)
    client_id: Mapped[int]= mapped_column(ForeignKey("clients.id"), index=True)
    user_id: Mapped[str]= mapped_column(String,index=True)
    event_type: Mapped[str]= mapped_column(String(50))
    event_metadata: Mapped[dict]= mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime]= mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),server_default=func.now(), index=True)
    client: Mapped["Client"]= relationship(back_populates="events")