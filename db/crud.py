from sqlmodel import Session, select
from db.models import Job
import json
from datetime import datetime
from typing import Optional, List

def create_job(session: Session, job_id: str, config: dict) -> Job:
    job = Job(
        id=job_id,
        status="queued",
        created_at=datetime.now(),
        config=json.dumps(config),
        clips="[]"
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

def get_job(session: Session, job_id: str) -> Optional[Job]:
    statement = select(Job).where(Job.id == job_id)
    return session.exec(statement).first()

def update_job_status(session: Session, job_id: str, status: str, error: Optional[str] = None) -> Optional[Job]:
    job = get_job(session, job_id)
    if job:
        job.status = status
        job.error = error
        session.add(job)
        session.commit()
        session.refresh(job)
    return job

def update_job_clips(session: Session, job_id: str, clips: list) -> Optional[Job]:
    job = get_job(session, job_id)
    if job:
        job.clips = json.dumps(clips)
        session.add(job)
        session.commit()
        session.refresh(job)
    return job

def list_jobs(session: Session) -> List[Job]:
    statement = select(Job).order_by(Job.created_at.desc())
    return session.exec(statement).all()

def delete_job(session: Session, job_id: str) -> bool:
    job = get_job(session, job_id)
    if job:
        session.delete(job)
        session.commit()
        return True
    return False
