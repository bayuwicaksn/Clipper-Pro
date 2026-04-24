"""
ClipperApp — Pipeline Router (FastAPI)
Handles: processing jobs, export, progress streaming (SSE), status.
"""

import os
import json
import uuid
import asyncio
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import queue as queue_module

from api import (
    WORKSPACE, jobs, progress_queues, progress_states,
    resolve_job_dir, get_clip_dir, is_new_layout,
    create_progress_callback, slugify, logger,
    timestamp_to_seconds, filter_words_by_range
)

router = APIRouter(prefix="/api", tags=["pipeline"])


# ─── Request Models ──────────────────────────────────────────────────────────
class ProcessRequest(BaseModel):
    url: str
    min_duration: int = 30
    max_duration: int = 90
    enable_hook: bool = True
    enable_captions: bool = True
    reframe_mode: str = 'opencv'
    tts_voice: str = 'alloy'
    caption_style: str = 'capcut'
    ai_provider: str = 'gpt-5.4-mini'
    transcription_provider: str = 'openai-whisper'


class ExportRequest(BaseModel):
    filename: Optional[str] = None
    clip_index: Optional[int] = None
    custom_start: Optional[str] = None
    custom_end: Optional[str] = None
    custom_crop_x: Optional[float] = None
    segments: Optional[list] = None
    caption_settings: Optional[dict] = None
    transcript: Optional[list] = None
    aspect_ratio: str = '9:16'


class ReprocessRequest(BaseModel):
    url: str = ''
    num_clips: int = 5
    min_duration: int = 30
    max_duration: int = 90
    enable_hook: bool = True
    enable_captions: bool = True
    reframe_mode: str = 'opencv'
    tts_voice: str = 'alloy'
    caption_style: str = 'capcut'


# ─── Internal Pipeline Runner ────────────────────────────────────────────────
def _run_pipeline(job_id, job_dir, config, progress_callback):
    """Execute the full clipping pipeline."""
    from core.pipeline import Pipeline

    jobs[job_id]['status'] = 'processing'
    try:
        pipeline = Pipeline(job_dir, config, progress_callback)
        clips = pipeline.run()
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['clips'] = clips
        progress_callback('done', f'Completed! Generated {len(clips)} clips.', 100)
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)
        progress_callback('error', str(e), 0)


# ─── Routes ──────────────────────────────────────────────────────────────────
@router.post('/process')
async def start_processing(data: ProcessRequest):
    """Start the full clipping pipeline."""
    if not data.url.strip():
        raise HTTPException(status_code=400, detail='YouTube URL is required')

    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(WORKSPACE, job_id)
    os.makedirs(job_dir, exist_ok=True)

    config = data.model_dump()

    jobs[job_id] = {
        'id': job_id,
        'folder_name': job_id,
        'status': 'queued',
        'config': config,
        'created_at': datetime.now().isoformat(),
        'clips': [],
        'error': None,
    }

    callback = create_progress_callback(job_id)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, job_dir, config, callback),
        daemon=True
    )
    thread.start()

    return {'job_id': job_id, 'status': 'queued'}


@router.post('/reprocess/{job_id}')
async def reprocess_job(job_id: str, data: ReprocessRequest):
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

    jobs[job_id] = {
        'id': job_id,
        'status': 'queued',
        'config': config,
        'created_at': datetime.now().isoformat(),
        'clips': [],
        'error': None,
    }

    callback = create_progress_callback(job_id)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, job_dir, config, callback),
        daemon=True
    )
    thread.start()

    return {'job_id': job_id, 'status': 'reprocessing'}


@router.get('/status/{job_id}')
async def get_status(job_id: str):
    """Get job status."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return job


@router.get('/progress/{job_id}')
async def stream_progress(job_id: str):
    """SSE endpoint for real-time progress."""
    if job_id not in progress_queues:
        progress_queues[job_id] = queue_module.Queue()

    async def event_stream():
        q = progress_queues[job_id]
        # Send padding to force flush through proxies
        yield ': ' + ' ' * 2048 + '\n\n'
        yield 'data: ' + json.dumps({'step': 'connected', 'message': 'Connected', 'progress': 0}) + '\n\n'

        while True:
            try:
                event = q.get(timeout=0.1)
                yield 'data: ' + json.dumps(event) + '\n\n'
                if event.get('step') in ('done', 'error'):
                    break
            except queue_module.Empty:
                # Non-blocking check — yield heartbeat every ~10 seconds
                await asyncio.sleep(1)
                yield 'data: ' + json.dumps({'step': 'heartbeat', 'message': 'Processing...', 'progress': -1}) + '\n\n'

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
async def poll_progress(job_id: str):
    """Polling fallback when SSE doesn't work through tunnels."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    latest = progress_states.get(job_id, {'step': 'waiting', 'message': 'Starting...', 'progress': 0})
    return {
        'status': job['status'],
        'latest_event': latest,
        'error': job.get('error'),
        'clips': job.get('clips', []),
    }


