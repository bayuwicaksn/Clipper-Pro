"""
Worker GPU — Entry Point
Clipper-Pro Video Processing Worker

Consume jobs dari Pub/Sub dan proses:
1. Download video (yt-dlp)
2. Transcribe audio (Whisper)
3. Analyze highlights (Gemini/OpenAI)
4. Extract clips (ffmpeg)
5. Push caption job ke Pub/Sub worker_node
"""

import os
import sys
import json
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_gpu")


def process_job(job_data: dict) -> None:
    """
    Proses satu job dari Pub/Sub.
    
    Ini adalah placeholder — implementasi penuh di Phase 3.
    """
    job_id = job_data.get("job_id", "unknown")
    logger.info(f"[Job {job_id}] Starting processing...")

    try:
        # Phase 3 akan implement:
        # 1. from worker_gpu.tasks.download import download_video
        # 2. from worker_gpu.tasks.transcribe import transcribe_audio
        # 3. from worker_gpu.tasks.analyze import analyze_highlights
        # 4. from worker_gpu.tasks.clip import extract_clips
        # 5. Push ke caption Pub/Sub topic

        logger.info(f"[Job {job_id}] Placeholder — full implementation in Phase 3")

    except Exception as e:
        logger.error(f"[Job {job_id}] Failed: {e}", exc_info=True)
        raise


def pull_messages():
    """
    Pull messages dari Google Cloud Pub/Sub.
    Placeholder — implementasi penuh di Phase 3.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_JOBS", "clipper-jobs-sub")

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — running in demo mode")
        logger.info("Worker GPU ready, waiting for jobs...")

        # Demo loop
        while True:
            logger.info("Polling for jobs... (demo mode)")
            time.sleep(30)
        return

    try:
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)

        logger.info(f"Listening on {subscription_path}")

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                logger.info(f"Received job: {data.get('job_id')}")
                process_job(data)
                message.ack()
                logger.info(f"Job {data.get('job_id')} acknowledged")
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                message.nack()

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

        with subscriber:
            try:
                streaming_pull_future.result()
            except Exception as e:
                streaming_pull_future.cancel()
                raise

    except ImportError:
        logger.error("google-cloud-pubsub not installed")
        raise


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received, exiting gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Clipper-Pro GPU Worker Starting")
    logger.info(f"Whisper Model: {os.getenv('WHISPER_MODEL', 'medium')}")
    logger.info(f"GPU Enabled: {os.getenv('GPU_ENABLED', 'false')}")
    logger.info("=" * 50)

    # Handle graceful shutdown
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Start pulling
    pull_messages()
