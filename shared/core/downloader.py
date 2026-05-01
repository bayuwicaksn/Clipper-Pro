"""
Downloader â€” YouTube video + subtitle download via yt-dlp
"""

import os
import json
import subprocess
import re
import time


def download_video(url, output_dir, progress_callback=None):
    """
    Download YouTube video and subtitles.
    
    Args:
        url: YouTube video URL
        output_dir: Directory to save files
        progress_callback: Optional callback(step, message, progress)
    
    Returns:
        dict with video_path, subtitle_path, metadata
    """
    if progress_callback:
        progress_callback('download', 'Starting video download...', 5)

    video_path = os.path.join(output_dir, 'source.mp4')

    # â”€â”€â”€ Resume support: skip download if video already exists â”€â”€â”€â”€â”€â”€â”€
    if os.path.exists(video_path) and os.path.getsize(video_path) > 1_000_000:
        print(f'[Downloader] Video already exists ({os.path.getsize(video_path) / 1024 / 1024:.0f} MB), skipping download.')
        if progress_callback:
            progress_callback('download', 'Video already downloaded, skipping...', 12)

        # Still need metadata from info.json
        metadata = {}
        for f in os.listdir(output_dir):
            if f.endswith('.info.json'):
                info_file = os.path.join(output_dir, f)
                with open(info_file, 'r', encoding='utf-8') as fp:
                    raw = json.load(fp)
                    metadata = {
                        'title': raw.get('title', 'Unknown'),
                        'channel': raw.get('channel', raw.get('uploader', 'Unknown')),
                        'duration': raw.get('duration', 0),
                        'description': raw.get('description', ''),
                        'thumbnail': raw.get('thumbnail', ''),
                        'upload_date': raw.get('upload_date', ''),
                    }
                break

        if progress_callback:
            progress_callback('download', 'Download complete!', 15)

        return {
            'video_path': video_path,
            'subtitle_path': None,
            'metadata': metadata,
        }

    # ── Find cookies file ──────────────────────────────────────────────────
    cookies_path_tmp = '/tmp/cookies.txt'
    
    # Check GCS first (central storage for UI uploads)
    bucket_name = os.getenv("GCS_BUCKET")
    if bucket_name:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob('cookies.txt')
            if blob.exists():
                blob.download_to_filename(cookies_path_tmp)
                print(f'[Downloader] Downloaded fresh cookies.txt from gs://{bucket_name}')
        except Exception as e:
            print(f'[Downloader] GCS cookies check failed: {e}')

    cookies_arg = []
    cookies_locations = [
        cookies_path_tmp,                                             # /tmp from GCS
        'cookies.txt',                                                # Root current dir
        os.path.join(os.getcwd(), 'cookies.txt'),                     # Absolute current dir
        '/app/cookies.txt',                                           # Standard Docker path
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt'), # shared/cookies.txt
        '/content/cookies.txt',                                       # Legacy/Colab
    ]
    for cp in cookies_locations:
        if os.path.exists(cp):
            cookies_arg = ['--cookies', cp]
            print(f'[Downloader] Using cookies from: {cp}')
            break

    # Try multiple download strategies
    # IMPORTANT: Force H.264 codec (avc1). AV1 has NO hardware decoder on GTX 1050 Ti,
    # causing 90% CPU usage during clipping. H.264 is lightweight and GPU-decodable.
    strategies = [
        {
            'name': 'default (EJS + Deno)',
            'args': [
                '--format', 'bv[height<=1080][vcodec~="^(avc|h264)"]+ba/bv[height<=1080]+ba/b/best',
            ]
        },
        {
            'name': 'web_creator client',
            'args': [
                '--extractor-args', 'youtube:player_client=web_creator',
                '--format', 'bv[height<=1080][vcodec~="^(avc|h264)"]+ba/bv[height<=1080]+ba/b/best',
            ]
        },
        {
            'name': 'live Chrome cookies',
            'args': [
                '--cookies-from-browser', 'chrome',
                '--format', 'bv[height<=1080][vcodec~="^(avc|h264)"]+ba/bv[height<=1080]+ba/b/best',
            ]
        },
        {
            'name': 'live Edge cookies',
            'args': [
                '--cookies-from-browser', 'edge',
                '--format', 'bv[height<=1080][vcodec~="^(avc|h264)"]+ba/bv[height<=1080]+ba/b/best',
            ]
        },
        {
            'name': 'any format, remote EJS',
            'args': [
                '--remote-components', 'ejs:github',
                '--format', 'bv[height<=1080][vcodec~="^(avc|h264)"]+ba/b/best/bv+ba',
            ]
        },
    ]

    base_cmd = [
        'yt-dlp',
        '--merge-output-format', 'mp4',
        '--write-info-json',
        '--output', os.path.join(output_dir, 'source.%(ext)s'),
        '--no-playlist',
        '--progress',
        '--force-overwrites',
        '--no-check-certificates',
        '--limit-rate', '10M',           # ðŸ¢ Stable speed (Avoids YouTube throttling)
        '--buffer-size', '1M',           # ðŸ”¥ Boost throughput
        '--http-chunk-size', '10M',      # Optimal chunking
        '--no-part',                     # Direct write (faster on Windows)
        '--sleep-interval', '1',         # ðŸƒ Breathe between requests (human-like)
        '--retries', '5',
        '--socket-timeout', '30',
        '--verbose',
    ]

    last_error = None
    for strategy in strategies:
        if progress_callback:
            progress_callback('download', f"Trying: {strategy['name']}...", 10)

        # Avoid conflict: don't pass --cookies if using --cookies-from-browser
        strat_args = strategy['args']
        if '--cookies-from-browser' not in strat_args:
            strat_args = strat_args + cookies_arg

        cmd = base_cmd + strat_args + [url]
        print(f"[Downloader] Strategy '{strategy['name']}': {' '.join(cmd)}")

        output_lines = []
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()
            output_lines.append(line)
            print(f"[yt-dlp] {line}")
            match = re.search(r'(\d+\.?\d*)%', line)
            if match and progress_callback:
                pct = float(match.group(1))
                progress_callback('download', f'Downloading: {pct:.1f}%', 5 + int(pct * 0.1))

        process.wait()

        if process.returncode == 0:
            print(f"[Downloader] Success with strategy: {strategy['name']}")
            break
        else:
            # WinError 32 workaround: Windows Defender or other processes often lock the temp file 
            # right after ffmpeg finishes, causing yt-dlp's rename to fail.
            success_manual = False
            for ext in ['.mp4', '.mkv', '.webm']:
                temp_path = os.path.join(output_dir, f'source.temp{ext}')
                target_path = os.path.join(output_dir, f'source{ext}')
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1_000_000:
                    print(f"[Downloader] WinError 32 workaround: found {temp_path}, attempting manual rename...")
                    for _ in range(5):
                        try:
                            if os.path.exists(target_path):
                                os.remove(target_path)
                            os.rename(temp_path, target_path)
                            success_manual = True
                            break
                        except Exception:
                            time.sleep(1)
                    if success_manual:
                        break
            
            if success_manual:
                print(f"[Downloader] Success with strategy: {strategy['name']} (manual rename)")
                break

            error_tail = '\n'.join(output_lines[-10:])
            last_error = error_tail
            print(f"[Downloader] Strategy '{strategy['name']}' failed, trying next...")

            # Clean up partial files before retry
            for f in os.listdir(output_dir):
                if f.startswith('source'):
                    try:
                        os.remove(os.path.join(output_dir, f))
                    except Exception:
                        pass
    else:
        # All strategies failed
        full_output = '\n'.join(output_lines)
        if 'Sign in to confirm' in full_output or 'LOGIN_REQUIRED' in full_output:
            raise RuntimeError(
                'YouTube is blocking the download (bot detection). '
                'Please upload a fresh cookies.txt file. '
                'Export from your browser using "Get cookies.txt LOCALLY" extension.'
            )
        raise RuntimeError(
            f'All download strategies failed. Last error:\n{last_error}'
        )

    # Find the downloaded video file (might not be named exactly source.mp4)
    if not os.path.exists(video_path):
        for f in os.listdir(output_dir):
            if f.startswith('source') and f.endswith(('.mp4', '.mkv', '.webm')):
                if '.f' in f or '.temp' in f:
                    continue  # Skip intermediate yt-dlp component files
                actual_video = os.path.join(output_dir, f)
                if actual_video != video_path:
                    os.rename(actual_video, video_path)
                break

    if not os.path.exists(video_path):
        raise RuntimeError(
            f'Video file not found after download. '
            f'Files in dir: {os.listdir(output_dir)}'
        )

    # Find info JSON
    metadata = {}
    for f in os.listdir(output_dir):
        if f.endswith('.info.json'):
            info_file = os.path.join(output_dir, f)
            with open(info_file, 'r', encoding='utf-8') as fp:
                raw = json.load(fp)
                metadata = {
                    'title': raw.get('title', 'Unknown'),
                    'channel': raw.get('channel', raw.get('uploader', 'Unknown')),
                    'duration': raw.get('duration', 0),
                    'description': raw.get('description', ''),
                    'thumbnail': raw.get('thumbnail', ''),
                    'upload_date': raw.get('upload_date', ''),
                }
            break

    if progress_callback:
        progress_callback('download', 'Download complete!', 15)

    return {
        'video_path': video_path,
        'subtitle_path': None,
        'metadata': metadata,
    }
