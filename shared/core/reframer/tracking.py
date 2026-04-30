import os
import cv2
from .utils import _find_face_center

# MediaPipe Import Logic
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
        try:
            import mediapipe as mp
            solutions = getattr(mp, 'solutions', None)
            if solutions:
                mp_face_mesh = getattr(solutions, 'face_mesh', None)
                mp_drawing = getattr(solutions, 'drawing_utils', None)
                mp_drawing_styles = getattr(solutions, 'drawing_styles', None)
            else:
                mp_face_mesh = mp_drawing = mp_drawing_styles = None
        except ImportError:
            mp_face_mesh = mp_drawing = mp_drawing_styles = None

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
    
    if mp_face_mesh is None:
        cap.release()
        return 0.5

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

def _track_with_override(width, height, custom_crop_x_pct, target_ratio, start_frame, end_frame):
    """Static framing using a user-provided percentage override (0.0 to 1.0)"""
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
    """
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened(): return []

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

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

    # SINKRONISASI BASE VIEWPORT
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
        crop_w = int(base_viewport_w / zoom)
        crop_h = int(base_viewport_h / zoom)
        center_x = width * active_seg['crop_x']
        center_y = height * active_seg['crop_y']
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
    best_overall_cx = width // 2
    
    if mp_face_mesh is not None:
        with mp_face_mesh.FaceMesh(
            max_num_faces=3,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            
            scan_limit = int(fps * 2) 
            f_idx = 0
            while f_idx < scan_limit:
                ret, frame = cap.read()
                if not ret: break
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(frame_rgb)
                
                if results.multi_face_landmarks:
                    face_landmarks = results.multi_face_landmarks[0]
                    best_overall_cx = _find_face_center(face_landmarks.landmark, width)
                    print(f"[Reframer] ðŸŽ¯ Found subject! Locking camera at CX: {best_overall_cx}")
                    break
                f_idx += 1
            
    # Apply static lock
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
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
