from dotenv import load_dotenv
# Load environment variables FIRST before any shared imports
load_dotenv()

import os
import sys
import json
import logging
import signal
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Fix path so it can find 'src' and 'shared'
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import from local src
from src.caption.generator import (
    generate_caption_composition, 
    render_composition, 
    composite_transparent_captions
)
from shared.db import crud
from shared.db.database import engine
from sqlmodel import Session

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker_node")

# Supabase initialization removed - using shared SQLModel engine

# Global event for Graceful Shutdown
shutdown_event = threading.Event()

# ── Database Update Helper ─────────────────────────────────────────────
def update_job_db(job_id: str, data: dict):
    """Update job status/data using shared CRUD logic."""
    try:
        with Session(engine) as session:
            crud.update_job(session, job_id, data)
            return True
    except Exception as e:
        logger.error(f"[{job_id}] Database update failed: {e}")
        return False

# ── Health Check HTTP Server ──────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        status = "ok" if not shutdown_event.is_set() else "shutting_down"
        self.wfile.write(json.dumps({"status": status, "worker": "node"}).encode())

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server listening on port {port}")
    while not shutdown_event.is_set():
        server.handle_request()


# ── Rendering Logic ───────────────────────────────────────────────────
def process_caption_job(job_data: dict) -> None:
    """
    Render captions and composite them for all clips in a job.
    """
    job_id = job_data.get("job_id")
    
    from shared.utils.logging_utils import set_correlation_id
    set_correlation_id(job_id)

    job_dir = job_data.get("job_dir")
    clips = job_data.get("clips", [])
    config = job_data.get("config", {})

    logger.info(f"[{job_id}] Received caption job. Checking status...")
    
    # ── Check if this job should even run ──
    try:
        from shared.db.database import engine
        from shared.db import crud
        from sqlmodel import Session
        with Session(engine) as session:
            existing_job = crud.get_job(session, job_id)
            if existing_job:
                if existing_job.status in ["completed", "error"]:
                    logger.info(f"[{job_id}] Skipping captioning: job is already '{existing_job.status}'.")
                    return
                if existing_job.status == "rendering_captions":
                    from datetime import datetime, timedelta, timezone
                    if existing_job.updated_at and existing_job.updated_at > datetime.now(timezone.utc) - timedelta(minutes=5):
                        logger.warning(f"[{job_id}] Skipping: caption render is already being processed (updated recently).")
                        return
                    logger.info(f"[{job_id}] Job is 'rendering_captions' but stale. Re-taking ownership.")
    except Exception as e:
        logger.warning(f"[{job_id}] Could not verify job status in DB: {e}")

    logger.info(f"[{job_id}] Starting caption job for {len(clips)} clips.")
    crud.update_job_status(session, job_id, "rendering_captions", "Rendering captions...")
    
    final_clips_metadata = []

    for i, clip in enumerate(clips):
        if shutdown_event.is_set():
            logger.warning(f"[{job_id}] Shutdown requested, skipping remaining clips.")
            break

        try:
            clip_index = clip.get("clip_index", i)
            msg = f"Rendering captions for Clip {clip_index+1}/{len(clips)}"
            logger.info(f"[{job_id}] {msg}")
            update_job_db(job_id, {
                "status": "processing",
                "progress": int(((i) / len(clips)) * 100),
                "status_message": msg
            })
            
            clip_folder = os.path.join(job_dir, 'clips', f'clip_{clip_index + 1:02d}')
            exports_dir = os.path.join(clip_folder, 'exports')
            reframed_video = os.path.join(exports_dir, clip['filename'])
            
            # Delegation check: if the target video doesn't exist, check for the _reframed version from GPU worker
            if not os.path.exists(reframed_video):
                reframed_alt = os.path.join(exports_dir, clip['filename'].replace('.mp4', '_reframed.mp4'))
                if os.path.exists(reframed_alt):
                    logger.info(f"[{job_id}] Found delegated reframed video: {reframed_alt}")
                    reframed_video = reframed_alt
                else:
                    logger.error(f"[{job_id}] Reframed video not found: {reframed_video} or {reframed_alt}")
                    final_clips_metadata.append(clip)
                    continue

            # Prepare word-level transcript
            from shared.utils.helpers import timestamp_to_seconds
            transcript_words = clip.get('transcript', [])
            
            # Fallback: Try to load from source_transcript.json if missing
            if not transcript_words:
                transcript_path = os.path.join(job_dir, "source_transcript.json")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            transcript_words = data if isinstance(data, list) else data.get('words', [])
                        logger.info(f"[{job_id}] Loaded fallback transcript from source_transcript.json")
                    except Exception as e:
                        logger.warning(f"[{job_id}] Failed to load fallback transcript: {e}")

            clip_start = timestamp_to_seconds(clip.get('start_time', '00:00:00'))
            clip_end = timestamp_to_seconds(clip.get('end_time', '00:00:00'))
            
            custom_words = []
            for w in transcript_words:
                w_start = w.get('start', 0)
                w_end = w.get('end', 0)
                if w_start >= clip_start and w_end <= clip_end:
                    local_start = w_start - clip_start
                    local_end = w_end - clip_start
                    custom_words.append({
                        'word': w.get('word', w.get('text', '')),
                        'start': max(0, local_start),
                        'end': max(0, local_end)
                    })

            if not custom_words:
                logger.warning(f"[{job_id}] No words for clip {clip_index}, skipping captions.")
                final_clips_metadata.append(clip)
                continue

            # Render
            caption_settings = config.get('caption_settings', {})
            temp_dir = os.path.join(clip_folder, 'temp_render')
            os.makedirs(temp_dir, exist_ok=True)
            
            composition_html = os.path.join(temp_dir, 'index.html')
            generate_caption_composition(
                video_src=reframed_video,
                output_html=composition_html,
                words=custom_words,
                settings=caption_settings,
                video_w=1080,
                video_h=1920,
            )

            overlay_mov = os.path.join(temp_dir, 'overlay.mov')
            render_composition(composition_html, overlay_mov)

            final_filename = f"{clip['filename'].replace('.mp4', '')}_final.mp4"
            final_output = os.path.join(exports_dir, final_filename)
            composite_transparent_captions(reframed_video, overlay_mov, final_output)

            # Update metadata to point to the captioned video
            updated_clip = clip.copy()
            updated_clip['filename'] = final_filename
            final_clips_metadata.append(updated_clip)

            logger.info(f"[{job_id}] Clip {clip_index} render complete.")

            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"[{job_id}] Failed rendering clip {i}: {e}", exc_info=True)
            final_clips_metadata.append(clip)

    # 7. Update Database to Completed
    if not shutdown_event.is_set():
        update_job_db(job_id, {
            "status": "completed",
            "progress": 100,
            "status_message": "All captions rendered",
            "clips": final_clips_metadata
        })
        logger.info(f"[{job_id}] Worker Node finished and updated DB to 'completed'.")


