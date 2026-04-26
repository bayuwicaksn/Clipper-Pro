"""
ClipperApp — Projects Router (FastAPI)
Handles: project listing, deletion, clip metadata retrieval.
"""

import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session

from api import (
    WORKSPACE, resolve_job_dir, get_clip_dir,
    is_new_layout, robust_rmtree, logger
)
from db import crud
from db.database import get_session
from api.schemas import ProjectResponse

router = APIRouter(prefix="/api", tags=["projects"])


@router.get('/projects', response_model=List[ProjectResponse])
async def list_projects(session: Session = Depends(get_session)):
    """List all previously processed projects in the workspace."""
    projects = []
    if not os.path.exists(WORKSPACE):
        return []

    for folder_name in os.listdir(WORKSPACE):
        job_dir = os.path.join(WORKSPACE, folder_name)
        if not os.path.isdir(job_dir):
            continue

        if '--' in folder_name:
            slug_part = folder_name.rsplit('--', 1)[0]
            actual_id = folder_name.rsplit('--', 1)[1]
        else:
            slug_part = ''
            actual_id = folder_name

        session_path = os.path.join(job_dir, 'session.json')
        if not os.path.exists(session_path):
            session_path = os.path.join(job_dir, 'output', 'session.json')

        if os.path.exists(session_path):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    created_at = session_data.get('created_at', '')
                    job = crud.get_job(session, actual_id)
                    status = job.status if job else 'completed'
                    
                    projects.append({
                        'id': actual_id,
                        'slug': slug_part,
                        'status': status,
                        'title': session_data.get('video', {}).get('title', 'Untitled Project'),
                        'thumbnail': session_data.get('video', {}).get('thumbnail', ''),
                        'video_duration': session_data.get('video', {}).get('duration', 0),
                        'created_at': created_at,
                        'created_timestamp': datetime.fromisoformat(created_at).timestamp() if created_at else 0,
                        'clip_count': len(session_data.get('clips', [])),
                        'video_url': session_data.get('config', {}).get('url', '')
                    })
            except Exception:
                continue
        else:
            info_path = os.path.join(job_dir, 'source.info.json')
            if os.path.exists(info_path):
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        info_data = json.load(f)
                        job = crud.get_job(session, actual_id)
                        status = job.status if job else 'completed'

                        projects.append({
                            'id': actual_id,
                            'slug': slug_part,
                            'status': status,
                            'title': info_data.get('title', 'Untitled Project'),
                            'thumbnail': info_data.get('thumbnail', ''),
                            'video_duration': info_data.get('duration', 0),
                            'created_at': datetime.fromtimestamp(os.path.getctime(job_dir)).isoformat(),
                            'created_timestamp': os.path.getctime(job_dir),
                            'clip_count': 0,
                            'video_url': info_data.get('webpage_url', '')
                        })
                except Exception:
                    continue

    projects.sort(key=lambda x: x['created_at'], reverse=True)
    return projects


@router.delete('/projects/{job_id}')
async def delete_project(job_id: str, session: Session = Depends(get_session)):
    """Delete a project and all its files from the workspace."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Project not found')
        
    job = crud.get_job(session, job_id)
    if job and job.status == 'processing':
        raise HTTPException(status_code=400, detail='Cannot delete project while it is currently rendering.')
        
    try:
        robust_rmtree(job_dir)
        crud.delete_job(session, job_id)
        return {'status': 'deleted', 'id': job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/clips/{job_id}')
async def list_clips(job_id: str):
    """List clips for a job, recovering from session.json if needed."""
    job_dir = resolve_job_dir(job_id)
    if not job_dir:
        raise HTTPException(status_code=404, detail='Job not found or clips missing')

    session_path = os.path.join(job_dir, 'session.json')
    if not os.path.exists(session_path):
        session_path = os.path.join(job_dir, 'output', 'session.json')
        
    if os.path.exists(session_path):
        try:
            with open(session_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            clips = session_data.get('clips', [])
            
            for i, clip in enumerate(clips):
                idx = clip.get('clip_index', i)
                clip_path = get_clip_dir(job_dir, idx)
                exports_dir = os.path.join(clip_path, 'exports')
                
                exported_files = []
                if os.path.exists(exports_dir):
                    exported_files = sorted([f for f in os.listdir(exports_dir) if f.endswith('.mp4')], reverse=True)
                
                clip['exported'] = len(exported_files) > 0
                clip['exports'] = []
                for j, ef in enumerate(exported_files):
                    ver_label = f'Ver {len(exported_files) - j}' if len(exported_files) > 1 else None
                    clip['exports'].append({'filename': ef, 'version_label': ver_label})
                
                if exported_files:
                    clip['filename'] = exported_files[0]
                
                dur = clip.get('duration_seconds', 0)
                clip['duration_display'] = f'{int(dur // 60)}:{int(dur % 60):02d}'
                
            return {'clips': clips}
        except Exception as e:
            print(f"[GET_CLIPS] Error reading session.json: {e}")

    if is_new_layout(job_dir):
        pass

    print(f"[EXPORT] ERROR: Final fallback failed. No meta.json found! json_path={session_path}")
    raise HTTPException(status_code=404, detail='Clip metadata not found (checked all layouts)')
