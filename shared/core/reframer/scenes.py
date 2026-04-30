import cv2
import numpy as np

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
