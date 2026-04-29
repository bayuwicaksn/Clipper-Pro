"""
Worker Node — Entry Point
Clipper-Pro Caption Rendering Worker

Consume caption jobs dari Pub/Sub dan:
1. Generate HTML composition (HyperFrames + GSAP)
2. Render transparent MOV via headless Chromium
3. Composite caption overlay ke video
4. Upload hasil ke Cloud Storage
5. Update status di Supabase
"""

import os
import sys
import json
import logging
import signal
import time

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_node")


def process_caption_job(job_data: dict) -> None:
    """
    Proses satu caption job.
    Placeholder — implementasi penuh di Phase 3.
    """
    job_id = job_data.get("job_id", "unknown")
    logger.info(f"[Job {job_id}] Starting caption rendering...")

    try:
        # Phase 3 akan implement:
        # from worker_node.src.caption.generator import generate_caption_composition
        # from worker_node.src.caption.generator import render_composition
        # from worker_node.src.caption.generator import composite_transparent_captions

        logger.info(f"[Job {job_id}] Placeholder — full implementation in Phase 3")

    except Exception as e:
        logger.error(f"[Job {job_id}] Failed: {e}", exc_info=True)
        raise


def pull_messages():
    """Pull messages dari Pub/Sub caption topic."""
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_CAPTION", "clipper-caption-jobs-sub")

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — running in demo mode")
        logger.info("Worker Node ready, waiting for caption jobs...")

        while True:
            logger.info("Polling for caption jobs... (demo mode)")
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
                logger.info(f"Received caption job: {data.get('job_id')}")
                process_caption_job(data)
                message.ack()
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
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
    logger.info("Clipper-Pro Node Worker Starting")

    # Verify Chromium tersedia
    chromium_path = os.getenv("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium")
    if os.path.exists(chromium_path):
        logger.info(f"Chromium found: {chromium_path}")
    else:
        logger.warning(f"Chromium not found at {chromium_path}")

    # Verify Node.js tersedia
    import subprocess
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        logger.info(f"Node.js: {result.stdout.strip()}")
    except Exception:
        logger.warning("Node.js not found in PATH")

    logger.info("=" * 50)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    pull_messages()
