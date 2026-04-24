# ClipperApp Project Structure

This document outlines the project structure and the purpose of key directories and files.

```text
clipperApp/
├── app.py                  # Flask entry point (~57 lines, mounts blueprints)
├── api/                    # Modular API Blueprints
│   ├── __init__.py         # Shared state (jobs, queues, helpers)
│   ├── projects.py         # Project CRUD, clip listing
│   ├── media.py            # Video streaming, downloads, thumbnails
│   ├── pipeline.py         # Processing jobs, export, SSE progress
│   ├── editor.py           # Editor state save/load, transcript API
│   └── ai.py               # Caption presets, scene detection, face tracking
├── core/                   # Backend Processing Engine
│   ├── pipeline.py         # Main Orchestrator
│   ├── analyzer.py         # AI Logic (GPT/Gemini)
│   ├── caption_generator.py # Transcription & Burn-in
│   ├── reframer.py         # AI Portrait Reframe
│   └── ...                 # Helpers (GPU, HTML Render, etc.)
├── deploy/                 # Deployment Configs
│   └── gcp/                # GCP-specific scripts
│       ├── provision.sh    # VM creation & firewall
│       ├── setup.sh        # Dependency installation
│       └── schedule.sh     # Auto start/stop for cost savings
├── run_local.py            # Local Dev Launcher
├── requirements.txt        # Python Dependencies
├── .env                    # API Keys & Secrets
├── frontend/               # React + Tailwind v4 Application
│   ├── src/
│   │   ├── components/     # Editor, Timeline, Preview, etc.
│   │   ├── index.css       # Global Design System
│   │   └── App.jsx         # UI Entry Point
├── static/                 # Static Assets for Flask
├── workspace/              # Processed Data (Job Folders)
│   └── <job_id>/           # Unique Project Folder
│       ├── source.mp4      # Downloaded Original
│       ├── session.json    # AI Analysis & Highlights
│       └── clips/          # Edited Clip Folders
│           └── clip_01/    # Sub-folder for each clip
│               ├── meta.json    # Edit State (Trim, Style)
│               └── exports/     # Final Rendered Videos
```

## Root Directory
- `app.py`: Slim Flask entry point that mounts all blueprint modules.
- `api/`: Modular API route handlers, organized by domain.
- `run_local.py`: Launcher script for local development.
- `requirements.txt`: Python dependencies.
- `.env`: Environment variables (OpenAI keys, etc.).
- `workspace/`: Data directory where all processed videos, clips, and metadata are stored.

## API Blueprints (`api/`)
Route handlers organized by domain responsibility.
- `__init__.py`: Shared state (jobs dict, progress queues) and helper functions.
- `projects.py`: Project listing, deletion, clip metadata retrieval.
- `media.py`: Video streaming, download, thumbnail generation, export file management.
- `pipeline.py`: Pipeline job processing, export rendering, SSE progress streaming.
- `editor.py`: Editor state persistence, transcript API (get/save).
- `ai.py`: Caption preset management, AI clip regeneration, face tracking, scene detection.

## Backend Core (`core/`)
The processing engine — 10 focused modules, each with a single responsibility.

**Orchestration:**
- `pipeline.py` (300 lines): Main orchestrator. `run()` for full analysis, `export_single_clip()` for rendering.
- `utils.py` (174 lines): Shared helpers — logging, timestamps, transcript I/O.
- `gpu_utils.py` (149 lines): GPU/encoder auto-detection (NVENC, AMF, MF, CPU fallback).

**Ingest:**
- `downloader.py` (260 lines): YouTube download via yt-dlp with multi-strategy fallback and cookie support.

**AI & Analysis:**
- `analyzer.py` (392 lines): GPT-4o/Gemini highlight detection with timestamp snapping and de-overlap.
- `caption_generator.py` (247 lines): pycaps-powered karaoke captions + Whisper API transcription.

**Video Processing:**
- `reframer.py` (517 lines): 16:9 → 9:16 portrait crop with face tracking (MediaPipe/OpenCV/manual segments).
- `clipper.py` (84 lines): FFmpeg-based segment extraction with GPU-accelerated encoding.
- `hook_generator.py` (203 lines): TTS voiceover (OpenAI) + blurred intro scene generation.

## Frontend (`frontend/`)
Vite + React + Tailwind CSS v4 application.
- `src/App.jsx`: Main entry point and routing logic.
- `src/components/`:
    - `HomeLayout.jsx`: Project library, settings panel, and new project creation.
    - `EditorLayout.jsx`: The main NLE (Non-Linear Editor) interface.
    - `Timeline.jsx`: Multi-layer timeline for trimming and caption timing.
    - `Preview.jsx`: Real-time video preview with synchronized caption rendering.
    - `Sidebar.jsx`: Navigation and export management.
- `src/index.css`: Core design system and Tailwind v4 utilities.

## Data Structure (`workspace/<job_id>/`)
- `source.mp4`: The original downloaded video.
- `source_transcript.json`: Full word-level transcript of the source.
- `session.json`: Core project metadata and list of detected highlights.
- `clips/clip_XX/`:
    - `meta.json`: Clip-specific settings (trim, zoom, captions).
    - `segments/`: Raw video slices for editing.
    - `exports/`: Final rendered video files.
