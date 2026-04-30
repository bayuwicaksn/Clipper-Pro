"""
Backend database adapter.

Re-exports the shared DB primitives so the rest of the backend can use
the canonical ``backend.db.database`` import path without caring that the
actual implementation lives in ``shared``.
"""

from shared.db.database import create_db_and_tables, engine, get_session

__all__ = ["create_db_and_tables", "engine", "get_session"]
