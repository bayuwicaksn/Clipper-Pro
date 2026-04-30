import logging
import json
import time
import os
import threading
from typing import Any, Optional

# Thread-local storage for correlation ID
_local = threading.local()

def set_correlation_id(correlation_id: str):
    _local.correlation_id = correlation_id

def get_correlation_id() -> Optional[str]:
    return getattr(_local, "correlation_id", None)

class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format for Google Cloud Logging.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Check thread-local if not already on record
        corr_id = getattr(record, "correlation_id", get_correlation_id())
        
        log_data = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "logging.googleapis.com/sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
            "logger": record.name,
            "correlation_id": corr_id,
        }
        
        # Add extra fields if provided via 'extra' param
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

class CorrelationIdFilter(logging.Filter):
    """
    Injects correlation_id into log records from thread-local storage.
    """
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True

def setup_structured_logging(level=logging.INFO):
    """
    Configure the root logger to use JSON formatting in production.
    """
    handler = logging.StreamHandler()
    
    if os.getenv("ENVIRONMENT") == "production":
        formatter = JsonFormatter()
    else:
        # Pretty console format for dev
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
        )
        
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Clear existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    # Add the filter to the root logger
    root_logger.addFilter(CorrelationIdFilter())
    
    return root_logger