# ── Pub/Sub Listener ──────────────────────────────────────────────────
def pull_messages():
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_CAPTION") or "clipper-caption-jobs-sub"

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — idle mode")
        while not shutdown_event.is_set():
            time.sleep(10)
        return

    from google.cloud import pubsub_v1
    retry_delay = 10

    while not shutdown_event.is_set():
        try:
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(project_id, subscription_id)
            logger.info(f"Connecting to Pub/Sub: {subscription_path}")

            def callback(message):
                try:
                    # Always acknowledge IMMEDIATELY to prevent infinite retry loops on startup
                    message.ack()
                    
                    data = json.loads(message.data.decode("utf-8"))
                    process_caption_job(data)
                except Exception as e:
                    logger.error(f"Error processing caption job: {e}")

            streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
            logger.info(f"Listening for messages on {subscription_id}...")
            
            with subscriber:
                while not shutdown_event.is_set() and not streaming_pull_future.done():
                    time.sleep(1)
                
                if shutdown_event.is_set():
                    logger.info("Cancelling caption subscription...")
                    streaming_pull_future.cancel()
                    streaming_pull_future.result()

        except Exception as e:
            if not shutdown_event.is_set():
                logger.error(f"Pub/Sub Listener Error: {e}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received! Graceful exit initiated...")
    shutdown_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Setup Structured Logging
    from shared.utils.logging_utils import setup_structured_logging
    setup_structured_logging()

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    logger.info("Node Worker starting listeners...")
    pull_messages()
    logger.info("Worker Node process exited cleanly.")
