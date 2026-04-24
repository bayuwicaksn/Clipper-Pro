"""
Caption Generator — pycaps-powered animated captions (CapCut-style)
Whisper transcription fallback when custom_words not provided.
"""

import os
import subprocess
import json
import logging

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
    Burn word-by-word animated captions into video using pycaps.

    Args:
        clip_path:         Path to the input clip.
        output_path:       Path for output with burned-in captions.
        config:            Dict with styling/caption settings.
        progress_callback: Optional progress callback (event, message, pct).
        clip_index:        Index of this clip (for progress calculation).
        total_clips:       Total number of clips (for progress calculation).
        custom_words:      Optional list of {'word', 'start', 'end'} dicts.
                           Already mapped to local clip time by pipeline.py.
                           If None, transcription is run on the clip itself.
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

    # ── 2. Build pycaps pipeline ──────────────────────────────────
    _progress('Rendering animated captions with pycaps...', 5)

    try:
        from pycaps.pipeline import CapsPipelineBuilder
        from pycaps.common import Word, SubtitleLayoutOptions
        from pycaps.template import TemplateFactory

        # Convert word dicts → pycaps Word objects
        pycaps_words = [
            Word(
                text=w['word'],
                start=float(w['start']),
                end=float(w['end'])
            )
            for w in words
            if w.get('word') and w.get('end', 0) > w.get('start', 0)
        ]

        if not pycaps_words:
            logger.warning("[Caption] No valid words after filtering. Copying clip.")
            import shutil
            shutil.copy(clip_path, output_path)
            return

        # Style settings dari caption_settings
        font_name     = caption_settings.get('fontName', 'Anton')
        font_size     = caption_settings.get('fontSize', 100)
        primary_color = caption_settings.get('primaryColor', '#FFD700')
        outline_color = caption_settings.get('outlineColor', '#000000')
        margin_v      = caption_settings.get('verticalMargin', 150)

        layout = SubtitleLayoutOptions(
            font_family=font_name,
            font_size=font_size,
            primary_color=primary_color,
            secondary_color=outline_color,
            vertical_margin=margin_v,
            max_width_ratio=0.9
        )

        # Mapping nama lama -> nama pycaps resmi untuk backward compatibility
        PRESET_MAP = {
            'karaoke':   'word-focus',
            'bold':      'explosive',
            'clean':     'minimalist',
            'cinematic': 'model',
            'retro':     'retro-gaming',
            'neo':       'neo-minimal',
        }
        mapped_id = PRESET_MAP.get(preset_id, preset_id)

        from pycaps import TemplateLoader

        # Build pipeline exactly as shown in pycaps "Quick Start" documentation
        # but with our custom transcription and layout overrides
        pipeline = (
            TemplateLoader(mapped_id)
            .with_input_video(clip_path)
            .load(False) # Returns CapsPipelineBuilder
            .with_output_video(output_path)
            .with_transcription(pycaps_words)
            .with_layout_options(layout)
            .build()
        )

        logger.info(f"[Caption] Running pycaps pipeline with preset '{mapped_id}'")
        pipeline.run() # Official way to start rendering
        
        logger.info(f"[Caption] pycaps rendered successfully -> {output_path}")

    except ImportError as e:
        logger.error(
            f"[Caption] pycaps import failed: {e}. "
            "Run: pip install 'git+https://github.com/francozanardi/pycaps.git#egg=pycaps[all]'"
        )
        import shutil
        shutil.copy(clip_path, output_path)

    except Exception as e:
        import traceback
        logger.error(f"[Caption] pycaps rendering failed: {e}")
        traceback.print_exc()
        # Fallback: copy raw clip agar pipeline tidak berhenti total
        import shutil
        shutil.copy(clip_path, output_path)

    _progress(f'Captions done for clip {clip_index + 1}', 15)


# ── Audio helpers ─────────────────────────────────────────────────

def _extract_audio(video_path: str, audio_path: str) -> None:
    """Extract mono 16kHz WAV audio dari video untuk Whisper."""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        audio_path
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _, stderr = process.communicate()
    if process.returncode != 0:
        err = stderr.decode('utf-8', errors='replace')[-300:] if stderr else 'unknown'
        logger.warning(f"[Caption] Audio extraction failed: {err}")


def _transcribe_audio(audio_path: str) -> list:
    """Transcribe audio menggunakan OpenAI Whisper API dengan word-level timestamps."""
    from openai import OpenAI

    logger.info("[Caption] Uploading audio to OpenAI Whisper API...")
    client = OpenAI()

    # Compress jika melebihi limit 25MB Whisper
    file_size = os.path.getsize(audio_path)
    if file_size > 24 * 1024 * 1024:
        logger.info(f"[Caption] Audio too large ({file_size/1024/1024:.1f}MB), compressing...")
        compressed_path = audio_path.replace('.wav', '_compressed.mp3')
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-vn', '-acodec', 'libmp3lame', '-ab', '24k',
            '-ar', '16000', '-ac', '1',
            compressed_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(compressed_path):
            audio_path = compressed_path

    with open(audio_path, 'rb') as audio_file:
        transcription = client.audio.transcriptions.create(
            model='whisper-1',
            file=audio_file,
            response_format='verbose_json',
            timestamp_granularities=['word']
        )

    words = []
    raw_words = getattr(transcription, 'words', None) or []
    for w in raw_words:
        text  = w.word  if hasattr(w, 'word')  else w.get('word', '')
        start = w.start if hasattr(w, 'start') else w.get('start', 0)
        end   = w.end   if hasattr(w, 'end')   else w.get('end', 0)
        if text.strip():
            words.append({'word': text.strip(), 'start': start, 'end': end})

    logger.info(f"[Caption] Whisper returned {len(words)} words.")
    return words


def _get_clip_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"[Caption] ffprobe duration failed: {e}")
    return 0.0