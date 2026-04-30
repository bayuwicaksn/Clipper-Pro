"""
CRUD helpers for the Job model.

All functions accept an open SQLModel Session and return the mutated/fetched
object (or None / bool on failure).  Callers own the session lifecycle.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, select

from shared.db.models import Job

logger = logging.getLogger(__name__)


# ── Create ────────────────────────────────────────────────────────────────

def create_job(session: Session, job_id: str, config: dict) -> Job:
    """
    Insert a new Job row.  If a row with the same *job_id* already exists it
    is deleted first so callers can safely call this on re-process.
    """
    # Clean up any stale row from a previous attempt.
    existing = get_job(session, job_id)
    if existing:
        session.delete(existing)
        session.flush()

    job = Job(
        id=job_id,
        status="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        config=json.dumps(config, ensure_ascii=False),
        clips="[]",
        error=None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    logger.info("Created job %s", job_id)
    return job


# ── Read ──────────────────────────────────────────────────────────────────

def get_job(session: Session, job_id: str) -> Optional[Job]:
    """Return the Job with *job_id*, or None if not found."""
    statement = select(Job).where(Job.id == job_id)
    return session.exec(statement).first()


def list_jobs(session: Session, limit: int = 100) -> List[Job]:
    """Return the most-recently-created jobs (newest first)."""
    statement = select(Job).order_by(Job.created_at.desc()).limit(limit)
    return list(session.exec(statement).all())


# ── Update ────────────────────────────────────────────────────────────────

def _touch(job: Job) -> None:
    """Update the updated_at timestamp in-place (no commit)."""
    job.updated_at = datetime.utcnow()


def update_job_status(
    session: Session,
    job_id: str,
    status: str,
    status_message: Optional[str] = "KEEP_EXISTING",
    error_message: Optional[str] = "KEEP_EXISTING",
) -> Optional[Job]:
    """
    Set the job status (and optionally informative messages).
    Returns the updated Job or None if not found.
    """
    job = get_job(session, job_id)
    if not job:
        logger.warning("update_job_status: job %s not found", job_id)
        return None

    job.status = status
    if status_message != "KEEP_EXISTING":
        job.status_message = str(status_message)[:4096] if status_message is not None else None
    if error_message != "KEEP_EXISTING":
        job.error_message = str(error_message)[:4096] if error_message is not None else None

    _touch(job)
    session.add(job)
    session.commit()
    session.refresh(job)
    logger.debug("Job %s status → %s", job_id, status)
    return job


def update_job_clips(
    session: Session, job_id: str, clips: list
) -> Optional[Job]:
    """Persist a new clips list (serialised as JSON) for *job_id*."""
    job = get_job_config(session, job_id) # wait, the fix had get_job
    job = get_job(session, job_id)
    if not job:
        logger.warning("update_job_clips: job %s not found", job_id)
        return None

    job.clips = json.dumps(clips, ensure_ascii=False)
    _touch(job)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def update_job(session: Session, job_id: str, data: dict) -> Optional[Job]:
    """
    Generic field-level update.  Only columns that actually exist on the
    Job model are written; unknown keys are silently ignored so callers
    don't need to maintain an allowlist.
    """
    job = get_job(session, job_id)
    if not job:
        logger.warning("update_job: job %s not found", job_id)
        return None

    allowed_columns = {col for col in Job.__fields__}
    for key, value in data.items():
        if key in allowed_columns:
            # Serialise list/dict values that map to JSON columns.
            if isinstance(value, (list, dict)) and key in ("clips", "config"):
                value = json.dumps(value, ensure_ascii=False)
            setattr(job, key, value)
        else:
            logger.debug("update_job: ignoring unknown field '%s'", key)

    _touch(job)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


# ── Delete ────────────────────────────────────────────────────────────────

def delete_job(session: Session, job_id: str) -> bool:
    """Delete a job by id.  Returns True if deleted, False if not found."""
    job = get_job(session, job_id)
    if not job:
        return False
    session.delete(job)
    session.commit()
    logger.info("Deleted job %s", job_id)
    return True


# ── Helpers ───────────────────────────────────────────────────────────────

def get_job_config(session: Session, job_id: str) -> Optional[dict]:
    """Return the config dict for a job, or None."""
    job = get_job(session, job_id)
    if not job or not job.config:
        return None
    try:
        return json.loads(job.config)
    except json.JSONDecodeError:
        logger.error("Job %s has invalid JSON in config column", job_id)
        return None


def get_job_clips(session: Session, job_id: str) -> List[dict]:
    """Return the clips list for a job, or []."""
    job = get_job(session, job_id)
    if not job or not job.clips:
        return []
    try:
        return json.loads(job.clips) or []
    except json.JSONDecodeError:
        logger.error("Job %s has invalid JSON in clips column", job_id)
        return []
