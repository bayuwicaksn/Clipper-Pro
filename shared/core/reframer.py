"""
Reframer â€” Convert 16:9 landscape to 9:16 portrait with face/speaker tracking
GPU-accelerated encoding when NVIDIA GPU is available.
"""

import os
import subprocess
import cv2
import numpy as np
import math
from .gpu_utils import get_ffmpeg_video_encode_args, has_nvidia_gpu
try:
    import mediapipe.python.solutions.face_mesh as mp_face_mesh
    import mediapipe.python.solutions.drawing_utils as mp_drawing
    import mediapipe.python.solutions.drawing_styles as mp_drawing_styles
except ImportError:
    try:
        from mediapipe.solutions import face_mesh as mp_face_mesh
        from mediapipe.solutions import drawing_utils as mp_drawing
        from mediapipe.solutions import drawing_styles as mp_drawing_styles
    except ImportError:
        import mediapipe as mp
        mp_face_mesh = getattr(mp.solutions, 'face_mesh', None)
        mp_drawing = getattr(mp.solutions, 'drawing_utils', None)
        mp_drawing_styles = getattr(mp.solutions, 'drawing_styles', None)

# Note: OpenCV hardware decoding (d3d11va/cuvid) is intentionally DISABLED.
# On GTX 1050 Ti (4GB VRAM), it conflicts with YOLO + FFmpeg encoding.
# CPU decoding for OpenCV is fast enough and keeps VRAM free.

def _get_mouth_aspect_ratio(landmarks, width, height):
    """
    Calculate Mouth Aspect Ratio (MAR) to determine how wide the mouth is open.
    Using standard MediaPipe FaceMesh inner lip indices:
    Upper inner lip: 13, Lower inner lip: 14
    Left mouth corner: 61, Right mouth corner: 291
    """
    p13 = landmarks[13]
    p14 = landmarks[14]
    p61 = landmarks[61]
    p291 = landmarks[291]
    
    # Calculate vertical distance
    v_dist = math.hypot((p14.x - p13.x) * width, (p14.y - p13.y) * height)
    # Calculate horizontal distance
    h_dist = math.hypot((p291.x - p61.x) * width, (p291.y - p61.y) * height)
    
    if h_dist == 0:
        return 0
    return v_dist / h_dist

def _find_face_center(landmarks, width):
    """Find the approximate horizontal center of the face."""
    x_coords = [lm.x for lm in landmarks]
    cx = (min(x_coords) + max(x_coords)) / 2.0
    return int(cx * width)

def get_face_center_x(clip_path, timestamp_sec):
    """
    Seeks to specific timestamp in a video and returns the face center ratio (0.0 to 1.0).
    If no face is found, returns 0.5 (center).
    """
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened(): 
        return 0.5
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0: fps = 30
    
    target_frame = int(timestamp_sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    
    ret, frame = cap.read()
    if not ret:
        cap.release()
        return 0.5
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5
    ) as face_mesh:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(frame_rgb)
        
        if results.multi_face_landmarks:
            face_landmarks = results.multi_face_landmarks[0]
            cx_px = _find_face_center(face_landmarks.landmark, width)
            cap.release()
            return cx_px / width
            
    cap.release()
    return 0.5

