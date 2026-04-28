"""
ClipperApp — AI Router (FastAPI)
Handles: caption presets, scene detection, face tracking, clip regeneration.
"""

import os
import re
import json
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from api import (
    resolve_job_dir, get_clip_dir, is_new_layout, logger,
    timestamp_to_seconds
)
from api.schemas import RegenerateRequest

router = APIRouter(prefix="/api", tags=["ai"])




@router.get('/captions/presets')
async def get_caption_presets():
    """Get available pycaps caption presets with their configuration."""
    import pycaps
    
    pycaps_dir = os.path.dirname(pycaps.__file__)
    preset_dir = os.path.join(pycaps_dir, 'template', 'preset')
    
    presets_data = []
    
    if not os.path.exists(preset_dir):
        preset_names = ['classic', 'default', 'explosive', 'fast', 'hype', 'line-focus', 'minimalist', 'neo-minimal', 'retro-gaming', 'vibrant', 'word-focus']
    else:
        preset_names = [d for d in os.listdir(preset_dir) if os.path.isdir(os.path.join(preset_dir, d))]

    PRESET_STYLES = {
        'classic':     {'font': 'Anton', 'color': '#FFFFFF', 'outline': '#000000'},
        'default':     {'font': 'Anton', 'color': '#FFFFFF', 'outline': '#000000'},
        'explosive':   {'font': 'Anton', 'color': '#FF3B30', 'outline': '#FFFFFF'},
        'fast':        {'font': 'Anton', 'color': '#FFD60A', 'outline': '#000000'},
        'hype':        {'font': 'Anton', 'color': '#007AFF', 'outline': '#FFFFFF'},
        'line-focus':  {'font': 'Inter', 'color': '#FFFFFF', 'outline': 'transparent'},
        'minimalist':  {'font': 'Inter', 'color': '#FFFFFF', 'outline': 'transparent'},
        'model':       {'font': 'Anton', 'color': '#FFFFFF', 'outline': '#000000'},
        'neo-minimal': {'font': 'Inter', 'color': '#FFFFFF', 'outline': 'transparent'},
        'retro-gaming':{'font': 'Press Start 2P', 'color': '#34C759', 'outline': '#000000'},
        'vibrant':     {'font': 'Anton', 'color': '#5856D6', 'outline': '#FFFFFF'},
        'word-focus':  {'font': 'Anton', 'color': '#FF9500', 'outline': '#000000'},
    }

    for name in preset_names:
        try:
            json_path = os.path.join(preset_dir, name, 'pycaps.template.json')
            
            template_json = {}
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    template_json = json.load(f)
            
            css_path = os.path.join(preset_dir, name, 'styles.css')
            css_content = ""
            if os.path.exists(css_path):
                with open(css_path, 'r', encoding='utf-8') as f:
                    css_content = f.read()
            
            layout = template_json.get('layout', {})
            style = PRESET_STYLES.get(name, PRESET_STYLES['default'])
            
            presets_data.append({
                'id': name,
                'name': name.replace('-', ' ').title(),
                'config': {
                    'fontName': layout.get('font_family', style['font']),
                    'fontSize': layout.get('font_size', 120),
                    'primaryColor': layout.get('primary_color', style['color']),
                    'outlineColor': layout.get('secondary_color', style['outline']),
                    'verticalMargin': layout.get('vertical_margin', 400),
                    'css': css_content
                }
            })
        except Exception:
            presets_data.append({'id': name, 'name': name.replace('-', ' ').title(), 'config': {}})
            
    return {'presets': presets_data}


