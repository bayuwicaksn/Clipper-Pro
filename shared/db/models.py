from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = Field(default=None)
    config: Optional[str] = Field(default=None)  # Stored as JSON string
    clips: Optional[str] = Field(default="[]")   # Stored as JSON string