def reframe_clip(clip_path, output_path, mode='opencv', progress_callback=None, 
                 clip_index=0, total_clips=1, custom_crop_x=None, segments=None, 
                 aspect_ratio='9:16', auto_background_enabled=True,
                 start_time=None, end_time=None):
    """
    Convert a 16:9 clip to a target aspect ratio with face tracking.
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

    if progress_callback:
        base = 40 + int((clip_index / total_clips) * 10)
        progress_callback('reframe', f'Reframing clip {clip_index+1}/{total_clips}...', base)
    else:
        base = 40

    _apply_crop(clip_path, output_path, crop_positions, target_ratio, progress_callback, base, 
                auto_background_enabled=auto_background_enabled, 
                start_frame=start_frame, end_frame=end_frame)


def _track_with_override(clip_path, custom_crop_x_pct, target_ratio, start_frame, end_frame):
    """Static framing using a user-provided percentage override (0.0 to 1.0)"""
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened(): return []

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    crop_w = int(height * target_ratio)
    
    center_x = width * custom_crop_x_pct
    crop_x = int(center_x - (crop_w / 2))
    
    if crop_w > width:
        crop_x = (width - crop_w) // 2
    else:
        crop_x = max(0, min(crop_x, width - crop_w))
    
    positions = []
    for i in range(start_frame, end_frame):
        positions.append({'frame': i, 'x': crop_x, 'w': crop_w})
    
    cap.release()
    return positions


def _track_with_opencv(clip_path, target_ratio, start_frame, end_frame):
    """Fallback static tracking using OpenCV's Haar Cascade (Zero Movement)."""
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened(): return []

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # 1. Scan for the first face to lock camera
    locked_cx = width // 2
    for _ in range(int(fps * 2)): # Scan first 2 seconds
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(100, 100))
        if len(faces) > 0:
            fx, fy, fw, fh = faces[0]
            locked_cx = fx + fw // 2
            break
    
    # 2. Apply static lock
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    crop_w = int(height * target_ratio)
    if crop_w > width:
        crop_x = (width - crop_w) // 2
    else:
        crop_x = max(0, min(int(locked_cx) - crop_w // 2, width - crop_w))
    
    positions = []
    for i in range(start_frame, end_frame):
        positions.append({'frame': i, 'x': crop_x, 'w': crop_w})
    
    cap.release()
    return positions


def _track_with_segments(clip_path, segments, target_ratio, start_frame, end_frame):
    """
    Apply multiple crop positions over time based on segments.
    segments: list of {'start': seconds, 'end': seconds, 'crop_x': offset_pct, 'crop_y': offset_pct, 'crop_z': zoom}
    """
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened(): return []

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Offset segments to local clip time (clip starts at 0)
    clip_origin = min(seg['start'] for seg in segments)
    local_segments = []
    for seg in segments:
        local_segments.append({
            'start': seg['start'] - clip_origin,
            'end': seg['end'] - clip_origin,
            'crop_x': seg.get('crop_x', 0.5),
            'crop_y': seg.get('crop_y', 0.5),
            'crop_z': seg.get('crop_z', 1.0),
        })

    # --- FIX: SINKRONISASI BASE VIEWPORT ---
    # Di UI, Zoom 1.0 menyesuaikan lebar (width) untuk video 16:9 di container 9:16
    video_ratio = width / height
    if video_ratio > target_ratio:
        base_viewport_w = width
        base_viewport_h = width / target_ratio
    else:
        base_viewport_h = height
        base_viewport_w = height * target_ratio

    positions = []
    for i in range(start_frame, end_frame):
        ts = i / fps
        active_seg = None
        for seg in local_segments:
            if ts >= seg['start'] and ts <= seg['end']:
                active_seg = seg
                break
        
        if not active_seg:
            active_seg = local_segments[-1]
            
        zoom = active_seg['crop_z']
        
        # 1. Hitung dimensi kamera aktual yang diproyeksikan
        crop_w = int(base_viewport_w / zoom)
        crop_h = int(base_viewport_h / zoom)
        
        # 2. Titik tengah berdasarkan persentase UI
        center_x = width * active_seg['crop_x']
        center_y = height * active_seg['crop_y']
        
        # 3. Titik potong X dan Y (DIBIARKAN BISA NEGATIF)
        crop_x = int(center_x - (crop_w / 2))
        crop_y = int(center_y - (crop_h / 2))
        
        positions.append({
            'frame': i, 
            'x': crop_x, 
            'y': crop_y,
            'w': crop_w,
            'h': crop_h
        })

    cap.release()
    return positions


def _track_with_mediapipe(clip_path, target_ratio, start_frame, end_frame):
    """
    Reframes a 16:9 video to a target aspect ratio.
    Uses MediaPipe FaceMesh to track faces and locks center.
    """
    print(f"\n[Reframer] Starting Active Speaker tracking for: {os.path.basename(clip_path)}")
    
    cap = cv2.VideoCapture(clip_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    crop_w = int(height * target_ratio)
    if crop_w > width:
        crop_w = width

    positions = []
    
    # --- Steady-Cam Tracking Parameters ---
    current_cx_float = float(width / 2)
    target_cx = width // 2
    
    dead_zone_px = width * 0.25      # 25% tolerance
    smoothing_alpha = 0.05           # Cinematic smooth glide
    
    # --- Active Speaker Logic Parameters ---
    speaker_mar_history = {}    # {face_id: [mar1, mar2, ...]}
    speaker_center_history = {} # {face_id: cx}
    active_speaker_id = None
    switch_cooldown = 0
    COOLDOWN_FRAMES = 24        
    HISTORY_LEN = 15            
    
    # 1. Cari satu posisi terbaik (Pass Pertama)
    best_overall_cx = width // 2
    found_any_face = False
    
    with mp_face_mesh.FaceMesh(
        max_num_faces=3,
        refine_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:
        
        # Scan 2 detik pertama (atau seluruh video pendek) untuk cari posisi
        # Biasanya 2 detik cukup untuk menentukan di mana orangnya duduk
        scan_limit = int(fps * 2) 
        f_idx = 0
        while f_idx < scan_limit:
            ret, frame = cap.read()
            if not ret: break
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(frame_rgb)
            
            if results.multi_face_landmarks:
                # Ambil wajah paling dominan (terbesar/pertama)
                face_landmarks = results.multi_face_landmarks[0]
                best_overall_cx = _find_face_center(face_landmarks.landmark, width)
                found_any_face = True
                print(f"[Reframer] ðŸŽ¯ Found subject! Locking camera at CX: {best_overall_cx}")
                break # Ketemu satu posisi, langsung kunci dan keluar scan
            f_idx += 1
            
    # 2. Reset video to range start for preparation
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # 3. Isi semua frame dengan koordinat YANG SAMA (Diam total)
    total_frames = end_frame - start_frame
    print(f"[Reframer] Applying Super-Static Lock to all {total_frames} frames.")
    
    if crop_w > width:
        crop_x = (width - crop_w) // 2
    else:
        crop_x = max(0, min(int(best_overall_cx) - crop_w // 2, width - crop_w))
    
    for i in range(start_frame, end_frame):
        positions.append({'frame': i, 'x': crop_x, 'w': crop_w})

    cap.release()
    return positions


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
    # We pipe the RESIZED frame to FFmpeg because zoom means frame sizes vary per segment.
    # FFmpeg expects a constant rawvideo input size.
    cmd = [
        'ffmpeg', '-y',
        '-loglevel', 'error',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{out_w}x{out_h}',
        '-pix_fmt', 'bgr24',
        '-r', str(fps),
        '-i', '-',          # Input 0: stdin (cropped video stream)
        '-ss', str(start_frame / fps),
        '-i', clip_path,    # Input 1: original clip (for audio)
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

        # Dynamic crop based on x, y, w, h
        # Handle out-of-bounds coordinates to maintain exact crop aspect ratio
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
            bg = cv2.convertScaleAbs(bg, alpha=0.5, beta=0) # Dim the background
        else:
            bg = np.zeros((ch, cw, 3), dtype=np.uint8)
        
        canvas = bg
        if y1 < y2 and x1 < x2:
            canvas[cy1:cy2, cx1:cx2] = frame[y1:y2, x1:x2]
            
        resized = cv2.resize(canvas, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        
        # Write raw bytes directly to FFmpeg.
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
    
    # Wait for FFmpeg to finish encoding
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg encoding failed during reframe (return code: {process.returncode})")


def detect_scenes(video_path, threshold=25.0, progress_callback=None):
    """
    Detect scene changes in a video using frame-to-frame absolute difference.
    Returns a list of timestamps (seconds) where cuts occur.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0: fps = 30.0
    
    cuts = []
    prev_frame = None
    frame_idx = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if progress_callback:
        progress_callback(0)

    print(f"  [Scene Detection] Processing {total_frames} frames...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Downscale for faster processing
        frame_small = cv2.resize(frame, (128, 72))
        gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
        
        if prev_frame is not None:
            # Calculate absolute difference
            diff = cv2.absdiff(gray, prev_frame)
            score = np.mean(diff)
            
            if score > threshold:
                timestamp = frame_idx / fps
                cuts.append(round(timestamp, 3))
        
        prev_frame = gray
        frame_idx += 1
        
        if frame_idx % 100 == 0:
            if progress_callback:
                progress_callback(int((frame_idx / total_frames) * 100))
            if frame_idx % 300 == 0:
                print(f"  [Scene Detection] Progress: {int((frame_idx/total_frames)*100)}%")

    cap.release()
    print(f"  [Scene Detection] Completed. Found {len(cuts)} cuts.")
    return cuts
