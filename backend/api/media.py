"""
ClipperApp â€” Media Router (FastAPI)
Handles: video streaming, downloads, thumbnails, export files, cookies.
"""

import os
import json
import subprocess
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse

from . import resolve_job_dir, get_clip_dir, is_new_layout, logger

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


@router.post('/caption_composition/{job_id}')
async def get_caption_composition(job_id: str, request: Request):
    """
    Generate and serve a HyperFrames caption composition HTML.
    Accepts transcript and caption settings in POST body.
    Returns the generated HTML composition.
    """
    from fastapi.responses import HTMLResponse
    from shared.core.caption_composition import generate_caption_composition
    import tempfile

    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Project not found')

    try:
        data = await request.json()
        transcript = data.get('transcript', [])
        caption_settings = data.get('caption_settings', {})
        aspect_ratio = data.get('aspect_ratio', '9:16')

        if not transcript:
            return HTMLResponse('<html><body></body></html>', status_code=200)

        # Parse dimensions from aspect ratio
        try:
            parts = [float(x) for x in aspect_ratio.split(':')]
            if parts[0] < parts[1]:  # Portrait
                video_w, video_h = 1080, 1920
            elif parts[0] > parts[1]:  # Landscape
                video_w, video_h = 1920, 1080
            else:  # Square
                video_w, video_h = 1080, 1080
        except Exception:
            video_w, video_h = 1080, 1920

        # Convert transcript words to the format expected by the generator
        words = []
        for w in transcript:
            text = w.get('word', w.get('text', '')).strip()
            # Handle both 'start' (seconds) and 'startMs' (ms)
            start = w.get('start')
            if start is None:
                start = w.get('startMs', 0) / 1000.0
            
            end = w.get('end')
            if end is None:
                end = w.get('endMs', 0) / 1000.0
                
            if text and end > 0:
                words.append({'word': text, 'start': float(start), 'end': float(end)})

        if not words:
            return HTMLResponse('<html><body></body></html>', status_code=200)

        # Use the source video URL for the background
        video_src = f'/api/preview_source/{job_id}'

        # Generate to a unique temp file to avoid Windows file locks
        import tempfile
        clip_dir = get_clip_dir(job_dir, 0)
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, dir=clip_dir) as tf:
            composition_path = tf.name
        
        # Ensure coordinates are floats
        c_x = float(caption_settings.get('captionX') or 0.5)
        c_y = float(caption_settings.get('captionY') or 0.82)
        
        generate_caption_composition(
            video_src=video_src,
            output_html=composition_path,
            words=words,
            settings={**caption_settings, 'captionX': c_x, 'captionY': c_y},
            video_w=video_w,
            video_h=video_h,
            preview_mode=True,
        )

        if not os.path.exists(composition_path):
            raise HTTPException(status_code=500, detail='Failed to generate composition')

        # We want to delete the file after sending, but FileResponse needs it to exist
        # FastAPI BackgroundTasks can handle this
        from fastapi import BackgroundTasks
        background_tasks = BackgroundTasks()
        background_tasks.add_task(os.remove, composition_path)

        return FileResponse(
            composition_path, 
            media_type='text/html',
            background=background_tasks
        )
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"[Caption] Error generating composition for job {job_id}:\n{error_msg}")
        logger.error(f"[Caption] Error generating composition for job {job_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=str(e))


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
    legacy_root = os.path.join(job_dir, 'output')

    # Try modern layout
    if os.path.isdir(clips_root):
        for clip_folder in os.listdir(clips_root):
            export_path = os.path.join(clips_root, clip_folder, 'exports', safe_name)
            if os.path.exists(export_path):
                try:
                    os.remove(export_path)
                    print(f"[DELETE] Removed export (modern): {export_path}")
                    return {'status': 'deleted', 'filename': safe_name}
                except PermissionError:
                    raise HTTPException(status_code=423, detail='File is currently in use and cannot be deleted')
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f'Failed to delete: {str(e)}')

    # Try legacy layout
    if os.path.isdir(legacy_root):
        export_path = os.path.join(legacy_root, safe_name)
        if os.path.exists(export_path):
            try:
                os.remove(export_path)
                print(f"[DELETE] Removed export (legacy): {export_path}")
                return {'status': 'deleted', 'filename': safe_name}
            except PermissionError:
                raise HTTPException(status_code=423, detail='File is currently in use and cannot be deleted')
            except Exception as e:
                raise HTTPException(status_code=500, detail=f'Failed to delete: {str(e)}')

    raise HTTPException(status_code=404, detail='Export file not found')


