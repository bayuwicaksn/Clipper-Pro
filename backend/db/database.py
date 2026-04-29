"""Backend DB adapter.

DB primitives are shared with workers while the backend keeps the target
backend/db import path.
"""

from shared.db.database import create_db_and_tables, engine, get_session

__all__ = ["create_db_and_tables", "engine", "get_session"]
