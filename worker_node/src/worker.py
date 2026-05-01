"""Worker Node entry point adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from worker_node.worker import *  # noqa: F401,F403
    from worker_node.worker import handle_shutdown, pull_messages, start_health_server
except ModuleNotFoundError:
    from worker import *  # type: ignore # noqa: F401,F403
    from worker import handle_shutdown, pull_messages, start_health_server  # type: ignore


if __name__ == "__main__":
    import signal
    import threading

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info("Node Worker Entry Point: starting listeners...")
    pull_messages()
