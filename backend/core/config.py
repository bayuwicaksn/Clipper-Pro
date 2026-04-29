"""Backend settings adapter.

The canonical settings object currently lives in shared.config so backend and
workers read the same environment contract.
"""

from shared.config import Settings, settings

__all__ = ["Settings", "settings"]
