
import sys
import os
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, create_engine, SQLModel
from shared.db.models import Job
from shared.db import crud

def test_job_state_model():
    sqlite_url = "sqlite://"
    engine = create_engine(sqlite_url)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        job_id = "test-123"
        crud.create_job(session, job_id, {"test": True})
        
        # 1. Test standard progress update
        crud.update_job_status(session, job_id, "processing", status_message="Downloading video...")
        job = crud.get_job(session, job_id)
        assert job.status == "processing"
        assert job.status_message == "Downloading video..."
        assert job.error_message is None
        assert job.error is None
        
        # 2. Test error update
        crud.update_job_status(session, job_id, "error", error_message="Disk Full")
        job = crud.get_job(session, job_id)
        assert job.status == "error"
        assert job.error_message == "Disk Full"
        assert job.error == "Disk Full"
        
        # 3. Test completion
        crud.update_job_status(session, job_id, "completed", status_message="Done!", error_message=None)
        job = crud.get_job(session, job_id)
        assert job.status == "completed"
        assert job.error_message is None
        assert job.status_message == "Done!"

if __name__ == "__main__":
    test_job_state_model()
    sys.exit(0)
