"""
ClipperApp — API Module (FastAPI)
Shared state and helpers used across all router modules.
"""

import os
import re
import queue
from datetime import datetime

from core.utils import (
    resolve_job_dir as _resolve_job_dir,
    get_clip_dir as _get_clip_dir,
    timestamp_to_seconds,
    seconds_to_timestamp,
    seconds_to_timestamp_simple,
    filter_words_by_range,
    get_source_transcript,
    app_logger as logger
)

# ─── Configuration ───────────────────────────────────────────────────────────
WORKSPACE = os.environ.get('CLIPPER_WORKSPACE', '/content/clipper_workspace')
os.makedirs(WORKSPACE, exist_ok=True)

# ─── Global Job State ────────────────────────────────────────────────────────
# Shared across all routers. In the future, replace with Redis/DB.
jobs = {}
progress_queues = {}
progress_states = {}  # Latest state for polling fallback


# ─── Shared Helpers ──────────────────────────────────────────────────────────
def slugify(title, max_len=50):
    """Convert a video title into a URL-safe slug."""
    s = title.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)       # remove non-alphanumeric
    s = re.sub(r'[\s-]+', '-', s).strip('-')   # collapse whitespace/hyphens
    return s[:max_len].rstrip('-')


def resolve_job_dir(job_id):
    return _resolve_job_dir(job_id, WORKSPACE)


def get_clip_dir(job_dir, clip_index):
    return _get_clip_dir(job_dir, clip_index)


def is_new_layout(job_dir):
    """Check if a project uses the new per-clip folder layout."""
    return os.path.isdir(os.path.join(job_dir, 'clips'))


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


def robust_rmtree(path):
    """Retry-capable recursive directory removal for Windows file locks."""
    import time
    import shutil
    import gc
    for i in range(5):
        try:
            gc.collect()
            shutil.rmtree(path)
            return
        except Exception as e:
            if i == 4:
                raise e
            time.sleep(1)
