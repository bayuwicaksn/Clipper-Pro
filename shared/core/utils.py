import os
import json
import logging
import subprocess
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

def get_source_transcript(job_dir, force=False, provider='openai-whisper', progress_callback=None):
    """Load or generate the full source transcript (transcribe once, reuse forever)."""
    transcript_path = os.path.join(job_dir, 'source_transcript.json')
    
    def _report(step, msg, progress):
        if progress_callback:
            progress_callback(step, msg, progress)
        else:
            print(f"[{step}] {msg} ({progress}%)")

    # If already generated, check if it needs upgrading
    if os.path.exists(transcript_path) and not force:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    source = data.get('_source', 'unknown')
                    words = data.get('words', [])
                else:
                    source = 'unknown'
                    words = data
                
                if source not in ('srt', 'unknown'):
                    return transcript_path, words
                
                _report('analyze', f"Cached transcript from '{source}' is imprecise. Upgrading...", 25)
            except Exception as e:
                print(f"[TRANSCRIPT] Error loading cache: {e}")

    # Transcription Logic
    _report('analyze', f"Generating word-level transcript ({provider})...", 25)
    
    # Provider normalization
    api_providers = ('openai-whisper', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe', 'whisper-api', 'local-whisper')
    
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
            if provider in api_providers:
                from .caption_generator import _transcribe_audio, _transcribe_audio_gpt4o
                
                # Normalize provider for internal logic
                actual_provider = provider
                if provider == 'local-whisper' or provider == 'whisper-api':
                    actual_provider = 'openai-whisper'

                # 1. Extract Full Audio
                audio_path = os.path.join(job_dir, 'source_audio_temp.mp3')
                _report('analyze', "Extracting audio for transcription...", 26)
                cmd = [
                    'ffmpeg', '-y', '-i', video_path,
                    '-vn', '-acodec', 'libmp3lame', '-ab', '64k', '-ar', '16000', '-ac', '1',
                    audio_path
                ]
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300) # 5 min timeout
                except subprocess.TimeoutExpired:
                    _report('error', "Audio extraction timed out after 5 minutes.", 0)
                    raise TimeoutError("FFmpeg audio extraction timed out.")
                
                if os.path.exists(audio_path):
                    # 2. Get Duration
                    res = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], capture_output=True, text=True, timeout=10)
                    duration = float(res.stdout.strip() or 0)
                    
                    # 3. Chunking Logic (5 minutes per chunk)
                    chunk_size = 300 # seconds
                    words = []
                    num_chunks = int(duration / chunk_size) + 1
                    
                    for i in range(num_chunks):
                        start_time = i * chunk_size
                        if start_time >= duration: break
                        
                        chunk_audio = os.path.join(job_dir, f'chunk_{i}.mp3')
                        p_val = 27 + int((i / num_chunks) * 40)
                        _report('analyze', f"Transcribing part {i+1}/{num_chunks}...", p_val)
                        
                        # Extract chunk
                        try:
                            subprocess.run(['ffmpeg', '-y', '-ss', str(start_time), '-t', str(chunk_size), '-i', audio_path, '-acodec', 'copy', chunk_audio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                        except subprocess.TimeoutExpired:
                            print(f"[TRANSCRIPT] Chunk {i+1} extraction timed out.")
                            continue
                        
                        if os.path.exists(chunk_audio):
                            try:
                                if actual_provider == 'openai-whisper':
                                    chunk_words = _transcribe_audio(chunk_audio, offset=start_time)
                                else:
                                    chunk_words = _transcribe_audio_gpt4o(chunk_audio, model_name=actual_provider, offset=start_time)
                                
                                if chunk_words:
                                    words.extend(chunk_words)
                            finally:
                                if os.path.exists(chunk_audio):
                                    os.remove(chunk_audio)
                    
                    source_label = actual_provider
                    os.remove(audio_path)
            else:
                _report('analyze', f"Warning: Provider '{provider}' not supported. Using fallback.", 30)

        except Exception as e:
            _report('error', f"Transcription failed: {e}", 0)
            import traceback
            traceback.print_exc()
            words = None

    if not words:
        _report('error', "Transcription FAILED. Check API keys and source video.", 0)
        raise FileNotFoundError(f"Transcription failed for provider '{provider}'.")
    
    with open(transcript_path, 'w', encoding='utf-8') as f:
        json.dump({'_source': source_label, 'words': words}, f, indent=2, ensure_ascii=False)
    
    _report('analyze', f"Transcription complete! ({len(words)} words)", 68)
    return transcript_path, words
