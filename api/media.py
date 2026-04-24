"""
ClipperApp — Media Router (FastAPI)
Handles: video streaming, downloads, thumbnails, export files, cookies.
"""

import os
import json
import subprocess
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from api import resolve_job_dir, get_clip_dir, is_new_layout, logger

router = APIRouter(prefix="/api", tags=["media"])


def _find_clip_file(job_dir, filename):
    """Search for a clip file in new layout then legacy."""
    if is_new_layout(job_dir):
        clips_root = os.path.join(job_dir, 'clips')
        for clip_folder in os.listdir(clips_root):
            for sub in ['exports', 'segments', '']:
                candidate = os.path.join(clips_root, clip_folder, sub, filename) if sub else os.path.join(clips_root, clip_folder, filename)
                if os.path.exists(candidate):
                    return candidate
    legacy = os.path.join(job_dir, 'output', filename)
    if os.path.exists(legacy):
        return legacy
    return None


@router.get('/preview_source/{job_id}')
async def preview_source(job_id: str):
    """Stream the original downloaded source video for the editor."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Source video not found')
    source_path = os.path.join(job_dir, 'source.mp4')
    if not os.path.exists(source_path):
        for f in os.listdir(job_dir):
            if f.endswith('.mp4') and not os.path.isdir(os.path.join(job_dir, f)):
                source_path = os.path.join(job_dir, f)
                break
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail='Source video not found')
    return FileResponse(
        source_path,
        media_type='video/mp4',
        headers={"Content-Disposition": "inline"}
    )


@router.get('/download/{job_id}/{filename}')
async def download_clip(job_id: str, filename: str):
    """Download a clip file."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='File not found')
    clip_path = _find_clip_file(job_dir, filename)
    if not clip_path:
        raise HTTPException(status_code=404, detail='File not found')
    return FileResponse(
        clip_path,
        media_type='video/mp4',
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get('/preview/{job_id}/{filename}')
async def preview_clip(job_id: str, filename: str):
    """Stream a clip for preview."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='File not found')
    clip_path = _find_clip_file(job_dir, filename)
    if not clip_path:
        raise HTTPException(status_code=404, detail='File not found')
    return FileResponse(
        clip_path,
        media_type='video/mp4',
        headers={"Content-Disposition": "inline"}
    )


@router.get('/thumbnail/{job_id}/{clip_index}')
async def get_thumbnail(job_id: str, clip_index: int):
    """Generate and serve a thumbnail for a clip."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Project not found')

    clip_dir = get_clip_dir(job_dir, clip_index)
    thumb_path = os.path.join(clip_dir, 'thumb.jpg')

    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type='image/jpeg')

    source_path = os.path.join(job_dir, 'source.mp4')
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail='Source video not found')

    meta_path = os.path.join(clip_dir, 'meta.json')
    timestamp = '00:00:02'
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            start = meta.get('start_time', '00:00:00')
            parts = [float(x) for x in start.split(':')]
            secs = parts[0]*3600 + parts[1]*60 + parts[2] + 2
            h, m = divmod(int(secs), 3600)
            m, s = divmod(m, 60)
            timestamp = f'{h:02d}:{m:02d}:{s:02d}'
        except Exception:
            pass

    cmd = [
        'ffmpeg', '-y',
        '-ss', timestamp,
        '-i', source_path,
        '-vframes', '1',
        '-q:v', '3',
        '-vf', 'scale=480:-1',
        thumb_path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass

    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type='image/jpeg')
    raise HTTPException(status_code=500, detail='Failed to generate thumbnail')


@router.delete('/export/{job_id}/{filename}')
async def delete_export(job_id: str, filename: str):
    """Delete a specific exported video file."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found')

    # Security: sanitize filename
    from pathlib import PurePosixPath
    safe_name = PurePosixPath(filename).name
    if not safe_name or not safe_name.endswith('.mp4'):
        raise HTTPException(status_code=400, detail='Invalid filename')

    clips_root = os.path.join(job_dir, 'clips')
    if os.path.isdir(clips_root):
        for clip_folder in os.listdir(clips_root):
            export_path = os.path.join(clips_root, clip_folder, 'exports', safe_name)
            if os.path.exists(export_path):
                try:
                    os.remove(export_path)
                    print(f"[DELETE] Removed export: {export_path}")
                    return {'status': 'deleted', 'filename': safe_name}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f'Failed to delete: {str(e)}')

    raise HTTPException(status_code=404, detail='Export file not found')


@router.post('/upload-cookies')
async def upload_cookies(file: UploadFile = File(...)):
    """Upload cookies.txt for yt-dlp authentication."""
    if not file.filename:
        raise HTTPException(status_code=400, detail='No file selected')
    cookies_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')
    content = await file.read()
    with open(cookies_path, 'wb') as f:
        f.write(content)
    return {'message': 'cookies.txt uploaded successfully!', 'path': cookies_path}
