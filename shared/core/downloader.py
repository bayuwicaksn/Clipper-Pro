import os
import tempfile
import yt_dlp

# Lazy initialization for GCS client to avoid slow module imports
_storage_client = None
_storage_client_initialized = False

def get_storage_client():
    global _storage_client, _storage_client_initialized
    if not _storage_client_initialized:
        _storage_client_initialized = True
        try:
            from google.cloud import storage
            _storage_client = storage.Client()
        except Exception as e:
            print(f"[Downloader] Failed to initialize global storage client: {e}")
    return _storage_client

class CustomLogger:
    """Redirects yt-dlp logs to standard print for Cloud Logging"""
    def debug(self, msg):
        print(msg)
            
    def info(self, msg):
        print(msg)

    def warning(self, msg):
        print(f"[WARNING] {msg}")

    def error(self, msg):
        print(f"[ERROR] {msg}")

def download_video(url, output_dir, progress_callback=None):
    """
    Download YouTube video and subtitles using native yt-dlp API.
    """
    if progress_callback:
        progress_callback('download', 'Starting video download...', 5)

    video_path = os.path.join(output_dir, 'source.mp4')
    subtitle_path = os.path.join(output_dir, 'source.en.vtt') # yt-dlp names it based on language

    # ─── Resume support ───────────────────────────────────────────────────────
    if os.path.exists(video_path) and os.path.getsize(video_path) > 1_000_000:
        print(f'[Downloader] Video already exists ({os.path.getsize(video_path) / 1024 / 1024:.0f} MB), skipping.')
        if progress_callback:
            progress_callback('download', 'Video already downloaded, skipping...', 12)
        # Metadata extraction logic remains the same here...
        return {'video_path': video_path, 'subtitle_path': subtitle_path, 'metadata': {}}

    # ─── Cookie Management ────────────────────────────────────────────────────
    cookies_path = None
    tmp_cookie_file = os.path.join(tempfile.gettempdir(), 'cookies.txt')
    
    bucket_name = os.getenv("GCS_BUCKET")
    client = get_storage_client()
    if bucket_name and client:
        try:
            bucket = client.bucket(bucket_name)
            blob = bucket.blob('cookies.txt')
            if blob.exists():
                blob.download_to_filename(tmp_cookie_file)
                cookies_path = tmp_cookie_file
                print(f'[Downloader] Downloaded fresh cookies.txt from gs://{bucket_name}')
        except Exception as e:
            print(f'[Downloader] GCS cookies check failed: {e}')

    if not cookies_path:
        # Fallback locations if GCS fails
        for cp in ['cookies.txt', '/app/cookies.txt']:
            if os.path.exists(cp):
                cookies_path = cp
                break

    # ─── Progress Hook ────────────────────────────────────────────────────────
    def my_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            percent_str = d.get('_percent_str', '0.0%').strip('\x1b[0;94m').strip('\x1b[0m').replace('%', '')
            try:
                pct = float(percent_str)
                progress_callback('download', f"Downloading: {pct:.1f}%", 5 + int(pct * 0.1))
            except ValueError:
                pass
        elif d['status'] == 'finished':
            print('[Downloader] Download finished, now merging/post-processing...')

    # ─── yt-dlp Configuration ─────────────────────────────────────────────────
    ydl_opts = {
        'format': 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio/bestvideo[height<=1080]+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_dir, 'source.%(ext)s'),
        'writeinfojson': True,
        
        # Subtitle config
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        
        # Performance & Networking
        'limit_rate': 10000000, # 10M
        'http_chunk_size': 10485760, # 10M
        'sleep_interval': 1,
        'retries': 5,
        'socket_timeout': 30,
        
        # Anti-Bot Strategy (Client spoofing with PO Token support)
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'default']
            },
            'youtubepot-bgutilscript': {
                'server_home': ['/app/bgutil-ytdlp-pot-provider/server']
            }
        },
        
        'logger': CustomLogger(),
        'progress_hooks': [my_hook],
        'cookiefile': cookies_path,
        'nocheckcertificate': True,
        'noplaylist': True,
    }

    # ─── Execute Download ─────────────────────────────────────────────────────
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("[Downloader] Starting native yt-dlp extraction...")
            info_dict = ydl.extract_info(url, download=True)
            
            # Extract metadata directly from the memory object instead of reading the JSON file!
            metadata = {
                'title': info_dict.get('title', 'Unknown'),
                'channel': info_dict.get('channel', info_dict.get('uploader', 'Unknown')),
                'duration': info_dict.get('duration', 0),
                'description': info_dict.get('description', ''),
                'thumbnail': info_dict.get('thumbnail', ''),
                'upload_date': info_dict.get('upload_date', ''),
            }
            
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"yt-dlp failed: {e}")

    # Check for actual output files
    actual_video = None
    actual_sub = None
    
    for f in os.listdir(output_dir):
        if f.startswith('source') and f.endswith('.mp4'):
            actual_video = os.path.join(output_dir, f)
        if f.startswith('source') and f.endswith(('.vtt', '.srt')):
            actual_sub = os.path.join(output_dir, f)

    if not actual_video:
        raise RuntimeError(f'Video file not found after download. Dir contents: {os.listdir(output_dir)}')

    if progress_callback:
        progress_callback('download', 'Download complete!', 15)

    return {
        'video_path': actual_video,
        'subtitle_path': actual_sub,
        'metadata': metadata,
    }
