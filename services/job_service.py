import os
import json
from sqlmodel import Session
from db import crud
from db.database import engine
from core.pipeline import Pipeline

def start_job(job_id: str, job_dir: str, config: dict, progress_callback: callable):
    """Business logic for starting a full clipping job."""
    with Session(engine) as session:
        crud.update_job_status(session, job_id, 'processing')
        try:
            pipeline = Pipeline(job_dir, config, progress_callback)
            clips = pipeline.run()
            crud.update_job_status(session, job_id, 'completed')
            crud.update_job_clips(session, job_id, clips)
            progress_callback('done', f'Completed! Generated {len(clips)} clips.', 100)
        except Exception as e:
            crud.update_job_status(session, job_id, 'error', error=str(e))
            progress_callback('error', str(e), 0)

def start_export(
    export_id: str, 
    job_dir: str, 
    metadata: dict, 
    clip_index: int, 
    export_data: any, 
    config: dict, 
    json_path: str,
    progress_callback: callable
):
    """Business logic for exporting a single clip."""
    with Session(engine) as session:
        crud.update_job_status(session, export_id, 'processing')
        try:
            pipeline = Pipeline(job_dir, config, progress_callback)
            
            final_data = pipeline.export_single_clip(
                metadata, 
                custom_start=export_data.custom_start, 
                custom_end=export_data.custom_end, 
                custom_crop_x=export_data.custom_crop_x,
                segments=export_data.segments,
                clip_index=clip_index,
                aspect_ratio=export_data.aspect_ratio
            )
            
            # Master sync to session.json
            session_path = os.path.join(job_dir, 'session.json')
            if os.path.exists(session_path):
                with open(session_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                clips = session_data.get('clips', [])
                if clip_index is not None and int(clip_index) < len(clips):
                    clips[int(clip_index)] = final_data
                    with open(session_path, 'w', encoding='utf-8') as f:
                        json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            # Update the specific meta.json for the clip
            if json_path:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, indent=2, ensure_ascii=False)
            
            crud.update_job_status(session, export_id, 'completed')
            crud.update_job_clips(session, export_id, [final_data])
            progress_callback('done', 'Export finished.', 100)
            
        except Exception as e:
            crud.update_job_status(session, export_id, 'error', error=str(e))
            progress_callback('error', str(e), 0)
