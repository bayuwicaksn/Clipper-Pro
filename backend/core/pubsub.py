"""Small Pub/Sub publisher helpers for backend API routes."""

import json
import time
from typing import Any

from .config import settings


def publish_json(topic_id: str, payload: dict[str, Any], timeout: int = 30) -> str:
    """Publish JSON to a Pub/Sub topic and wait for the message id."""
    if not settings.GCP_PROJECT_ID:
        raise RuntimeError("GCP_PROJECT_ID is not configured")

    from google.cloud import pubsub_v1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, topic_id)
    message = {**payload, "timestamp": payload.get("timestamp", time.time())}
    future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
    return future.result(timeout=timeout)


def publish_job(payload: dict[str, Any], timeout: int = 30) -> str:
    return publish_json(settings.PUBSUB_TOPIC_JOBS, payload, timeout=timeout)
