"""
Shared Pydantic models — digunakan oleh backend, worker_gpu, dan worker_node.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    CLIPPING = "clipping"
    CAPTIONING = "captioning"
    UPLOADING = "uploading"
    DONE = "done"
    FAILED = "failed"


class HighlightSegment(BaseModel):
    start_time: str          # HH:MM:SS.mmm
    end_time: str            # HH:MM:SS.mmm
    title: str
    hook_text: str
    hook_score: int          # 0-100
    description: str
    tags: List[str]
    duration_seconds: Optional[float] = None


class JobPayload(BaseModel):
    """Payload yang dikirim ke Pub/Sub."""
    job_id: str
    video_url: str
    user_id: str
    settings: dict           # Caption settings dari editor
    config: dict             # AI config (model, min/max duration, dll)


class CaptionJobPayload(BaseModel):
    """Payload dari worker_gpu ke worker_node."""
    job_id: str
    clip_path: str           # GCS path ke video clip
    segment: HighlightSegment
    words: List[dict]        # Word timestamps dari Whisper
    settings: dict           # Caption settings
    output_path: str         # GCS path output final
