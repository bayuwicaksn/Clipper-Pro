from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str = Field(index=True)
    progress: int = Field(default=0)
    status_message: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    
    # Use native JSON/JSONB for better performance and scalability
    config: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    clips: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    @property
    def error(self) -> Optional[str]:
        """Backward compatibility alias for error_message."""
        return self.error_message

    @error.setter
    def error(self, value: Optional[str]):
        """Backward compatibility setter for error_message."""
        self.error_message = value
