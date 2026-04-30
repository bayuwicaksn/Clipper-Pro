"""
ClipperApp â€” Pipeline Router (FastAPI)
Handles: processing jobs, export, progress streaming (SSE), status.
"""

import os
from ..core.config import settings
import json
import uuid
import asyncio
import time
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import Field
from typing import Optional
import queue as queue_module
from sqlmodel import Session

from . import (
    WORKSPACE, progress_queues, progress_states,
    resolve_job_dir, get_clip_dir, is_new_layout,
    create_progress_callback, slugify, logger,
    timestamp_to_seconds, filter_words_by_range
)
from shared.db import crud
from shared.pubsub import Publisher # NEW
from backend.db.database import get_session, engine
from .schemas import ProcessRequest, ExportRequest, ReprocessRequest, JobResponse
from ..services import job_service

router = APIRouter(prefix="/api", tags=["pipeline"])


# â”€â”€â”€ Internal Pipeline Runner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _run_pipeline(job_id, job_dir, config, progress_callback):
    """Execute the full clipping pipeline via job_service."""
    job_service.start_job(job_id, job_dir, config, progress_callback)


@router.post('/process')
async def start_processing(data: ProcessRequest, session: Session = Depends(get_session)):
    """Start the full clipping pipeline by publishing to Pub/Sub."""
    if not data.url.strip():
        raise HTTPException(status_code=400, detail='YouTube URL is required')

    job_id = str(uuid.uuid4())[:8]
    config = data.model_dump()

    # Create job in database
    crud.create_job(session, job_id, config)

    # Publish to Pub/Sub
    project_id = settings.GCP_PROJECT_ID
    topic_id = settings.PUBSUB_TOPIC_JOBS

    if project_id:
        try:
            pub = Publisher(project_id)
            payload = {
                "job_id": job_id,
                "config": config,
                "timestamp": time.time()
            }
            
            success = pub.publish(topic_id, payload)
            if not success:
                raise Exception("Publisher failed after retries")
            
            logger.info(f"[Pub/Sub] Published job {job_id} to {topic_id}")
        except Exception as e:
            logger.error(f"[Pub/Sub] Failed to publish: {e}")
            if os.getenv("ENVIRONMENT") == "production":
                crud.update_job_status(session, job_id, 'error', error_message=f"Pub/Sub Error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to queue job: {e}")
    
    else:
        logger.warning(f"[Dev] GCP_PROJECT_ID not set. Job {job_id} created but not queued.")

    return {'job_id': job_id, 'status': 'queued'}


