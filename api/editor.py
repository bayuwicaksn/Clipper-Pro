"""
ClipperApp — Editor Router (FastAPI)
Handles: editor state save/load, transcript API.
"""

import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Query
from typing import Optional

from api import (
    resolve_job_dir, get_clip_dir, is_new_layout, logger,
    timestamp_to_seconds, filter_words_by_range, get_source_transcript
)

router = APIRouter(prefix="/api", tags=["editor"])


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _get_clip_bounds(job_dir, clip_index):
    """Get clip start/end from meta.json, falling back to session.json."""
    clip_dir = get_clip_dir(job_dir, clip_index)
    meta_path = os.path.join(clip_dir, 'meta.json')
    
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        start = timestamp_to_seconds(meta.get('start_time', '00:00:00'))
        end = timestamp_to_seconds(meta.get('end_time', '00:00:00'))
        if end > start:
            return start, end
    
    session_path = os.path.join(job_dir, 'session.json')
    if os.path.exists(session_path):
        with open(session_path, 'r', encoding='utf-8') as f:
            session = json.load(f)
        clips = session.get('clips', [])
        idx = int(clip_index)
        if idx < len(clips):
            start = timestamp_to_seconds(clips[idx].get('start_time', '00:00:00'))
            end = timestamp_to_seconds(clips[idx].get('end_time', '00:00:00'))
            if end > start:
                return start, end
    
    return 0, 0


# ─── Routes ──────────────────────────────────────────────────────────────────
@router.post('/save_editor/{job_id}')
async def save_editor_state(job_id: str, request: Request, clip_index: int = Query(0)):
    """Save the current editor state (segments, active clip, etc.) to disk."""
    try:
        job_dir = resolve_job_dir(job_id)
        
        logger.info(f"[SAVE] Attempting to save state for job: {job_id}")

        if not job_dir:
            logger.error(f"[SAVE] Error: Job directory not found: {job_id}")
            raise HTTPException(status_code=404, detail=f'Job directory for {job_id} not found.')

        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail='No data provided')

        clip_index = data.get('clip_index', clip_index)
        
        if is_new_layout(job_dir):
            clip_dir = get_clip_dir(job_dir, clip_index)
            state_path = os.path.join(clip_dir, 'editor_state.json')
        else:
            output_dir = os.path.join(job_dir, 'output')
            os.makedirs(output_dir, exist_ok=True)
            state_path = os.path.join(output_dir, f'editor_state_{clip_index}.json')

        # MASTER SYNC: Update session.json
        session_path = os.path.join(job_dir, 'session.json')
        updated_clip = data.get('clip')
        
        if os.path.exists(session_path) and updated_clip:
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            clips = session_data.get('clips', [])
            idx = int(clip_index)
            if idx < len(clips):
                orig_index = clips[idx].get('clip_index', idx)
                clips[idx].update(updated_clip)
                clips[idx]['clip_index'] = orig_index
                
                with open(session_path, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2, ensure_ascii=False)
                
                if is_new_layout(job_dir):
                    meta_path = os.path.join(get_clip_dir(job_dir, clip_index), 'meta.json')
                    with open(meta_path, 'w', encoding='utf-8') as f:
                        json.dump(clips[idx], f, indent=2, ensure_ascii=False)
                    logger.info(f"[SAVE] Synced session.json -> meta.json for clip {idx}")

        editor_state = {
            'active_clip_index': int(clip_index),
            'segments': data.get('segments', []),
            'caption_settings': data.get('caption_settings', {}),
            'active_segment_index': data.get('active_segment_index', 0),
            'saved_at': datetime.now().isoformat()
        }

        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(editor_state, f, indent=2, ensure_ascii=False)

        logger.info(f"[SAVE] Successfully saved state to {state_path}")
        return {'status': 'saved', 'saved_at': editor_state['saved_at'], 'clip_index': clip_index}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SAVE] Critical Exception: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/load_editor/{job_id}')
async def load_editor_state(job_id: str, clip_index: int = Query(0)):
    """Load saved editor state from disk."""
    try:
        job_dir = resolve_job_dir(job_id)
        if not job_dir:
            return {'exists': False, 'message': 'Job not found.'}
        
        if is_new_layout(job_dir):
            clip_dir = get_clip_dir(job_dir, clip_index)
            state_path = os.path.join(clip_dir, 'editor_state.json')
            if os.path.exists(state_path):
                with open(state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['exists'] = True
                    return data
        
        state_path = os.path.join(job_dir, 'output', f'editor_state_{clip_index}.json')
        if not os.path.exists(state_path) and str(clip_index) == '0':
            state_path = os.path.join(job_dir, 'output', 'editor_state.json')

        if not os.path.exists(state_path):
            return {'exists': False, 'message': 'No saved state found.'}

        with open(state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data['exists'] = True
            return data
    except Exception as e:
        print(f"[LOAD] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/transcript/{job_id}/{clip_index}')
async def get_transcript(job_id: str, clip_index: str, force: bool = Query(False)):
    """Return word-level transcript filtered to the clip's current bounds."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        provider = 'openai-whisper'
        session_path = os.path.join(job_dir, 'session.json')
        if os.path.exists(session_path):
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                provider = session_data.get('config', {}).get('transcription_provider', 'openai-whisper')
        
        _, all_words = get_source_transcript(job_dir, force=force, provider=provider)
        
        if not all_words:
            return []
        
        start_sec, end_sec = _get_clip_bounds(job_dir, clip_index)
        
        if end_sec <= start_sec:
            logger.warning(f"[TRANSCRIPT] Invalid bounds start={start_sec}, end={end_sec}. Returning all words.")
            return all_words
        
        filtered = filter_words_by_range(all_words, start_sec, end_sec)
        
        logger.info(f"[TRANSCRIPT] Filtered {len(all_words)} -> {len(filtered)} words for clip {clip_index}")
        
        return filtered
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/transcript/{job_id}/{clip_index}')
async def save_transcript(job_id: str, clip_index: str, request: Request):
    """Save edited transcript."""
    data = await request.json()
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail="Job not found")
        
    clip_dir = get_clip_dir(job_dir, clip_index)
    transcript_path = os.path.join(clip_dir, 'transcript.json')

    with open(transcript_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    return {"status": "saved"}
