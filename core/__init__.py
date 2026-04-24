"""
ClipperApp Core — Processing Engine

Modules:
    utils           — Shared helpers: logging, timestamps, transcript I/O
    gpu_utils       — GPU/encoder auto-detection (NVENC, AMF, MF, CPU fallback)
    pipeline        — Main orchestrator: run() for analysis, export_single_clip() for render
    downloader      — YouTube video download via yt-dlp (multi-strategy + cookie support)
    analyzer        — AI-powered highlight detection (GPT-4o / Gemini)
    clipper         — FFmpeg-based segment extraction (GPU-accelerated encoding)
    reframer        — 16:9 → 9:16 portrait crop with face tracking (MediaPipe/OpenCV)
    caption_generator — pycaps-powered karaoke captions + Whisper transcription
    hook_generator  — TTS voiceover + blurred intro scene generation
"""
