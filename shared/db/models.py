from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str
    progress: int = Field(default=0)
    status_message: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    config: Optional[str] = Field(default=None)  # Stored as JSON string
    clips: Optional[str] = Field(default="[]")   # Stored as JSON string

    @property
    def error(self) -> Optional[str]:
        """Backward compatibility alias for error_message."""
        return self.error_message

    @error.setter
    def error(self, value: Optional[str]):
        """Backward compatibility setter for error_message."""
        self.error_message = value
