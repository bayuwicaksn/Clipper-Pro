import os
import sys
import json
import logging
import signal
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import caption generator from src
from src.caption.generator import (
    generate_caption_composition, 
    render_composition, 
    composite_transparent_captions
)

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker_node")


# ── Health Check HTTP Server ──────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","worker":"node"}')

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server listening on port {port}")
    server.serve_forever()


# ── Rendering Logic ───────────────────────────────────────────────────
def process_caption_job(job_data: dict) -> None:
    """
    Render captions and composite them for all clips in a job.
    """
    job_id = job_data.get("job_id")
    job_dir = job_data.get("job_dir")
    clips = job_data.get("clips", [])
    config = job_data.get("config", {})

    logger.info(f"[{job_id}] Received caption job for {len(clips)} clips.")

    for i, clip in enumerate(clips):
        try:
            clip_index = clip.get("clip_index", i)
            logger.info(f"[{job_id}] Rendering captions for Clip {clip_index}")
            
            # 1. Determine paths
            # In Docker, we assume the shared workspace is mounted at the same path or we use relative
            # For Cloud Run, we might need to download from GCS first, but if we use local disk for now:
            
            # Find the reframed video produced by worker_gpu
            # Usually it's in clips/clip_XX/exports/clip_XX_vXXXX.mp4
            # We need to find it based on clip['filename']
            clip_folder = os.path.join(job_dir, 'clips', f'clip_{clip_index + 1:02d}')
            exports_dir = os.path.join(clip_folder, 'exports')
            
            reframed_video = os.path.join(exports_dir, clip['filename'])
            
            if not os.path.exists(reframed_video):
                logger.error(f"[{job_id}] Reframed video not found: {reframed_video}")
                continue

            # 2. Prepare Caption Data
            # Prepare word-level transcript mapped to clip-local time
            from shared.utils.helpers import timestamp_to_seconds
            
            transcript_words = clip.get('transcript', [])
            clip_start = timestamp_to_seconds(clip.get('start_time', '00:00:00'))
            
            custom_words = []
            for w in transcript_words:
                local_start = w.get('start', 0) - clip_start
                local_end = w.get('end', 0) - clip_start
                if local_end > 0:
                    custom_words.append({
                        'word': w.get('word', w.get('text', '')),
                        'start': max(0, local_start),
                        'end': max(0, local_end)
                    })

            if not custom_words:
                logger.warning(f"[{job_id}] No words for clip {clip_index}, skipping captions.")
                continue

            # 3. Generate HTML Composition
            caption_settings = config.get('caption_settings', {})
            temp_dir = os.path.join(clip_folder, 'temp_render')
            os.makedirs(temp_dir, exist_ok=True)
            
            composition_html = os.path.join(temp_dir, 'index.html')
            
            generate_caption_composition(
                video_src=reframed_video,
                output_html=composition_html,
                words=custom_words,
                settings=caption_settings,
                video_w=1080, # Assuming 9:16
                video_h=1920,
            )

            # 4. Render to Transparent MOV
            overlay_mov = os.path.join(temp_dir, 'overlay.mov')
            render_composition(composition_html, overlay_mov)

            # 5. Composite with FFmpeg
            final_output = os.path.join(exports_dir, f"{clip['filename'].replace('.mp4', '')}_final.mp4")
            composite_transparent_captions(reframed_video, overlay_mov, final_output)

            logger.info(f"[{job_id}] Clip {clip_index} render complete: {final_output}")

            # 6. Cleanup temp
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"[{job_id}] Failed rendering clip {i}: {e}", exc_info=True)


# ── Pub/Sub Listener ──────────────────────────────────────────────────
def pull_messages():
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_CAPTION") or "clipper-caption-jobs-sub"

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — idle mode")
        while True:
            time.sleep(60)

    from google.cloud import pubsub_v1
    retry_delay = 10

    while True:
        try:
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(project_id, subscription_id)
            logger.info(f"Connecting to Pub/Sub: {subscription_path}")

            def callback(message):
                try:
                    data = json.loads(message.data.decode("utf-8"))
                    process_caption_job(data)
                    message.ack()
                except Exception as e:
                    logger.error(f"Error processing caption job: {e}", exc_info=True)
                    message.nack()

            streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
            
            logger.info(f"Listening for messages on {subscription_id}...")
            with subscriber:
                try:
                    streaming_pull_future.result()
                except Exception as e:
                    if "NotFound" in str(e) or "404" in str(e):
                        logger.error(f"CRITICAL: Subscription '{subscription_id}' not found in project '{project_id}'. "
                                     "Please ensure it exists in GCP Console or check your GCP_PROJECT_ID env.")
                    streaming_pull_future.cancel()
                    raise e
        except Exception as e:
            logger.error(f"Pub/Sub Listener Error: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    pull_messages()
