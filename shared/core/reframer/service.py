import os
import cv2
from .tracking import (
    _track_with_segments, 
    _track_with_override, 
    _track_with_mediapipe, 
    _track_with_opencv
)
from .render_ffmpeg import _apply_crop_ffmpeg
from .render_dynamic import _apply_crop

def reframe_clip(clip_path, output_path, mode='opencv', progress_callback=None, 
                 clip_index=0, total_clips=1, custom_crop_x=None, segments=None, 
                 aspect_ratio='9:16', auto_background_enabled=True,
                 start_time=None, end_time=None):
    """
    Convert a 16:9 clip to a target aspect ratio with face tracking.
    Main entry point orchestrator.
    """
    # Parse target aspect ratio
    try:
        parts = [float(x) for x in aspect_ratio.split(':')]
        target_ratio = parts[0] / parts[1]
    except Exception:
        target_ratio = 9/16  # Default fallback
        
    # Calculate frame range
    cap_temp = cv2.VideoCapture(clip_path)
    fps = cap_temp.get(cv2.CAP_PROP_FPS) or 30.0
    total_source_frames = int(cap_temp.get(cv2.CAP_PROP_FRAME_COUNT))
    cap_temp.release()

    start_frame = int(start_time * fps) if start_time is not None else 0
    end_frame = int(end_time * fps) if end_time is not None else total_source_frames
    
    # Clip to source limits
    start_frame = max(0, min(start_frame, total_source_frames - 1))
    end_frame = max(start_frame + 1, min(end_frame, total_source_frames))

    if segments:
        crop_positions = _track_with_segments(clip_path, segments, target_ratio, start_frame, end_frame)
    elif custom_crop_x is not None:
        crop_positions = _track_with_override(clip_path, custom_crop_x, target_ratio, start_frame, end_frame)
    elif mode == 'mediapipe' or mode == 'yolo':
        crop_positions = _track_with_mediapipe(clip_path, target_ratio, start_frame, end_frame)
    else:
        crop_positions = _track_with_opencv(clip_path, target_ratio, start_frame, end_frame)

    # --- OPTIMIZATION: Check if positions are static ---
    is_static = False
    if len(crop_positions) > 0:
        first = crop_positions[0]
        is_static = all(
            p.get('x') == first.get('x') and 
            p.get('y', 0) == first.get('y', 0) and 
            p.get('w') == first.get('w') and 
            p.get('h', first.get('h')) == first.get('h', first.get('h'))
            for p in crop_positions
        )

    if progress_callback:
        base = 40 + int((clip_index / total_clips) * 10)
        progress_callback('reframe', f'Reframing clip {clip_index+1}/{total_clips}...', base)
    else:
        base = 40

    if is_static:
        print(f"[Reframer] Static framing detected. Using Pure FFmpeg Fast-Path.")
        _apply_crop_ffmpeg(clip_path, output_path, crop_positions, target_ratio,
                           start_frame=start_frame, end_frame=end_frame,
                           auto_background_enabled=auto_background_enabled)
    else:
        _apply_crop(clip_path, output_path, crop_positions, target_ratio, progress_callback, base, 
                    auto_background_enabled=auto_background_enabled, 
                    start_frame=start_frame, end_frame=end_frame)
