import os
import sys
import json
import logging
import signal
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        pass  # suppress access logs


def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server listening on port {port}")
    server.serve_forever()


# ── Pub/Sub Worker ────────────────────────────────────────────────────
def process_caption_job(job_data: dict) -> None:
    job_id = job_data.get("job_id", "unknown")
    logger.info(f"[Job {job_id}] Starting caption rendering...")
    # Phase 3 implementation here


def pull_messages():
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_CAPTION", "clipper-caption-jobs-sub")

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — idle mode")
        while True:
            time.sleep(60)
        return

    try:
        from google.cloud import pubsub_v1
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)
        logger.info(f"Listening on {subscription_path}")

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                process_caption_job(data)
                message.ack()
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                message.nack()

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        with subscriber:
            streaming_pull_future.result()

    except ImportError:
        logger.error("google-cloud-pubsub not installed")
        while True:
            time.sleep(60)


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received")
    sys.exit(0)


if __name__ == "__main__":
    logger.info("Clipper-Pro Node Worker Starting")

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Jalankan health server di background thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # Jalankan Pub/Sub consumer di main thread
    pull_messages()
