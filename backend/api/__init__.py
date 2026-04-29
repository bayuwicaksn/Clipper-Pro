"""
ClipperApp â€” API Module (FastAPI)
Shared state and helpers used across all router modules.
"""

import os
import queue
from datetime import datetime

from shared.core.utils import get_source_transcript, app_logger as logger
from shared.utils.helpers import (
    resolve_job_dir as _resolve_job_dir,
    get_clip_dir as _get_clip_dir,
    timestamp_to_seconds,
    seconds_to_timestamp,
    seconds_to_timestamp_simple,
    filter_words_by_range,
    slugify,
    is_new_layout,
    robust_rmtree
)

from backend.core.config import settings

# â”€â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WORKSPACE = settings.CLIPPER_WORKSPACE
os.makedirs(WORKSPACE, exist_ok=True)

# â”€â”€â”€ Global Job State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Shared across all routers. Persistent data moved to SQLite.
progress_queues = {}
progress_states = {}  # Latest state for polling fallback


# â”€â”€â”€ Shared Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def resolve_job_dir(job_id):
    return _resolve_job_dir(job_id, WORKSPACE)


def get_clip_dir(job_dir, clip_index):
    return _get_clip_dir(job_dir, clip_index)




def create_progress_callback(job_id):
    """Create a callback function that pushes progress events to SSE queue."""
    if job_id not in progress_queues:
        progress_queues[job_id] = queue.Queue()

    def callback(step, message, progress=0, data=None):
        event = {
            'step': step,
            'message': message,
            'progress': progress,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        }
        progress_queues[job_id].put(event)
        progress_states[job_id] = event  # Store for polling

    return callback


