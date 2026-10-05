from pydantic import BaseModel,Field
from datetime import datetime
from typing import Dict,Any,Optional

class EventBase(BaseModel):
    user_id: str= Field(..., description='Unique identifier for the user or system') # '...' mean ellipsis which ensures the field is required and has no default value.
    event_type: str= Field(..., description="E.g., 'page_view', 'checkout_error'")
    event_metadata: Dict[str, Any] = Field(default_factory=dict, description="Flexible payload data")

class EventCreate(EventBase):
    timestamp: Optional[datetime]= None

class EventResponse(EventBase):
    id:int
    timestamp: datetime

    model_config={
        "from_attributes":True
    }