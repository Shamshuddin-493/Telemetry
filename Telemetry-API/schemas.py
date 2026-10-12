from pydantic import BaseModel,Field
from datetime import datetime
from typing import Any,Optional

# --- Client Schemas ---
class ClientBase(BaseModel):
    name: str = Field(..., description="Name of the application or service")

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: int
    api_key: str
    created_at: datetime

    
class EventBase(BaseModel):
    user_id: str= Field(..., description='Unique identifier for the user or system') # '...' mean ellipsis which ensures the field is required and has no default value.
    event_type: str= Field(..., description="E.g., 'page_view', 'checkout_error'")
    event_metadata: dict[str, Any] = Field(default_factory=dict, description="Flexible payload data")

class EventCreate(EventBase):
    timestamp: Optional[datetime]= None

class EventResponse(EventBase):
    id:int
    client_id:int
    timestamp: datetime

    model_config={  # actually not needed but might be useful. if in absence event_dto = EventResponse.model_validate(db_event) ran anywhere will raise pydantic_core._pydantic_core.ValidationError: Input should be a valid dictionary or instance of EventResponse.
        "from_attributes":True
    }

class EventAcceptedResponse(BaseModel):
    status: str = "queued"
    message: str = "Event accepted for background processing"

class EventBatchCreate(BaseModel):
    events: list[EventCreate] = Field(..., min_length=1, max_length=500, description="List of events (max 500 per batch)")

class EventBatchResponse(BaseModel):
    ingested_count: int
    client_id: int
class PaginatedEventsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventResponse]

class EventTypeSummary(BaseModel):
    event_type: str
    count: int

class AnalyticsSummary(BaseModel):
    total_events: int
    unique_users: int
    breakdown: list[EventTypeSummary]