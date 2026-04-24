"""
Clipper — FFmpeg-based video segment extraction (GPU-accelerated encoding)
Decoding stays on CPU for stability on low-VRAM GPUs (e.g. GTX 1050 Ti 4GB).
"""

import os
import subprocess
from core.gpu_utils import get_ffmpeg_video_encode_args


def clip_segments(video_path, highlights, output_dir, progress_callback=None):
    """
    Cut video segments based on highlight timestamps using FFmpeg.
    
    Args:
        video_path: Path to source video
        highlights: List of highlight dicts with start_time, end_time
        output_dir: Directory to save clips
        progress_callback: Optional callback(step, message, progress)
    
    Returns:
        List of clip file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    clip_paths = []
    total = len(highlights)

    for i, h in enumerate(highlights):
        if progress_callback:
            pct = 30 + int((i / total) * 10)  # 30-40%
            progress_callback('clip', f'Clipping segment {i+1}/{total}...', pct)

        clip_filename = f'clip_{i+1:02d}_raw.mp4'
        clip_path = os.path.join(output_dir, clip_filename)

        start = h['start_time']
        end = h['end_time']
        
        # Calculate duration for reliable cutting
        start_parts = [float(x) for x in start.split(':')]
        end_parts = [float(x) for x in end.split(':')]
        start_sec = start_parts[0]*3600 + start_parts[1]*60 + start_parts[2]
        end_sec = end_parts[0]*3600 + end_parts[1]*60 + end_parts[2]
        duration = str(end_sec - start_sec)

        # GPU for encoding only; NO hwaccel decoding (saves VRAM for YOLO later)
        video_enc = get_ffmpeg_video_encode_args()

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-ss', start,
            '-t', duration,
        ] + video_enc + [
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-avoid_negative_ts', 'make_zero',
            clip_path
        ]

        # CRITICAL: Do NOT use capture_output=True on large videos!
        # It buffers ALL of FFmpeg's output into RAM, causing MemoryError.
        # Instead: discard stdout, only capture stderr (limited).
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        _, stderr_data = process.communicate()

        if process.returncode != 0:
            err_tail = stderr_data.decode('utf-8', errors='replace')[-300:] if stderr_data else 'unknown'
            print(f'Warning: Failed to clip segment {i+1}: {err_tail}')
            continue

        if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
            clip_paths.append(clip_path)

    if progress_callback:
        progress_callback('clip', f'Clipped {len(clip_paths)} segments!', 40)

    return clip_paths
