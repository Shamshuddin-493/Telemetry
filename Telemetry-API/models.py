from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer,String,DateTime,JSON
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class TelmetryEvent(Base):      
    __tablename__="""telemetry_event"""
    
    id:Mapped[int] = mapped_column(Integer,primary_key=True,index=True)
    user_id: Mapped[int]= mapped_column(Integer,index=True)
    event_type: Mapped[str]= mapped_column(String(50))
    timestamp: Mapped[datetime]= mapped_column(DateTime,default=lambda:datetime.now(timezone.utc),index=True)
    event_metadata: Mapped[datetime]= mapped_column(JSON, default=dict)