"""
Caption Generator — Custom ASS-based animated captions (CapCut-style)
Replaces pycaps with a robust, library-free FFmpeg pipeline.
"""

import os
import subprocess
import json
import logging
import re
import math

logger = logging.getLogger('pipeline')

def generate_captions(
    clip_path,
    output_path,
    config=None,
    progress_callback=None,
    clip_index=0,
    total_clips=1,
    custom_words=None
):
    """
    Burn word-by-word animated captions into video using custom ASS generator.
    """
    config = config or {}
    caption_settings = config.get('caption_settings', {})
    preset_id = str(caption_settings.get('presetId', 'default')).lower()

    # Guard: skip if preset is explicitly 'none'
    if preset_id == 'none':
        logger.info("[Caption] Preset is 'none', skipping captions.")
        if progress_callback:
            progress_callback('caption', 'Skipping captions (Preset: None)', 90)
        return

    def _progress(msg, offset=0):
        if progress_callback:
            base = 60 + int((clip_index / max(total_clips, 1)) * 15)
            progress_callback('caption', msg, base + offset)

    # ── 1. Get words ──────────────────────────────────────────────
    if custom_words:
        words = custom_words
        logger.info(f"[Caption] Using {len(words)} pre-mapped words from pipeline.")
    else:
        job_dir = os.path.dirname(output_path)
        audio_path = os.path.join(job_dir, f'audio_{clip_index}.wav')

        _progress('Extracting audio for transcription...', 2)
        _extract_audio(clip_path, audio_path)

        _progress('Running Whisper transcription...', 3)
        words = _transcribe_audio(audio_path)

        # Cleanup temp audio
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass

    if not words:
        logger.warning("[Caption] No words to render. Copying clip as-is.")
        import shutil
        shutil.copy(clip_path, output_path)
        return

    # ── 2. Generate ASS Subtitle File ─────────────────────────────
    _progress('Generating custom ASS subtitle file...', 5)
    ass_path = output_path.replace('.mp4', '.ass')
    
    try:
        # Get video dimensions for proper placement
        width, height = _get_video_dimensions(clip_path)
        _generate_ass_file(words, caption_settings, ass_path, width, height)
        
        # ── 3. Burn captions with FFmpeg ──────────────────────────
        _progress('Burning captions into video (FFmpeg)...', 10)
        _burn_with_ffmpeg(clip_path, ass_path, output_path)
        
        logger.info(f"[Caption] Custom rendering successful -> {output_path}")

        # Cleanup ASS file
        if os.path.exists(ass_path):
            try:
                os.remove(ass_path)
            except Exception:
                pass

    except Exception as e:
        import traceback
        logger.error(f"[Caption] Custom rendering failed: {e}")
        traceback.print_exc()
        import shutil
        shutil.copy(clip_path, output_path)

    _progress(f'Captions done for clip {clip_index + 1}', 15)


# ── ASS Generation Logic ──────────────────────────────────────────

