"""
Database engine and session factory.

Uses absolute imports so this module works correctly when imported from
backend/, worker_gpu/, worker_node/, or the CLI — without needing the
caller to manipulate sys.path.
"""

import os
import logging
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine

logger = logging.getLogger(__name__)

# ── Resolve DATABASE_URL ───────────────────────────────────────────────────
_raw_url = os.getenv("DATABASE_URL")

if not _raw_url:
    raise ValueError("CRITICAL: DATABASE_URL environment variable is missing or empty. Please check your .env or Cloud Run secrets.")

# Heroku / Supabase ship postgres:// but SQLAlchemy requires postgresql://
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

if "://" not in _raw_url:
    raise ValueError(f"CRITICAL: DATABASE_URL is malformed: '{_raw_url}'. It must be a valid URI (e.g., postgresql://...).")

# ── Engine ────────────────────────────────────────────────────────────────
_connect_args: dict = {}
_engine_kwargs: dict = {
    "echo": os.getenv("DEBUG", "false").lower() == "true",
}

if _raw_url.startswith("sqlite"):
    # SQLite: allow access from multiple threads (FastAPI / workers).
    _connect_args["check_same_thread"] = False
    _engine_kwargs["connect_args"] = _connect_args
else:
    # PostgreSQL / Supabase: use a small connection pool.
    _engine_kwargs.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_pre_ping": True,        # Drop stale connections immediately
            "pool_recycle": 1800,         # Recycle connections every 30 min
        }
    )

engine = create_engine(_raw_url, **_engine_kwargs)


def create_db_and_tables() -> None:
    """
    Create all tables defined in SQLModel metadata.

    Safe to call multiple times — SQLModel is idempotent when tables already
    exist (it uses CREATE TABLE IF NOT EXISTS internally).
    """
    # Import models here to guarantee they are registered in SQLModel.metadata
    # before create_all() is called.
    from shared.db.models import Job  # noqa: F401

    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables verified / created.")
    except Exception as exc:
        logger.error("Failed to create database tables: %s", exc, exc_info=True)
        raise


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and auto-commits /
    rolls back on exit.

    Usage::

        @router.get("/items")
        def list_items(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
