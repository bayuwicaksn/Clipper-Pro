"""Shared Pub/Sub helpers used by workers and backend adapters."""

import json
import time
import logging
from typing import Callable, Optional, Any
from google.cloud import pubsub_v1
from google.api_core import exceptions

logger = logging.getLogger("shared.pubsub")

def decode_message_data(message) -> dict:
    return json.loads(message.data.decode("utf-8"))


def make_json_callback(handler: Callable[[dict], None], logger):
    def callback(message):
        try:
            handler(decode_message_data(message))
            message.ack()
        except Exception as exc:
            logger.error(f"Error processing Pub/Sub message: {exc}", exc_info=True)
            message.nack()

    return callback


class Publisher:
    """
    Robust Pub/Sub Publisher with retries and consistent logging.
    """
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client: Optional[pubsub_v1.PublisherClient] = None

    @property
    def client(self) -> pubsub_v1.PublisherClient:
        if self._client is None:
            self._client = pubsub_v1.PublisherClient()
        return self._client

    def publish(
        self, 
        topic_id: str, 
        data: Any, 
        retries: int = 3, 
        initial_backoff: float = 1.0
    ) -> bool:
        """
        Publish data to a topic with exponential backoff.
        `data` should be a dict (will be JSON encoded) or bytes.
        """
        if not self.project_id:
            logger.warning(f"GCP_PROJECT_ID not set. Skipping publish to {topic_id}")
            return False

        topic_path = self.client.topic_path(self.project_id, topic_id)
        
        if isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
        else:
            body = data

        attempt = 0
        while attempt <= retries:
            try:
                future = self.client.publish(topic_path, body)
                message_id = future.result(timeout=10)
                logger.info(f"Published message {message_id} to {topic_id}")
                return True
            except (exceptions.ServiceUnavailable, exceptions.DeadlineExceeded, exceptions.InternalServerError) as e:
                attempt += 1
                if attempt > retries:
                    logger.error(f"Failed to publish to {topic_id} after {retries} retries: {e}")
                    return False
                
                wait_time = initial_backoff * (2 ** (attempt - 1))
                logger.warning(f"Pub/Sub publish failed (attempt {attempt}/{retries+1}). Retrying in {wait_time}s... Error: {e}")
                time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Permanent failure publishing to {topic_id}: {e}")
                return False
        
        return False
