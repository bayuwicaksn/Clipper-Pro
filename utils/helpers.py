import os
import re
import shutil
import gc
import time

def timestamp_to_seconds(ts):
    """Convert HH:MM:SS to total seconds."""
    if not ts or not isinstance(ts, str):
        return 0
    parts = ts.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts)

def seconds_to_timestamp(seconds):
    """Convert seconds to HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def seconds_to_timestamp_simple(seconds):
    """Convert seconds to HH:MM:SS string (no decimals)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def slugify(title, max_len=50):
    """Convert a video title into a URL-safe slug."""
    s = title.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)       # remove non-alphanumeric
    s = re.sub(r'[\s-]+', '-', s).strip('-')   # collapse whitespace/hyphens
    return s[:max_len].rstrip('-')

def resolve_job_dir(job_id, workspace_root='workspace'):
    """Find the actual directory for a job_id.
    Supports direct match and slug--id pattern.
    """
    if not os.path.exists(workspace_root):
        return None
        
    direct = os.path.join(workspace_root, job_id)
    if os.path.isdir(direct):
        return direct

    # Search for slug--id pattern
    suffix = f'--{job_id}'
    for name in os.listdir(workspace_root):
        if name.endswith(suffix) and os.path.isdir(os.path.join(workspace_root, name)):
            return os.path.join(workspace_root, name)

    return None

def get_clip_dir(job_dir, clip_index):
    """Get path to a specific clip's directory."""
    idx = int(clip_index) + 1
    return os.path.join(job_dir, 'clips', f'clip_{idx:02d}')

def filter_words_by_range(words, start_sec, end_sec):
    """Filter word list to only include words within [start, end] range."""
    return [
        w for w in words 
        if w['start'] >= start_sec and w['start'] <= end_sec
    ]

def is_new_layout(job_dir):
    """Check if a project uses the new per-clip folder layout."""
    return os.path.isdir(os.path.join(job_dir, 'clips'))

def robust_rmtree(path):
    """Retry-capable recursive directory removal for Windows file locks."""
    for i in range(5):
        try:
            gc.collect()
            shutil.rmtree(path)
            return
        except Exception as e:
            if i == 4:
                raise e
            time.sleep(1)
