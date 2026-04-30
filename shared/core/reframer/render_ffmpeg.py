import subprocess
import cv2
from ..gpu_utils import get_ffmpeg_video_encode_args, get_ffmpeg_hwaccel_input_args

def _apply_crop_ffmpeg(clip_path, output_path, positions, target_ratio, width, height, fps,
                        start_frame=0, end_frame=0, auto_background_enabled=True):
    """
    Pure FFmpeg crop â€” significantly faster than Python frame loop.
    Optimized for static positions.
    """
    video_enc = get_ffmpeg_video_encode_args()
    hwaccel_args = get_ffmpeg_hwaccel_input_args()
    
    # Use first position for static crop (guaranteed static by caller)
    pos = positions[0] if positions else {'x': 0, 'y': 0, 'w': 1080, 'h': 1920}
    
    # --- CLAMPING: Ensure coordinates are within video bounds for FFmpeg ---
    cw = min(int(pos.get('w', 1080)), width)
    ch = min(int(pos.get('h', 1920)), height)
    crop_x = max(0, min(int(pos.get('x', 0)), width - cw))
    crop_y = max(0, min(int(pos.get('y', 0)), height - ch))
    
    # Output resolution logic
    if target_ratio < 1: # Portrait
        out_w, out_h = 1080, 1920
    elif target_ratio > 1: # Landscape
        out_w, out_h = 1920, 1080
    else: # Square
        out_w, out_h = 1080, 1080
    
    start_sec = start_frame / fps
    duration = (end_frame - start_frame) / fps
    
    if auto_background_enabled:
        # Blurred background logic with FFmpeg
        vf = (
            f"split=2[main][bg];"
            f"[bg]crop={cw}:{ch}:{crop_x}:{crop_y},scale={out_w}:{out_h},boxblur=20:10,eq=brightness=-0.3[blurred];"
            f"[main]crop={cw}:{ch}:{crop_x}:{crop_y},scale={out_w}:{out_h}[cropped];"
            f"[blurred][cropped]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        vf = f"crop={cw}:{ch}:{crop_x}:{crop_y},scale={out_w}:{out_h}"
    
    cmd = [
        'ffmpeg', '-y',
    ] + hwaccel_args + [
        '-ss', f"{start_sec:.4f}",
        '-t', f"{duration:.4f}",
        '-i', clip_path,
        '-vf', vf,
    ] + video_enc + [
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    
    print(f"[Reframer] Starting Fast-Path (Pure FFmpeg) Encode: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