@router.post('/export/{job_id}')
async def export_clip(job_id: str, data: ExportRequest):
    """Start the targeted FFmpeg processing for a single tweaked clip."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')

    filename = data.filename
    clip_index = data.clip_index
    print(f"[EXPORT] job_id={job_id}, filename={filename}, clip_index={clip_index}")

    # Find clip metadata
    json_path = None

    if is_new_layout(job_dir):
        clips_root = os.path.join(job_dir, 'clips')
        
        if clip_index is not None:
            folder_name = f'clip_{int(clip_index)+1:02d}'
            direct_meta = os.path.join(clips_root, folder_name, 'meta.json')
            print(f"[EXPORT] Trying direct path: {direct_meta}")
            if os.path.exists(direct_meta):
                json_path = direct_meta
                print(f"[EXPORT] Found meta.json via direct folder lookup")
        
        if not json_path:
            for clip_folder in sorted(os.listdir(clips_root)):
                meta_path = os.path.join(clips_root, clip_folder, 'meta.json')
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        m = json.load(f)
                    if filename and m.get('filename') == filename:
                        json_path = meta_path
                        clip_index = m.get('clip_index', 0)
                        print(f"[EXPORT] Found meta.json via filename match in {clip_folder}")
                        break
        
        if not json_path:
            for clip_folder in sorted(os.listdir(clips_root)):
                meta_path = os.path.join(clips_root, clip_folder, 'meta.json')
                if os.path.exists(meta_path):
                    json_path = meta_path
                    clip_index = clip_index if clip_index is not None else 0
                    print(f"[EXPORT] Fallback: using first meta.json found in {clip_folder}")
                    break

    if not json_path:
        json_path = os.path.join(job_dir, 'output', (filename or '').replace('.mp4', '.json'))
    if not os.path.exists(json_path):
        print(f"[EXPORT] ERROR: No meta.json found! json_path={json_path}")
        raise HTTPException(status_code=404, detail='Clip metadata not found')

    with open(json_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    config = {}
    for loc in ['session.json', os.path.join('output', 'session.json')]:
        session_path = os.path.join(job_dir, loc)
        if os.path.exists(session_path):
            with open(session_path, 'r', encoding='utf-8') as f:
                config = json.load(f).get('config', {})
            break

    if data.caption_settings:
        print(f"[DEBUG] Exporting with caption settings: {data.caption_settings}")
        config['caption_settings'] = data.caption_settings

    if data.transcript:
        metadata['transcript'] = data.transcript
    else:
        try:
            source_transcript_path = os.path.join(job_dir, 'source_transcript.json')
            if os.path.exists(source_transcript_path):
                with open(source_transcript_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                all_words = raw.get('words', raw) if isinstance(raw, dict) else raw
                
                segs = data.segments or []
                if segs:
                    clip_start = min(s.get('start', 0) for s in segs)
                    clip_end = max(s.get('end', 0) for s in segs)
                else:
                    clip_start = timestamp_to_seconds(metadata.get('start_time', '00:00:00'))
                    clip_end = timestamp_to_seconds(metadata.get('end_time', '00:00:00'))
                
                filtered = filter_words_by_range(all_words, clip_start, clip_end)
                metadata['transcript'] = filtered
                print(f"[EXPORT] Loaded {len(filtered)} words from source_transcript.json (range: {clip_start:.1f}s - {clip_end:.1f}s)")
        except Exception as e:
            print(f"[EXPORT] Warning: could not load source transcript: {e}")

    export_id = f"{job_id}-export"
    
    jobs[export_id] = {
        'id': export_id,
        'status': 'queued',
        'error': None
    }

    def run_export():
        jobs[export_id]['status'] = 'processing'
        callback = create_progress_callback(export_id)
        try:
            from core.pipeline import Pipeline
            pipeline = Pipeline(job_dir, config, callback)
            
            final_data = pipeline.export_single_clip(
                metadata, 
                custom_start=data.custom_start, 
                custom_end=data.custom_end, 
                custom_crop_x=data.custom_crop_x,
                segments=data.segments,
                clip_index=clip_index,
                aspect_ratio=data.aspect_ratio
            )
            
            session_path = os.path.join(job_dir, 'session.json')
            if os.path.exists(session_path):
                with open(session_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                clips = session_data.get('clips', [])
                if clip_index is not None and int(clip_index) < len(clips):
                    clips[int(clip_index)] = final_data
                    with open(session_path, 'w', encoding='utf-8') as f:
                        json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
                
            jobs[export_id]['status'] = 'completed'
            jobs[export_id]['clips'] = [final_data]
            callback('done', 'Export finished.', 100)
            
        except Exception as e:
            jobs[export_id]['status'] = 'error'
            jobs[export_id]['error'] = str(e)
            callback('error', str(e), 0)

    thread = threading.Thread(target=run_export, daemon=True)
    thread.start()

    return {'export_id': export_id, 'status': 'queued'}
