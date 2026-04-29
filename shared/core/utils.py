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

from shared.utils.helpers import (
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
            if provider in ('openai-whisper', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe'):
                import subprocess
                from .caption_generator import _transcribe_audio, _transcribe_audio_gpt4o
                
                # 1. Extract Full Audio
                audio_path = os.path.join(job_dir, 'source_audio_temp.mp3')
                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-vn', '-acodec', 'libmp3lame', '-ab', '64k', '-ar', '16000', '-ac', '1',
                    audio_path
                ]
                subprocess.run(cmd, capture_output=True)
                
                if os.path.exists(audio_path):
                    # 2. Get Duration
                    res = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], capture_output=True, text=True)
                    duration = float(res.stdout.strip() or 0)
                    
                    # 3. Chunking Logic (5 minutes per chunk)
                    chunk_size = 300 # seconds
                    words = []
                    num_chunks = int(duration / chunk_size) + 1
                    
                    for i in range(num_chunks):
                        start_time = i * chunk_size
                        if start_time >= duration: break
                        
                        chunk_audio = os.path.join(job_dir, f'chunk_{i}.mp3')
                        print(f"[TRANSCRIPT] Process: Part {i+1}/{num_chunks} ({int(start_time)}s - {int(min(start_time+chunk_size, duration))}s)...")
                        
                        # Extract chunk
                        subprocess.run(['ffmpeg', '-y', '-ss', str(start_time), '-t', str(chunk_size), '-i', audio_path, '-acodec', 'copy', chunk_audio], capture_output=True)
                        
                        if os.path.exists(chunk_audio):
                            if provider == 'openai-whisper':
                                chunk_words = _transcribe_audio(chunk_audio, offset=start_time)
                            else:
                                chunk_words = _transcribe_audio_gpt4o(chunk_audio, model_name=provider, offset=start_time)
                            
                            words.extend(chunk_words)
                            os.remove(chunk_audio)
                    
                    source_label = provider
                    os.remove(audio_path)

        except Exception as e:
            print(f"[TRANSCRIPT] Failed: {e}")
            words = None

    if not words:
        raise FileNotFoundError("Transcription failed. Check source file and API keys.")
    
    with open(transcript_path, 'w', encoding='utf-8') as f:
        json.dump({'_source': source_label, 'words': words}, f, indent=2, ensure_ascii=False)
    
    return transcript_path, words
