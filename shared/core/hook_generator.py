"""
Hook Generator â€” TTS voiceover + text overlay intro scene
GPU-accelerated encoding when NVIDIA GPU is available.
"""

import os
import subprocess
import cv2
import numpy as np
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from .gpu_utils import get_ffmpeg_video_encode_args


def generate_hook(clip_path, hook_text, output_path, config=None, progress_callback=None, clip_index=0, total_clips=1):
    """
    Generate a hook intro scene and prepend it to the clip.
    
    Args:
        clip_path: Path to the reframed clip
        hook_text: Hook text to display and speak
        output_path: Path for final output with hook
        config: Dict with tts_voice, tts_speed, etc.
        progress_callback: Optional progress callback
    """
    config = config or {}
    tts_voice = config.get('tts_voice', 'alloy')
    
    if progress_callback:
        base = 50 + int((clip_index / total_clips) * 10)
        progress_callback('hook', f'Generating hook for clip {clip_index+1}/{total_clips}...', base)

    job_dir = os.path.dirname(output_path)
    hook_audio_path = os.path.join(job_dir, f'hook_audio_{clip_index}.mp3')
    hook_video_path = os.path.join(job_dir, f'hook_scene_{clip_index}.mp4')

    # 1. Generate TTS audio
    _generate_tts(hook_text, hook_audio_path, tts_voice)

    # 2. Get TTS audio duration
    tts_duration = _get_duration(hook_audio_path)
    if tts_duration <= 0:
        tts_duration = 3.0

    # 3. Create hook video scene (blurred first frame + text)
    _create_hook_scene(clip_path, hook_text, hook_video_path, hook_audio_path, tts_duration)

    # 4. Concatenate hook + clip
    _concat_videos(hook_video_path, clip_path, output_path)

    # Cleanup temps
    for f in [hook_audio_path, hook_video_path]:
        if os.path.exists(f):
            os.remove(f)


def _generate_tts(text, output_path, voice='alloy'):
    """Generate TTS audio using OpenAI."""
    client = OpenAI()
    response = client.audio.speech.create(
        model='tts-1',
        voice=voice,
        input=text,
        speed=1.0,
    )
    response.stream_to_file(output_path)


def _get_duration(file_path):
    """Get audio/video duration using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def _create_hook_scene(clip_path, hook_text, output_path, audio_path, duration):
    """Create the hook intro video: blurred background + centered text + audio."""
    video_enc = get_ffmpeg_video_encode_args()

    # Extract first frame
    cap = cv2.VideoCapture(clip_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return

    h, w = frame.shape[:2]

    # Create blurred + dimmed background
    blurred = cv2.GaussianBlur(frame, (51, 51), 30)
    dimmed = (blurred * 0.3).astype(np.uint8)

    # Add text overlay using PIL (for better text rendering)
    img = Image.fromarray(cv2.cvtColor(dimmed, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)

    # Try to load a nice font
    font_size = 48
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    # Word wrap
    words = hook_text.split()
    lines = []
    current_line = ""
    max_width = w * 0.8

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            if current_line:
                lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Calculate text block position (centered)
    line_height = font_size + 10
    total_text_height = len(lines) * line_height
    y_start = (h - total_text_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        y = y_start + i * line_height

        # Draw text shadow
        draw.text((x + 2, y + 2), line, fill=(0, 0, 0), font=font)
        # Draw main text (yellow)
        draw.text((x, y), line, fill=(255, 255, 0), font=font)

    # Convert back to OpenCV
    hook_frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # Write static frame as video
    temp_img = output_path + '.png'
    cv2.imwrite(temp_img, hook_frame)

    # Create video from image + audio (GPU-accelerated)
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-i', temp_img,
        '-i', audio_path,
    ] + video_enc + [
        '-tune', 'stillimage' if 'libx264' in video_enc else '',
        '-c:a', 'aac', '-b:a', '128k',
        '-t', str(duration + 0.5),
        '-pix_fmt', 'yuv420p',
        '-vf', f'scale={w}:{h}',
        '-shortest',
        output_path
    ]
    # Remove empty args
    cmd = [c for c in cmd if c]
    subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(temp_img):
        os.remove(temp_img)


def _concat_videos(hook_path, clip_path, output_path):
    """Concatenate hook + clip using FFmpeg with GPU encoding."""
    video_enc = get_ffmpeg_video_encode_args()
    job_dir = os.path.dirname(output_path)
    concat_list = os.path.join(job_dir, 'concat_list.txt')

    with open(concat_list, 'w') as f:
        f.write(f"file '{hook_path}'\n")
        f.write(f"file '{clip_path}'\n")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', concat_list,
    ] + video_enc + [
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(concat_list):
        os.remove(concat_list)
