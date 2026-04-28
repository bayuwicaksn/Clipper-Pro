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
    """
    Generates an Advanced Substation Alpha (.ass) file with dynamic word-by-word
    animations, auto-highlighting, and styling that matches the React frontend.
    """
    # 1. Extract settings with defaults
    font_name      = settings.get('fontName', 'Montserrat')
    font_size      = settings.get('fontSize', 100)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(ass_path), exist_ok=True)
    logger.info(f"[Caption] Generating ASS file at: {ass_path}")
    primary_color  = _hex_to_ass(settings.get('primaryColor', '#FFFFFF'))
    outline_color  = _hex_to_ass(settings.get('outlineColor', '#000000'))
    outline_width  = settings.get('outlineWidth', 8)
    
    # Highlight Colors
    highlight_green  = _hex_to_ass(settings.get('highlightColorGreen', '#04f827'))
    highlight_yellow = _hex_to_ass(settings.get('highlightColorYellow', '#fffd03'))
    
    # Font Style & Weight
    font_weight    = settings.get('fontWeight', 'Black')
    is_italic      = 1 if settings.get('isItalic', False) else 0
    is_underline   = 1 if settings.get('isUnderline', False) else 0
    is_uppercase   = settings.get('isUppercase', True)
    bold_flag      = -1 if font_weight in ['Black', 'Bold', 'Heavy'] else 0
    
    # Shadow & Glow
    shadow_enabled = settings.get('shadowEnabled', True)
    shadow_color   = _hex_to_ass(settings.get('shadowColor', '#000000'))
    shadow_x       = settings.get('shadowOffsetX', 2)
    shadow_y       = settings.get('shadowOffsetY', 2)
    shadow_blur    = settings.get('shadowBlur', 2)
    
    # Position & Layout
    x_pos_ratio    = settings.get('captionX', 0.5)
    y_pos_ratio    = settings.get('captionY', 0.82)
    max_width_pct  = settings.get('captionWidth', 85) / 100.0
    line_limit     = settings.get('lineLimit', 2)
    style_type     = settings.get('styleType', 'classic').lower()
    auto_highlight = settings.get('autoHighlight', True)

    # Global Scaling 
    # We use 540px as the reference height because the browser preview 
    # area is typically around that height. This ensures the visual 
    # ratio between font and video height remains consistent.
    font_scale = video_h / 540.0 
    scaled_font_size = int(font_size * font_scale)
    scaled_outline   = (font_size * outline_width) / 1000.0 * font_scale
    
    pos_x = int(video_w * x_pos_ratio)
    pos_y = int(video_h * y_pos_ratio)

    # Word Chunking Logic (Matches Frontend Pages)
    if line_limit == 1:
        max_chars = 12
    elif line_limit == 3:
        max_chars = 40
    else: # Default line_limit 2
        max_chars = 25
        
    # Container-aware Line Wrapping
    # Calculate how many characters roughly fit in the container width
    # Reference: at 100% width, ~30-35 thick characters fit 1080p width
    chars_that_fit_container = int((settings.get('captionWidth', 85) / 100.0) * 32)
    
    # We take the stricter of the two: either balanced by lineLimit or limited by container
    max_chars_per_line = min(max_chars / line_limit, chars_that_fit_container)
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for w in words:
        txt = w['word'].strip()
        if not txt: continue
        txt = txt.upper() if is_uppercase else txt
        word_len = len(txt)
        
        if current_len + word_len > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_len = 0
        
        current_chunk.append({'word': txt, 'start': w['start'], 'end': w['end']})
        current_len += word_len + 1
        
    if current_chunk:
        chunks.append(current_chunk)

    # Regex patterns for auto-highlighting
    GREEN_REGEX  = r"^(sukses|kaya|uang|viral|trending|presiden|milyar|triliun|cuan)"
    YELLOW_REGEX = r"^(penting|rahasia|masalah|solusi|gila|keren|tips|trik|cara|fakta|bukti)"

    # Styles
    # Alignment 5 = Middle Center
    style_line = (
        f"Style: Default,{font_name},{scaled_font_size},{primary_color},&H0000FFFF,{outline_color},{shadow_color},"
        f"{bold_flag},{is_italic},{is_underline},0,100,100,0,0,1,{scaled_outline:0.2f},{shadow_blur if shadow_enabled else 0},5,0,0,0,1"
    )

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_w}",
        f"PlayResY: {video_h}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 1",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style_line,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    events = []
    for chunk in chunks:
        for i, target_word in enumerate(chunk):
            start_t = _to_ass_time(target_word['start'])
            end_t = _to_ass_time(target_word['end'])
            
            # Duration of this word in ms for animation timing
            duration_ms = int((target_word['end'] - target_word['start']) * 1000)
            anim_duration = min(150, duration_ms) # Cap animation at 150ms
            
            highlighted_text = f"{{\\pos({pos_x},{pos_y})}}"
            
            for j, w in enumerate(chunk):
                is_active = (i == j)
                word_txt = w['word']
                
                # Determine Color
                is_green_keyword = auto_highlight and re.match(GREEN_REGEX, word_txt, re.IGNORECASE)
                is_yellow_keyword = auto_highlight and re.match(YELLOW_REGEX, word_txt, re.IGNORECASE)
                
                current_color = primary_color
                if is_active:
                    current_color = highlight_green
                elif is_green_keyword:
                    current_color = highlight_green
                elif is_yellow_keyword:
                    current_color = highlight_yellow
                
                # Apply Tags
                tags = [f"\\c{current_color}"]
                
                # Apply Animations to Active Word
                if is_active:
                    is_intense = style_type in ['explosive', 'hype', 'vibrant']
                    is_bouncy  = style_type in ['explosive', 'hype', 'vibrant', 'model', 'fast']
                    
                    # Pop/Scale effect
                    scale_val = 125 if is_bouncy else 115
                    tags.append(f"\\fscx{scale_val}\\fscy{scale_val}")
                    tags.append(f"\\t(0,{anim_duration},\\fscx100\\fscy100)")
                    
                    # Rotation for intense styles
                    if is_intense:
                        rot = -4 if i % 2 == 0 else 4
                        tags.append(f"\\frz{rot}")
                        tags.append(f"\\t(0,{anim_duration},\\frz0)")
                    
                    # Glowing shadow for intense styles
                    if is_intense and shadow_enabled:
                        tags.append(f"\\blur15")
                        tags.append(f"\\t(0,{anim_duration},\\blur{shadow_blur})")

                elif j > i: # Future words (dimmed)
                    opacity = "99" if style_type in ['explosive', 'hype', 'vibrant'] else "44"
                    tags.append(f"\\alpha&H{opacity}&")
                
                word_full = f"{{{''.join(tags)}}}{word_txt}{{\\alpha&H00&\\fscx100\\fscy100\\frz0\\blur{shadow_blur if shadow_enabled else 0}}}"
                highlighted_text += word_full
                
                # Intelligent Line Breaking (\N)
                if j < len(chunk) - 1:
                    # Calculate if we should wrap
                    current_line_text = "".join([w_['word'] for w_ in chunk[:j+1]])
                    next_word = chunk[j+1]['word']
                    
                    # If adding the next word exceeds the balanced line limit, 
                    # and we haven't reached the line limit yet
                    if len(current_line_text) + len(next_word) > max_chars_per_line:
                        # Only wrap if we are balanced (simulating textWrap: balance)
                        # We use \N for explicit break
                        highlighted_text += "\\N"
                        # Reset virtual line counter for balancing the next line
                        # In a simple 2-line scenario, this just happens once
                    else:
                        highlighted_text += " "
            
            events.append(f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{highlighted_text}")

    # 5. Write to file
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(header + events))
    
    if os.path.exists(ass_path):
        logger.info(f"[Caption] ASS file created successfully: {os.path.getsize(ass_path)} bytes")
    else:
        logger.error(f"[Caption] FAILED to create ASS file at: {ass_path}")


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
    
    # Ensure input and ASS files exist
    if not os.path.exists(input_path):
        logger.error(f"[Caption] INPUT file NOT FOUND at: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not os.path.exists(ass_path):
        logger.error(f"[Caption] ASS file NOT FOUND at: {ass_path}")
        raise FileNotFoundError(f"ASS file not found: {ass_path}")

    # Path sanitization for FFmpeg's subtitles filter (crucial on Windows)
    # Trying format: subtitles=filename='C\:/path/to/file.ass'
    # According to FFmpeg's ticket #10243 and related Windows reports:
    # Forward slashes + escaped colon with one backslash inside single quotes.
    safe_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
    vf_filter = f"subtitles=filename='{safe_ass_path}'"
    
    # Try GPU (NVENC) first, fallback to CPU
    for codec, args in [
        ('h264_nvenc', ['-preset', 'p4', '-rc:v', 'vbr', '-cq:v', '23']),
        ('libx264', ['-preset', 'fast', '-crf', '23'])
    ]:
        # Cleanup output if it exists to avoid lock/prompt issues
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass

        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', vf_filter,
            '-c:v', codec,
            *args,
            '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',
            output_path
        ]
        
        try:
            logger.info(f"[Caption] Burning with {codec}: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return # Success!
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.warning(f"[Caption] {codec} failed: {error_msg}")
            if codec == 'libx264': # Final failure
                raise Exception(f"FFmpeg caption burn failed: {error_msg}")


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