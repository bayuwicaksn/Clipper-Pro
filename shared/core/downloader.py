import os
import tempfile
import uuid
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
    
    # Generate unique temp file name to prevent race conditions during concurrent downloads
    unique_id = uuid.uuid4().hex
    tmp_cookie_file = os.path.join(tempfile.gettempdir(), f'cookies_{unique_id}.txt')
    
    # ─── Proxy & Cookie Selection (Auto-Rotation Support) ─────────────────────
    proxy_url = os.getenv("PROXY_URL")
    cookie_name = os.getenv("COOKIE_NAME", "cookies.txt")
    
    proxy_list_json = os.getenv("PROXY_LIST_JSON")
    if proxy_list_json:
        try:
            import json, random
            proxies = json.loads(proxy_list_json)
            if isinstance(proxies, list) and len(proxies) > 0:
                selected = random.choice(proxies)
                proxy_url = selected.get('url', proxy_url)
                cookie_name = selected.get('cookie', cookie_name)
                print(f"[Downloader] Auto-rotation active. Selected proxy and matching cookie: {cookie_name}")
        except Exception as e:
            print(f"[Downloader] Failed to parse PROXY_LIST_JSON: {e}")

    bucket_name = os.getenv("GCS_BUCKET")
    client = get_storage_client()
    if bucket_name and client:
        try:
            bucket = client.bucket(bucket_name)
            # Automatically look in the specific project folder
            full_cookie_path = f"clipper_pro/cookies/{cookie_name}" if "/" not in cookie_name else cookie_name
            blob = bucket.blob(full_cookie_path)
            if blob.exists():
                blob.download_to_filename(tmp_cookie_file)
                cookies_path = tmp_cookie_file
                print(f'[Downloader] Downloaded matching cookies ({full_cookie_path}) from gs://{bucket_name}')
        except Exception as e:
            print(f'[Downloader] GCS cookies check failed: {e}')

    if not cookies_path:
        print(f'[Downloader] WARNING: No matching cookie file found for this proxy. Proceeding without cookies (Risk of 403).')

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
        'proxy': proxy_url, # Use the selected proxy from rotation logic
        
        # Anti-Bot Strategy (Client spoofing saja, tanpa bgutil)
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'default']
            }
        },
        
        'logger': CustomLogger(),
        'progress_hooks': [my_hook],
        'cookiefile': cookies_path,
        'nocheckcertificate': True,
        'noplaylist': True,
        'verbose': True,
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
        if cookies_path and os.path.exists(cookies_path) and 'cookies_' in cookies_path:
            try:
                os.remove(cookies_path)
            except OSError:
                pass
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

    # Cleanup temporary cookie file to prevent /tmp from filling up
    if cookies_path and os.path.exists(cookies_path) and 'cookies_' in cookies_path:
        try:
            os.remove(cookies_path)
        except OSError:
            pass

    return {
        'video_path': actual_video,
        'subtitle_path': actual_sub,
        'metadata': metadata,
    }