def _generate_ass_file(words, settings, ass_path, video_w, video_h):
    """Generates an Advanced Substation Alpha (.ass) file with word-focus styling."""
    
    # 1. Extract settings
    font_name      = settings.get('fontName', 'Montserrat')
    font_size      = settings.get('fontSize', 32)
    primary_color  = _hex_to_ass(settings.get('primaryColor', '#FFFFFF'))
    outline_color  = _hex_to_ass(settings.get('outlineColor', '#000000'))
    outline_width  = settings.get('outlineWidth', 8)
    shadow_enabled = settings.get('shadowEnabled', True)
    shadow_color   = _hex_to_ass(settings.get('shadowColor', '#000000'))
    is_uppercase   = settings.get('isUppercase', True)
    y_pos_ratio    = settings.get('captionY', 0.8)
    max_width_pct  = settings.get('captionWidth', 100) / 100.0
    
    # Scaling factor for font (ASS uses different coordinate space than CSS)
    # We calibrate based on 1080p target
    font_scale = video_h / 600.0 
    scaled_font_size = font_size * font_scale
    scaled_outline = outline_width * (video_h / 1080.0)

    # 2. Build Chunks (Word groups for line wrapping)
    # This logic mirrors the frontend wrapping
    chunks = []
    current_chunk = []
    
    # Simple line-length based chunking (can be improved)
    chars_per_line = 25 
    max_chars = chars_per_line * 2 # 2 lines
    
    current_len = 0
    for w in words:
        txt = w['word'].upper() if is_uppercase else w['word']
        if current_len + len(txt) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [w]
            current_len = len(txt)
        else:
            current_chunk.append(w)
            current_len += len(txt) + 1
    if current_chunk:
        chunks.append(current_chunk)

    # 3. Create ASS Header
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_w}",
        f"PlayResY: {video_h}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{scaled_font_size},{primary_color},&H0000FFFF,{outline_color},{shadow_color},-1,0,0,0,100,100,0,0,1,{scaled_outline},{2 if shadow_enabled else 0},2,10,10,{int(video_h * (1 - y_pos_ratio))},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    # 4. Generate Events
    events = []
    for chunk in chunks:
        chunk_start = _to_ass_time(chunk[0]['start'])
        chunk_end = _to_ass_time(chunk[-1]['end'])
        
        # Base text for the entire chunk
        full_text_list = []
        for w in chunk:
            full_text_list.append(w['word'].upper() if is_uppercase else w['word'])
        
        # For each word in the chunk, create a timed event where that word is highlighted
        for i, target_word in enumerate(chunk):
            start_t = _to_ass_time(target_word['start'])
            end_t = _to_ass_time(target_word['end'])
            
            # If there's a gap between words, we might need a "dimmed" state event, 
            # but for simplicity, we just span the highlighted word.
            
            highlighted_text = ""
            for j, w in enumerate(chunk):
                word_txt = w['word'].upper() if is_uppercase else w['word']
                if i == j:
                    # Highlight color (Yellowish default or from settings)
                    # For now, let's use a bright yellow highlight like Pycaps
                    highlight_tag = "{\\c&H00FFFF&}" # Yellow in BGR (&HBBGGRR)
                    highlighted_text += f"{highlight_tag}{word_txt}{{\\c{primary_color}}}"
                else:
                    highlighted_text += word_txt
                
                if j < len(chunk) - 1:
                    highlighted_text += " "
            
            events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{highlighted_text}")

    # Write to file
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(header + events))

def _hex_to_ass(hex_color):
    """Converts #RRGGBB to &HBBGGRR (ASS format)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}" # 00 is alpha (opaque)
    return "&H00FFFFFF"

def _to_ass_time(seconds):
    """Converts seconds to H:MM:SS.cc format."""
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{mins:02d}:{secs:05.2f}"

def _get_video_dimensions(path):
    """Get width and height via ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0', path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            w, h = map(int, res.stdout.strip().split('x'))
            return w, h
    except:
        pass
    return 1080, 1920 # Default

def _burn_with_ffmpeg(input_path, ass_path, output_path):
    """Uses FFmpeg to burn ASS subtitles into the video."""
    
    # Path sanitization for FFmpeg's subtitles filter (crucial on Windows)
    # FFmpeg expects backslashes to be escaped or forward slashes to be used.
    safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
    
    # Try GPU (NVENC) first, fallback to CPU
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f"subtitles='{safe_ass_path}'",
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',
            '-rc:v', 'vbr',
            '-cq:v', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',
            output_path
        ]
        logger.info(f"[Caption] Burning with NVENC: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        logger.warning(f"[Caption] NVENC failed, falling back to CPU (libx264): {e}")
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f"subtitles='{safe_ass_path}'",
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)


# ── Audio helpers (unchanged but cleaned) ─────────────────────────

def _extract_audio(video_path, audio_path):
    cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _transcribe_audio(audio_path):
    from openai import OpenAI
    client = OpenAI()
    with open(audio_path, 'rb') as f:
        transcription = client.audio.transcriptions.create(
            model='whisper-1', file=f, response_format='verbose_json', timestamp_granularities=['word']
        )
    words = []
    raw_words = getattr(transcription, 'words', None) or []
    for w in raw_words:
        text = w.word if hasattr(w, 'word') else w.get('word', '')
        start = w.start if hasattr(w, 'start') else w.get('start', 0)
        end = w.end if hasattr(w, 'end') else w.get('end', 0)
        if text.strip():
            words.append({'word': text.strip(), 'start': start, 'end': end})
    return words