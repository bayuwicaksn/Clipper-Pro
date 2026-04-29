"""Shared Pub/Sub helpers used by workers and backend adapters."""

import json
from typing import Callable


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
