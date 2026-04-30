"""
Shared database package.

Exposes the three core objects needed by every service:
    - engine  (SQLAlchemy engine)
    - get_session (FastAPI dependency / context-manager)
    - create_db_and_tables (startup initialiser)
    - crud  (CRUD helper module)
"""

from shared.db.database import create_db_and_tables, engine, get_session
from shared.db import crud
from shared.db.models import Job

__all__ = [
    "Job",
    "crud",
    "create_db_and_tables",
    "engine",
    "get_session",
]