@router.post('/regenerate/{job_id}')
async def regenerate_clip(job_id: str, data: RegenerateRequest):
    """Regenerate metadata for a specific clip."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')

    filename = data.filename

    json_path = None
    if is_new_layout(job_dir):
        for clip_folder in sorted(os.listdir(os.path.join(job_dir, 'clips'))):
            meta_path = os.path.join(job_dir, 'clips', clip_folder, 'meta.json')
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    m = json.load(f)
                    if m.get('filename') == filename:
                        json_path = meta_path
                        break
    if not json_path:
        json_path = os.path.join(job_dir, 'output', filename.replace('.mp4', '.json'))
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail='Clip metadata not found')

    with open(json_path, 'r', encoding='utf-8') as f:
        old_metadata = json.load(f)

    from core.analyzer import regenerate_clip_metadata, parse_srt, timestamp_to_seconds as a_ts
    
    subtitle_path = os.path.join(job_dir, 'subtitles.srt')
    if not os.path.exists(subtitle_path):
        raise HTTPException(status_code=400, detail='Original subtitles not found for context.')

    transcript = parse_srt(subtitle_path)
    lines = transcript.split('\n')
    
    start_sec = a_ts(old_metadata.get('start_time', '00:00:00'))
    end_sec = a_ts(old_metadata.get('end_time', '00:00:00'))
    
    snippet_lines = []
    for line in lines:
        match = re.match(r'\[(.*?)\] (.*)', line)
        if match:
            ts_str, text = match.groups()
            ts_sec = a_ts(ts_str)
            if start_sec <= ts_sec <= end_sec + 5:
                snippet_lines.append(text)
                
    snippet_text = " ".join(snippet_lines)
    if not snippet_text:
        raise HTTPException(status_code=400, detail='Could not extract transcript segment.')

    try:
        session_path = os.path.join(job_dir, 'session.json')
        session_config = {}
        if os.path.exists(session_path):
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                session_config = session_data.get('config', {})

        new_metadata = regenerate_clip_metadata(snippet_text, old_metadata, session_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(new_metadata, f, indent=2, ensure_ascii=False)

    return new_metadata


@router.get('/auto_track/{job_id}')
async def auto_track_frame(job_id: str, timestamp: float = Query(0), clip_index: int = Query(0)):
    """On-demand AI face tracking for a specific frame."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')
        
    clip_dir = get_clip_dir(job_dir, clip_index)
    
    clip_path = os.path.join(clip_dir, 'segments', f'clip_{clip_index+1:02d}_raw.mp4')
    
    if not os.path.exists(clip_path):
        clip_path = os.path.join(clip_dir, 'raw_clip.mp4')
        if not os.path.exists(clip_path):
            clip_path = os.path.join(job_dir, 'output', f'clip_{clip_index:03d}_raw.mp4')
            if not os.path.exists(clip_path):
                # Fallback to source video (same approach as detect_scenes)
                clip_path = os.path.join(job_dir, 'source.mp4')
                if not os.path.exists(clip_path):
                    for f in os.listdir(job_dir):
                        if f.endswith('.mp4') and not os.path.isdir(os.path.join(job_dir, f)):
                            clip_path = os.path.join(job_dir, f)
                            break
                if not os.path.exists(clip_path):
                    raise HTTPException(status_code=404, detail='Raw clip or source video not found')
            
    try:
        from core.reframer import get_face_center_x
        meta_path = os.path.join(clip_dir, 'meta.json')
        clip_origin = 0
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                clip_origin = timestamp_to_seconds(meta.get('start_time', '00:00:00'))
                
        local_timestamp = max(0, timestamp - clip_origin)
        logger.info(f"[AutoTrack] clip_path={clip_path}, exists={os.path.exists(clip_path)}, timestamp={timestamp}, clip_origin={clip_origin}, local_ts={local_timestamp}")
        
        crop_x = get_face_center_x(clip_path, local_timestamp)
        return {'crop_x': crop_x}
    except Exception as e:
        import traceback
        logger.error(f"[AutoTrack] Error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/detect_scenes/{job_id}')
async def detect_scenes_endpoint(job_id: str, start: float = Query(0), end: float = Query(0)):
    """Detect scenes in a specific range of the source video."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')
    source_path = os.path.join(job_dir, 'source.mp4')
    
    if not os.path.exists(source_path):
        for f in os.listdir(job_dir):
            if f.endswith('.mp4') and not os.path.isdir(os.path.join(job_dir, f)):
                source_path = os.path.join(job_dir, f)
                break

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail='Source video not found')

    import cv2
    import numpy as np

    async def generate():
        try:
            cap = cv2.VideoCapture(source_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            
            start_frame = int(start * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            end_frame = int(end * fps) if end > 0 else total_frames
            end_frame = min(end_frame, total_frames)
            
            duration_frames = end_frame - start_frame
            if duration_frames <= 0:
                duration_frames = 1

            cuts = []
            prev_frame = None
            
            for i in range(duration_frames):
                ret, frame = cap.read()
                if not ret: break
                
                frame_idx = start_frame + i
                
                if i % 100 == 0:
                    yield f"data: {json.dumps({'progress': int((i / duration_frames) * 100)})}\n\n"
                
                frame_small = cv2.resize(frame, (128, 72))
                gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
                if prev_frame is not None:
                    if np.mean(cv2.absdiff(gray, prev_frame)) > 25.0:
                        cuts.append(round(frame_idx/fps, 3))
                prev_frame = gray
            
            cap.release()
            yield f"data: {json.dumps({'cuts': cuts})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type='text/event-stream')
