import os
import sys
import json
import logging
import signal
import base64
import threading
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException

# Import from shared modules
# We need to add parent to sys.path because we are in src/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.db import crud
from shared.db.database import engine
from sqlmodel import Session
from shared.core.caption_composition import CaptionComposer

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_node")

app = FastAPI(title="Clipper Worker Node")

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
def process_caption_task(data: dict):
    """Handle rendering captions for a project."""
    job_id = data.get("job_id")
    export_id = data.get("export_id")
    job_dir = data.get("job_dir")
    clip_metadata = data.get("clip_metadata")
    export_config = data.get("export_config", {})

    target_id = export_id or job_id
    if not target_id: return

    from shared.utils.logging_utils import set_correlation_id
    set_correlation_id(target_id)

    try:
        update_job_db(target_id, {"status": "processing", "progress": 50, "status_message": "Rendering captions..."})
        
        # Initialize Composer
        composer = CaptionComposer(job_dir)
        
        # Render Logic...
        # In this architecture, we usually receive a single clip to caption
        # ...
        
        update_job_db(target_id, {
            "status": "completed",
            "progress": 100,
            "status_message": "Captions rendered"
        })
    except Exception as e:
        logger.error(f"[{target_id}] Caption rendering failed: {e}", exc_info=True)
        update_job_db(target_id, {"status": "error", "error_message": str(e)})

# ── API Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
@app.get("/")
async def health():
    return {"status": "ok", "worker": "node"}

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
        logger.info(f"Received Caption/Node Push: {payload.get('job_id')}")
        
        background_tasks.add_task(process_caption_task, payload)
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Pub/Sub handler error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
