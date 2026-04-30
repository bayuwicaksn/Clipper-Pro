import subprocess
import cv2
import numpy as np
from ..gpu_utils import get_ffmpeg_video_encode_args

def _apply_crop(clip_path, output_path, positions, target_ratio, progress_callback=None, base_pct=40, auto_background_enabled=True, start_frame=0, end_frame=0):
    """Apply crop positions using OpenCV for processing, GPU FFmpeg for encoding."""
    video_enc = get_ffmpeg_video_encode_args()

    cap = cv2.VideoCapture(clip_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = end_frame - start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    if not positions:
        print("[Reframer] No positions provided, using default center crop.")
        # Fallback: center crop with FFmpeg
        crop_w = int(height * target_ratio)
        crop_x = (width - crop_w) // 2
        
        # Calculate target resolution
        if target_ratio < 1: # Portrait-ish
            out_w, out_h = 1080, int(1080 / target_ratio)
        else: # Landscape-ish
            out_w, out_h = 1920, int(1920 / target_ratio)
            
        cmd = [
            'ffmpeg', '-y',
            '-i', clip_path,
            '-vf', f'crop={crop_w}:{height}:{crop_x}:0,scale={out_w}:{out_h}',
        ] + video_enc + [
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    # Final output resolution
    if target_ratio < 1: # Portrait
        out_w, out_h = 1080, 1920
    elif target_ratio > 1: # Landscape
        out_w, out_h = 1920, 1080
    else: # Square
        out_w, out_h = 1080, 1080
    
    # Start FFmpeg process
    cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'error',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{out_w}x{out_h}',
        '-pix_fmt', 'bgr24',
        '-r', str(fps),
        '-i', '-',          
        '-ss', str(start_frame / fps),
        '-i', clip_path,    
        '-map', '0:v',
        '-map', '1:a',
    ] + video_enc + [
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-shortest',
        output_path
    ]
    
    print(f"[Reframer] Starting GPU-Accelerated Encode: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frame_idx = 0
    while frame_idx < total_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx < len(positions):
            pos = positions[frame_idx]
            crop_x = pos.get('x', 0)
            crop_y = pos.get('y', 0)
            cw = pos.get('w', int(height * target_ratio))
            ch = pos.get('h', height)
        else:
            pos = positions[-1]
            crop_x = pos.get('x', 0)
            crop_y = pos.get('y', 0)
            cw = pos.get('w', int(height * target_ratio))
            ch = pos.get('h', height)

        y1 = max(0, crop_y)
        y2 = min(height, crop_y + ch)
        x1 = max(0, crop_x)
        x2 = min(width, crop_x + cw)
        
        cy1 = max(0, -crop_y)
        cy2 = cy1 + (y2 - y1)
        cx1 = max(0, -crop_x)
        cx2 = cx1 + (x2 - x1)
        
        if auto_background_enabled:
            bg = cv2.resize(frame, (cw, ch), interpolation=cv2.INTER_LINEAR)
            bg = cv2.GaussianBlur(bg, (99, 99), 30)
            bg = cv2.convertScaleAbs(bg, alpha=0.5, beta=0) 
        else:
            bg = np.zeros((ch, cw, 3), dtype=np.uint8)
        
        canvas = bg
        if y1 < y2 and x1 < x2:
            canvas[cy1:cy2, cx1:cx2] = frame[y1:y2, x1:x2]
            
        resized = cv2.resize(canvas, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        
        try:
            process.stdin.write(resized.tobytes())
        except BrokenPipeError:
            break
            
        frame_idx += 1
        
        if progress_callback and total_frames > 0 and frame_idx % int(fps) == 0:
            sub_pct = int((frame_idx / total_frames) * 10)
            progress_callback('reframe', f'Rendering frame {frame_idx}/{total_frames}...', base_pct + sub_pct)

    cap.release()
    process.stdin.close()
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg encoding failed during reframe (return code: {process.returncode})")
