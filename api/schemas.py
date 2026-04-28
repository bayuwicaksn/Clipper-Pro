from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# ─── Request Schemas ─────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    url: str
    min_duration: int = 30
    max_duration: int = 90
    enable_hook: bool = True
    enable_captions: bool = True
    reframe_mode: str = 'opencv'
    tts_voice: str = 'alloy'
    caption_style: str = 'capcut'
    ai_provider: str = 'gpt-5.4-mini'
    transcription_provider: str = 'openai-whisper'

class ExportRequest(BaseModel):
    filename: Optional[str] = None
    clip_index: Optional[int] = None
    custom_start: Optional[str] = None
    custom_end: Optional[str] = None
    custom_crop_x: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
    caption_settings: Optional[Dict[str, Any]] = None
    transcript: Optional[List[Dict[str, Any]]] = None
    aspect_ratio: str = '9:16'
    auto_background_enabled: bool = True

class ReprocessRequest(BaseModel):
    url: str = ''
    num_clips: int = 5
    min_duration: int = 30
    max_duration: int = 90
    enable_hook: bool = True
    enable_captions: bool = True
    reframe_mode: str = 'opencv'
    tts_voice: str = 'alloy'
    caption_style: str = 'capcut'

class RegenerateRequest(BaseModel):
    filename: str

# ─── Response Schemas ────────────────────────────────────────────────────────

class ClipResponse(BaseModel):
    clip_index: int
    filename: str
    title: str
    start_time: str
    end_time: str
    duration_seconds: float
    # Allow extra fields for dynamic metadata
    model_config = {"extra": "allow"}

class JobResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    error: Optional[str] = None
    clips: List[Dict[str, Any]] = []
    config: Optional[Dict[str, Any]] = None

class ProjectResponse(BaseModel):
    id: str
    slug: str
    title: str
    status: str
    clip_count: int
    created_at: str
    video_duration: Optional[float] = 0
    video_url: Optional[str] = ''
    thumbnail: Optional[str] = ''
    created_timestamp: Optional[float] = 0
