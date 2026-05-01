import os
import sys
import json
import logging
import signal
import base64
import threading
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException

# Import from shared modules
from shared.core.pipeline import Pipeline
from shared.db import crud
from shared.db.database import engine
from sqlmodel import Session
from shared.config import settings

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_gpu")

app = FastAPI(title="Clipper Worker GPU")

# ── Database Update Helper ─────────────────────────────────────────────
def update_job_db(job_id: str, data: dict):
    try:
        with Session(engine) as session:
            crud.update_job(session, job_id, data)
            return True
    except Exception as e:
        logger.error(f"[{job_id}] Database update failed: {e}")
        return False

# ── Processing Logic ──────────────────────────────────────────────────
def process_job_task(job_data: dict):
    """Heavy lifting logic moved to a background task."""
    job_id = job_data.get("job_id")
    config = job_data.get("config", {})
    
    if not job_id:
        logger.error("Job data missing job_id")
        return

    from shared.utils.logging_utils import set_correlation_id
    set_correlation_id(job_id)

    workspace_root = os.getenv("CLIPPER_WORKSPACE", "workspace")
    job_dir = os.path.join(workspace_root, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        update_job_db(job_id, {"status": "processing", "progress": 5})
        
        def progress_callback(step, message, progress):
            logger.info(f"[{job_id}] {step}: {message} ({progress}%)")
            update_job_db(job_id, {
                "status": "processing",
                "progress": progress,
                "status_message": f"{step}: {message}"
            })

        pipeline = Pipeline(job_dir, config, progress_callback)
        clips_metadata = pipeline.run()

        update_job_db(job_id, {
            "status": "completed",
            "clips": clips_metadata or [],
            "status_message": "Analysis complete",
            "error_message": None 
        })
    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        update_job_db(job_id, {"status": "error", "error_message": str(e)})

def process_export_task(export_data: dict):
    job_id = export_data.get("job_id")
    export_id = export_data.get("export_id")
    job_dir = export_data.get("job_dir")
    clip_metadata = export_data.get("clip_metadata")
    export_config = export_data.get("export_config", {})

    if not export_id: return

    try:
        update_job_db(export_id, {"status": "processing", "progress": 10})
        def callback(step, message, progress):
            logger.info(f"[{export_id}] {step}: {message} ({progress}%)")
            update_job_db(export_id, {"status": "processing", "progress": progress, "status_message": message})

        p = Pipeline(job_dir, {}, progress_callback=callback)
        p.export_single_clip(
            clip_metadata,
            custom_start=export_config.get("custom_start"),
            custom_end=export_config.get("custom_end"),
            custom_crop_x=export_config.get("custom_crop_x"),
            segments=export_config.get("segments"),
            aspect_ratio=export_config.get("aspect_ratio")
        )
        update_job_db(export_id, {"status": "completed", "progress": 100})
    except Exception as e:
        logger.error(f"[{export_id}] Export failed: {e}", exc_info=True)
        update_job_db(export_id, {"status": "error", "error_message": str(e)})

# ── API Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
@app.get("/")
async def health():
    return {"status": "ok", "worker": "gpu"}

@app.post("/pubsub")
async def pubsub_handler(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Pub/Sub Push messages."""
    try:
        envelope = await request.json()
        if not envelope or "message" not in envelope:
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")

        payload_raw = envelope["message"].get("data")
        if not payload_raw:
            return {"status": "ignored", "reason": "no_data"}

        payload = json.loads(base64.b64decode(payload_raw).decode("utf-8"))
        
        # Determine if it's a job or an export
        if "export_id" in payload:
            logger.info(f"Received Export Push: {payload.get('export_id')}")
            background_tasks.add_task(process_export_task, payload)
        else:
            logger.info(f"Received Job Push: {payload.get('job_id')}")
            background_tasks.add_task(process_job_task, payload)

        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Pub/Sub handler error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    # Initialize diagnostics
    from shared.core.gpu_utils import run_gpu_diagnostics
    run_gpu_diagnostics()
    uvicorn.run(app, host="0.0.0.0", port=port)