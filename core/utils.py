import os
import json
import logging
from datetime import datetime

# Ensure logs directory exists
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

def setup_logging(name, log_file, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    
    handler = logging.FileHandler(os.path.join(LOGS_DIR, log_file))        
    handler.setFormatter(formatter)

    # Console handler for terminal visibility
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger

# Initialize global loggers
app_logger = setup_logging('app', 'app.log')
pipeline_logger = setup_logging('pipeline', 'pipeline.log')

from utils.helpers import (
    timestamp_to_seconds,
    seconds_to_timestamp,
    seconds_to_timestamp_simple,
    resolve_job_dir,
    get_clip_dir,
    filter_words_by_range
)

def get_source_transcript(job_dir, force=False, provider='openai-whisper'):
    """Load or generate the full source transcript (transcribe once, reuse forever)."""
    transcript_path = os.path.join(job_dir, 'source_transcript.json')
    
    # If already generated, check if it needs upgrading
    if os.path.exists(transcript_path) and not force:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            source = data.get('_source', 'unknown')
            words = data.get('words', [])
        else:
            source = 'unknown'
            words = data
        
        if source in ('srt', 'unknown'):
            print(f"[TRANSCRIPT] Cached transcript was from '{source}' (imprecise). Auto-upgrading...")
        else:
            return transcript_path, words
    
    # Transcription Logic
    print(f"[TRANSCRIPT] Generating word-level transcript (Provider: {provider})...")
    words = None
    source_label = 'unknown'
    
    video_path = os.path.join(job_dir, 'source.mp4')
    if not os.path.exists(video_path):
        for f in os.listdir(job_dir):
            if f.endswith('.mp4') and not os.path.isdir(os.path.join(job_dir, f)):
                video_path = os.path.join(job_dir, f)
                break
    
    if os.path.exists(video_path):
        try:
            if provider == 'openai-whisper':
                import subprocess
                audio_path = os.path.join(job_dir, 'source_audio_temp.mp3')
                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-vn', '-acodec', 'libmp3lame', '-ab', '24k', '-ar', '16000', '-ac', '1',
                    audio_path
                ]
                subprocess.run(cmd, capture_output=True, text=True)
                
                if os.path.exists(audio_path):
                    from core.caption_generator import _transcribe_audio
                    words = _transcribe_audio(audio_path)
                    source_label = 'whisper'
                    os.remove(audio_path)
            
            elif provider == 'local-whisper':
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(video_path, word_timestamps=True, verbose=False)
                words = []
                for segment in result.get('segments', []):
                    for w in segment.get('words', []):
                        words.append({'word': w['word'].strip(), 'start': w['start'], 'end': w['end']})
                source_label = 'local-whisper'
            
            elif provider in ('gpt-4o-transcribe', 'gpt-4o-mini-transcribe'):
                from core.caption_generator import _transcribe_audio_gpt4o
                # Models from the new Audio API
                import subprocess
                audio_path = os.path.join(job_dir, 'source_audio_temp.wav')
                # Extract WAV as it is standard for transcription
                subprocess.run(['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path], capture_output=True)
                words = _transcribe_audio_gpt4o(audio_path, model_name=provider)
                source_label = provider
                if os.path.exists(audio_path): os.remove(audio_path)

        except Exception as e:
            print(f"[TRANSCRIPT] Failed: {e}")
            words = None

    if not words:
        raise FileNotFoundError("Transcription failed. Check source file and API keys.")
    
    with open(transcript_path, 'w', encoding='utf-8') as f:
        json.dump({'_source': source_label, 'words': words}, f, indent=2, ensure_ascii=False)
    
    return transcript_path, words
