from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid

class SuggestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

class Suggestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str
    action: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: SuggestionStatus = SuggestionStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
