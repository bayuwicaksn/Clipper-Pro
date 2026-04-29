"""
ClipperApp Core â€” Processing Engine

Modules:
    utils           â€” Shared helpers: logging, timestamps, transcript I/O
    gpu_utils       â€” GPU/encoder auto-detection (NVENC, AMF, MF, CPU fallback)
    pipeline        â€” Main orchestrator: run() for analysis, export_single_clip() for render
    downloader      â€” YouTube video download via yt-dlp (multi-strategy + cookie support)
    analyzer        â€” AI-powered highlight detection (GPT-4o / Gemini)
    clipper         â€” FFmpeg-based segment extraction (GPU-accelerated encoding)
    reframer        â€” 16:9 â†’ 9:16 portrait crop with face tracking (MediaPipe/OpenCV)
    caption_generator â€” pycaps-powered karaoke captions + Whisper transcription
    hook_generator  â€” TTS voiceover + blurred intro scene generation
"""