@router.post('/pipeline/reprocess/{job_id}')
async def reprocess_job(job_id: str, data: ReprocessRequest, session: Session = Depends(get_session)):
    """Re-run the pipeline for an existing job."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail=f'Job {job_id} not found in workspace')

    url = data.url
    if not url:
        info_path = os.path.join(job_dir, 'source.info.json')
        if os.path.exists(info_path):
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
                url = info.get('webpage_url', info.get('original_url', ''))

    if not url:
        raise HTTPException(status_code=400, detail='Could not determine video URL. Pass it in the request body.')

    config = data.model_dump()
    config['url'] = url

    output_dir = os.path.join(job_dir, 'output')
    if os.path.exists(output_dir):
        for f in os.listdir(output_dir):
            os.remove(os.path.join(output_dir, f))

    for f in os.listdir(job_dir):
        if f.startswith('full_audio'):
            os.remove(os.path.join(job_dir, f))

    crud.create_job(session, job_id, config)

    callback = create_progress_callback(job_id)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, job_dir, config, callback),
        daemon=True
    )
    thread.start()

    return {'job_id': job_id, 'status': 'reprocessing'}


@router.get('/status/{job_id}', response_model=JobResponse)
async def get_status(job_id: str, session: Session = Depends(get_session)):
    """Get job status."""
    job = crud.get_job(session, job_id)
    if not job:
        job_dir = resolve_job_dir(job_id)
        if job_dir and os.path.exists(os.path.join(job_dir, 'session.json')):
             return {
                'id': job_id,
                'status': 'completed',
                'config': {},
                'created_at': datetime.now(),
                'clips': [],
                'error': None
            }
        raise HTTPException(status_code=404, detail='Job not found')
    
    def safe_json(val):
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except:
                return {}
        return val

    return {
        'id': job.id,
        'status': job.status,
        'progress': job.progress,
        'status_message': job.status_message,
        'error_message': job.error_message,
        'config': safe_json(job.config),
        'created_at': job.created_at.isoformat() if hasattr(job.created_at, 'isoformat') else str(job.created_at),
        'clips': safe_json(job.clips) or [],
        'error': job.error
    }


@router.get('/progress/{job_id}')
async def stream_progress(job_id: str):
    """SSE endpoint for real-time progress."""
    if job_id not in progress_queues:
        progress_queues[job_id] = queue_module.Queue()

    async def event_stream():
        q = progress_queues[job_id]
        yield ': ' + ' ' * 2048 + '\n\n'
        yield 'data: ' + json.dumps({'step': 'connected', 'message': 'Connected', 'progress': 0}) + '\n\n'

        while True:
            try:
                # 1. Check local queue
                event = q.get(timeout=1.0)
                yield 'data: ' + json.dumps(event) + '\n\n'
                if event.get('step') in ('done', 'error'):
                    break
            except queue_module.Empty:
                # 2. Check Database status (Polling fallback)
                with Session(engine) as session:
                    job = crud.get_job(session, job_id)
                    if job:
                        if job.status == 'completed':
                            yield 'data: ' + json.dumps({
                                'step': 'done', 
                                'message': job.status_message or 'Job completed!', 
                                'progress': 100,
                                'status_message': job.status_message
                            }) + '\n\n'
                            break
                        elif job.status == 'error':
                            yield 'data: ' + json.dumps({
                                'step': 'error', 
                                'message': job.error_message or 'Job failed', 
                                'progress': 0,
                                'error_message': job.error_message
                            }) + '\n\n'
                            break
                        elif job.status == 'processing':
                            yield 'data: ' + json.dumps({
                                'step': 'processing',
                                'message': job.status_message or 'Processing...',
                                'progress': job.progress,
                                'status_message': job.status_message
                            }) + '\n\n'
                
                # 3. Heartbeat (Ping) to keep connection alive
                yield ': ping\n\n'
                await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@router.get('/progress-poll/{job_id}')
async def poll_progress(job_id: str, session: Session = Depends(get_session)):
    """Polling fallback."""
    job = crud.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    
    def safe_json(val):
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except:
                return {}
        return val

    latest = progress_states.get(job_id, {'step': 'waiting', 'message': 'Starting...', 'progress': 0})
    return {
        'status': job.status,
        'latest_event': latest,
        'error': job.error,
        'clips': safe_json(job.clips) or [],
    }


@router.post('/export/{job_id}')
async def export_clip(job_id: str, data: ExportRequest, session: Session = Depends(get_session)):
    """Start targeted FFmpeg processing for a single clip."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')

    filename = data.filename
    clip_index = data.clip_index
    logger.info(f"[EXPORT] job_id={job_id}, filename={filename}, clip_index={clip_index}")

    json_path = None
    if is_new_layout(job_dir):
        clips_root = os.path.join(job_dir, 'clips')
        if clip_index is not None:
            folder_name = f'clip_{int(clip_index)+1:02d}'
            direct_meta = os.path.join(clips_root, folder_name, 'meta.json')
            if os.path.exists(direct_meta):
                json_path = direct_meta
        
        if not json_path:
            for clip_folder in sorted(os.listdir(clips_root)):
                meta_path = os.path.join(clips_root, clip_folder, 'meta.json')
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        m = json.load(f)
                    if filename and m.get('filename') == filename:
                        json_path = meta_path
                        clip_index = m.get('clip_index', 0)
                        break

    if not json_path:
        raise HTTPException(status_code=404, detail='Clip metadata not found')

    with open(json_path, 'r', encoding='utf-8') as f:
        clip_metadata = json.load(f)

    # Generate a unique export ID to avoid overwriting previous runs of the same clip
    export_id = f"export_{job_id}_{clip_index or 0}_{str(uuid.uuid4())[:8]}"

    # 1. Create the job record in DB so the worker can update it
    try:
        from shared.db.models import Job
        from shared.db.database import engine
        from sqlmodel import Session
        # Create or Reset job record for tracking
        existing_job = crud.get_job(session, export_id)
        if existing_job:
            crud.update_job(session, export_id, {
                "status": "queued",
                "error_message": None,
                "updated_at": datetime.now()
            })
            logger.info(f"[EXPORT] Reset existing job record for retry: {export_id}")
        else:
            try:
                crud.create_job(session, export_id, data.model_dump())
            except Exception as e:
                logger.warning(f"[EXPORT] Failed to create job record: {e}")
    except Exception as e:
        logger.warning(f"[EXPORT] Job record creation skipped (maybe exists): {e}")

    # 2. Use a dedicated topic for exports (Recommended for isolation)
    project_id = settings.GCP_PROJECT_ID
    topic_id = settings.PUBSUB_TOPIC_EXPORT 

    if project_id:
        try:
            pub = Publisher(project_id)
            export_payload = {
                "job_id": job_id,
                "export_id": export_id,
                "job_dir": job_dir,
                "clip_metadata": clip_metadata,
                "export_config": data.model_dump(),
                "timestamp": time.time()
            }

            success = pub.publish(topic_id, export_payload)
            if not success:
                raise Exception("Export Publisher failed after retries")
                
            logger.info(f"[Pub/Sub] Export job for {job_id} sent to {topic_id}")
            return {"export_id": export_id, "status": "queued"}
        except Exception as e:
            logger.error(f"[Pub/Sub] Failed to publish export: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to queue export: {e}")

    # Fallback for local development if GCP is not configured
    logger.warning("[Dev] GCP_PROJECT_ID not set. Running export locally (not recommended).")
    
    def _run_export():
        try:
            from shared.core.pipeline import Pipeline
            p = Pipeline(job_dir, {}, progress_callback=callback)
            p.export_single_clip(
                clip_metadata,
                custom_start=data.custom_start,
                custom_end=data.custom_end,
                custom_crop_x=data.custom_crop_x,
                segments=data.segments,
                aspect_ratio=data.aspect_ratio
            )
            callback('done', 'Export successful', 100)
        except Exception as e:
            logger.error(f"[EXPORT] Failed: {e}")
            callback('error', str(e), 0)

    threading.Thread(target=_run_export, daemon=True).start()
    return {"export_id": export_id, "status": "started_local"}
