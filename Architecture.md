# Project: Viral-Aware Clipper (ClipperApp)

## Status Saat Ini
MVP — sudah jalan lokal, belum production-ready.  
Supports: Windows (local), Google Colab (remote).

---

## Stack

### Backend (Python 3.11)
| Library | Versi | Fungsi |
|---------|-------|--------|
| Flask | ≥3.0 | REST API + SSE streaming |
| flask-cors | — | CORS untuk frontend dev server |
| OpenAI SDK | ≥1.0 | GPT-4o-mini (highlight analysis) + TTS (hook voiceover) |
| Whisper (openai-whisper) | small model | Single-pass transcription, word-level timestamps |
| yt-dlp | latest | YouTube download + auto-subtitle extraction |
| FFmpeg / FFprobe | system | Clipping, reframing, caption burn, audio extraction |
| OpenCV (cv2) | ≥4.8 | Frame processing, scene detection, crop rendering |
| MediaPipe | ≥0.10 | FaceMesh — active speaker detection + face center tracking |
| NumPy | ≥1.24 | Frame diff computation (scene detection) |
| Pillow | ≥10.0 | Text rendering pada hook scene |
| Playwright | ≥1.40 | Headless Chromium — CSS caption frame rendering |
| PyTorch | ≥2.0 | Whisper backend (CUDA jika ada GPU) |
| python-dotenv | ≥1.0 | Environment variable management |

### Frontend (React 19 + Vite 8)
| Library | Fungsi |
|---------|--------|
| React 19 | UI framework |
| Vite 8 | Dev server + bundler |
| Tailwind CSS v4 | Utility-first styling |
| Radix UI | Accessible primitives (Dialog, Separator, Slot) |
| Shadcn UI (manual) | Button, Badge, Card, Input, Separator, Dialog |
| Lucide React | Icon system |
| Sonner | Toast notifications |
| class-variance-authority + clsx + tailwind-merge | Component variant system |

### System Dependencies
| Tool | Fungsi |
|------|--------|
| FFmpeg + FFprobe | Video processing pipeline |
| NVIDIA GPU (opsional) | h264_nvenc encoding, CUDA untuk Whisper/PyTorch |
| Conda | Environment management (`clipperapp` env) |

---

## Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────┐
│                    Frontend (Vite :5173)                  │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  │
│  │HomeLayout│  │  Editor  │  │ Preview │  │ Timeline │  │
│  │  (home)  │  │  Layout  │  │(video+  │  │(segments │  │
│  │          │  │(Clipper/ │  │ caption │  │ + scrub) │  │
│  │          │  │ Editor)  │  │ overlay)│  │          │  │
│  └──────────┘  └──────────┘  └─────────┘  └──────────┘  │
│                      │ Sidebar (Captions/AI Enhance)     │
└──────────────────────┼───────────────────────────────────┘
                       │ HTTP + SSE
┌──────────────────────┼───────────────────────────────────┐
│               Backend Flask (:5000)                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │                    app.py                          │  │
│  │  /api/start      → Pipeline (threading)            │  │
│  │  /api/progress   → SSE streaming                   │  │
│  │  /api/clips      → Clip metadata                   │  │
│  │  /api/transcript  → Source transcript (filter)     │  │
│  │  /api/export     → Render pipeline (threading)     │  │
│  │  /api/save_editor → Editor state persistence       │  │
│  │  /api/presets    → Caption preset configs          │  │
│  └────────────────────────────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────┼───────────────────────────────┐  │
│  │              core/ modules                         │  │
│  │  pipeline.py      — Orchestrator                   │  │
│  │  downloader.py    — yt-dlp wrapper                 │  │
│  │  analyzer.py      — GPT-4o-mini highlight finder   │  │
│  │  clipper.py       — FFmpeg segment extraction      │  │
│  │  reframer.py      — 16:9→9:16 + face tracking     │  │
│  │  hook_generator.py — TTS + intro scene             │  │
│  │  caption_generator.py — Whisper + HTML captions    │  │
│  │  html_caption_renderer.py — Playwright frame gen   │  │
│  │  gpu_utils.py     — NVIDIA/AMD/CPU encoder detect  │  │
│  │  captions/        — Preset system (CSS + JSON)     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Pipeline Flow

### Phase 1: Analysis (Non-destructive)
```
1. Download      yt-dlp → source.mp4 + subtitles.srt + source.info.json
                 ├─ H.264 forced (GPU-decodable)
                 ├─ Multi-strategy with fallback (default → web_creator → remote EJS)
                 └─ Resume support (skip if source.mp4 exists)

2. Transcribe    SRT available? → parse_srt()
                 No SRT?        → Whisper small (full video → timestamped text)

3. Analyze       GPT-4o-mini → identify N best highlights
                 ├─ Input: timestamped transcript 
                 ├─ Output: [{start_time, end_time, title, hook_text, tags, ...}]
                 └─ Validation: duration within [min*0.8, max*1.2]

4. Save          session.json (project root) + meta.json (per clip dir)
                 └─ NO physical clipping yet — deferred rendering
```

### Phase 2: Editor (Interactive)
```
5. Clipper Tab   User adjusts clip start/end on full source timeline
                 ├─ Bounds saved to meta.json via auto-save
                 ├─ Transcript cleared → re-filtered pada next fetch
                 └─ Preview uses source.mp4 with seek (no re-encode)

6. Editor Tab    User splits into segments, adjusts crop per segment
                 ├─ Segment state: [{id, start, end, crop_x, crop_y, crop_z}]
                 ├─ Face tracking: MediaPipe per-frame or user manual drag
                 ├─ Caption preview: React overlay with word-level sync
                 └─ Auto-save ke editor_state.json (per clip)
```

### Phase 3: Export (Destructive rendering)
```
7. Clip          FFmpeg: source.mp4 → raw clip (start/end cut)
                 └─ GPU encoding (h264_nvenc) if available

8. Reframe       16:9 → 9:16 portrait
                 ├─ Mode: static (user crop_x) | mediapipe (face lock) | segments (multi-position)
                 ├─ Blurred background fill for letterbox areas
                 ├─ Per-frame crop via OpenCV → rawvideo pipe → FFmpeg encode
                 └─ Zoom support via crop_z parameter

9. Hook          (Optional) TTS voiceover + blurred intro scene
                 ├─ OpenAI TTS API → hook audio MP3
                 ├─ First frame → blur + dim + PIL text overlay → static hook video
                 └─ FFmpeg concat: hook + clip

10. Captions     (Optional) Word-by-word karaoke-style captions
                 ├─ Source: source_transcript.json (single-pass, filtered by bounds)
                 ├─ Timestamp offset: absolute → relative (auto-detected)
                 ├─ Preset system: karaoke | explosive | hype | word-focus | none
                 ├─ HTML + CSS + JS → Playwright screenshot per frame (30fps)
                 └─ FFmpeg overlay: PNG sequence + clip → final output
```

---

## Highlight Scoring Strategy

Scoring dilakukan oleh **GPT-4o-mini** (bukan weighted composite manual). Model menerima full transcript dan diminta memilih N highlight berdasarkan kriteria:

| Signal | Deskripsi |
|--------|-----------|
| 🎯 Punchlines | Funny moments, surprising reveals |
| 💡 Insights | Interesting/valuable information |
| 😢 Emotion | Dramatic or emotional moments |
| 💬 Quotes | Memorable one-liners |
| 📖 Story Arc | Complete mini-narratives with beginning/end |
| ⏱ Duration | Constrained to configurable min/max (default 30-90s) |
| 🚫 Overlap | Clips must not overlap |

**Bukan** single-signal scoring — GPT mempertimbangkan composite of all signals secara implisit.

> **Catatan**: Ini belum menggunakan explicit weighted scoring. Jika ingin lebih deterministic dan reproducible, bisa di-migrate ke embedding-based scoring + heuristic signals (speech rate, silence gaps, sentiment peaks). Tapi untuk MVP, GPT cukup reliabel.

---

## Data Layout (Per Project)

```
workspace/
└── {slug}--{job_id}/
    ├── source.mp4                    # Downloaded video (H.264)
    ├── source.info.json              # yt-dlp metadata
    ├── subtitles.srt                 # Auto-downloaded captions
    ├── source_transcript.json        # ← NEW: Full Whisper transcript (transcribe once)
    ├── session.json                  # Pipeline config + original clip list
    ├── cookies.txt                   # (optional) YouTube auth
    │
    └── clips/
        ├── clip_01/
        │   ├── meta.json             # Clip metadata (start, end, title, tags...)
        │   ├── editor_state.json     # Persisted editor state (segments, caption settings)
        │   ├── transcript.json       # (legacy, ignored) Old per-clip transcript
        │   └── exports/
        │       ├── clip_01_v1713600000.mp4   # Timestamped exports
        │       └── clip_01_v1713603600.mp4
        │
        ├── clip_02/
        │   ├── meta.json
        │   ├── editor_state.json
        │   └── exports/
        │       └── ...
        └── ...
```

---

## Frontend Arsitektur

### Component Tree
```
App
├── HomeLayout                    # Project list + URL input + pipeline progress
│   └── (clips grid + clip cards)
│
└── EditorLayout                  # Full NLE workspace
    ├── Header (mode toggle: Clipper/Editor, save, export)
    ├── Main Split
    │   ├── Left Panel            # Transcript (Editor mode only)
    │   ├── Center Panel          # Preview (video + caption overlay)
    │   │   └── Preview.jsx       # <video> + viewfinder + draggable crop
    │   ├── Right Panel           # Sidebar (caption presets, font, AI tools)
    │   │   └── Sidebar.jsx
    │   └── Nav Ribbon            # Tab navigation (Editor mode only)
    │
    └── Bottom Panel              # Timeline
        └── Timeline.jsx          # Frame thumbnails + segments + playhead + ruler
```

### State Management
- **Lokal React state** (useState/useRef) — tidak pakai Redux/Zustand
- Auto-save: debounced 2s ke `/api/save_editor` pada perubahan segments/captionSettings
- Cross-component sync: props drilling dari EditorLayout ke child components

### Design System
- **Theme**: Shadcn Neutral (dark mode, high contrast)
- **CSS Variables**: `--background`, `--foreground`, `--card`, `--primary`, `--border`, dll.
- **Custom CSS**: `EditorNLE.css` untuk timeline & NLE-specific components
- **Base CSS**: `index.css` untuk layout grid, header, cards, progress bars

---

## Keputusan Desain yang Sudah Fixed (Jangan Diubah)

1. **Single-pass transcript** — Whisper dipanggil sekali per source video, di-cache sebagai `source_transcript.json`. Semua operasi transcript (editor preview, resize, export) filter dari cache ini.

2. **Deferred rendering** — Pipeline `run()` HANYA melakukan analysis (download + transcribe + GPT). Physical clipping/reframing/captioning baru terjadi saat user klik Export.

3. **Source-relative timestamps** — Semua word timestamps bersifat absolute terhadap `source.mp4`. Offset ke clip-local time dilakukan hanya saat caption rendering.

4. **GPU-adaptive encoding** — Auto-detect: h264_nvenc → h264_mf → h264_amf → libx264. Decoding selalu CPU (hemat VRAM).

5. **Per-clip directory layout** — Setiap clip punya folder sendiri (`clips/clip_NN/`) dengan meta.json, editor_state.json, dan exports/.

6. **HTML+CSS caption rendering** — Bukan ASS/SRT burn. Menggunakan Playwright headless browser untuk screenshot setiap frame, lalu FFmpeg overlay. Ini memberikan full CSS styling power (gradients, shadows, transforms, custom fonts).

7. **Caption preset system** — Presets defined sebagai JSON + CSS di `core/captions/presets/{name}/`. Extensible tanpa code change.

---

## Yang BELUM Ada (Prioritas)

- [ ] **Job queue** — Saat ini pakai `threading.Thread(daemon=True)`. Tidak ada retry, tidak ada persistence, race condition mungkin terjadi.
- [ ] **Structured logging** — Masih `print()` statements. Perlu proper logging dengan levels + file output.
- [ ] **Database untuk hasil** — Semua state disimpan sebagai JSON files di filesystem. Tidak ada index, tidak ada query capability.
- [ ] **Error handling per stage** — Pipeline gagal = seluruh job gagal. Tidak ada partial recovery atau stage retry.
- [ ] **Authentication** — Zero auth. Siapa saja bisa akses API.
- [ ] **Rate limiting** — Tidak ada protection terhadap API abuse.
- [ ] **Whisper model selection** — Hardcoded ke `small`. Seharusnya configurable (tiny/base/small/medium/large).
- [ ] **Concurrent exports** — Export ID pakai `{job_id}-export` (fixed), jadi hanya 1 export per project at a time.
- [ ] **Tests** — Zero unit tests, zero integration tests.
- [ ] **Docker** — Belum ada containerization.

---

## Keputusan yang Masih Terbuka

### Queue System
| Option | Pro | Con |
|--------|-----|-----|
| **RQ (Redis Queue)** | Simple, Python-native, lightweight | Butuh Redis server |
| **Celery** | Battle-tested, monitoring (Flower), retry built-in | Heavy, complex config |
| **BullMQ** | Jika mau pindah ke Node backend | Beda ecosystem |
| **Dramatiq** | Simple like RQ, tapi lebih modern | Smaller community |

**Rekomendasi**: RQ untuk MVP → Celery kalau scale.

### Database
| Option | Pro | Con |
|--------|-----|-----|
| **SQLite** | Zero setup, file-based, cocok untuk single-server | Concurrent writes terbatas |
| **PostgreSQL** | Production-grade, full SQL, concurrent | Butuh setup terpisah |

**Rekomendasi**: SQLite dulu (via SQLAlchemy ORM) → migrasi PostgreSQL kalau multi-user.

### Deployment
| Option | Status |
|--------|--------|
| Google Colab | ✅ Supported (setup_colab.sh + run_colab.py + cloudflared tunnel) |
| Local Windows | ✅ Supported (run_local.py + Conda) |
| Docker | ❌ Belum ada |
| Cloud VM (GCP/AWS) | ❌ Belum ada |

---

## Port Map
| Service | Port | Catatan |
|---------|------|---------|
| Flask API | 5000 | Backend REST + SSE |
| Vite Dev Server | 5173 | Frontend hot-reload |
| Cloudflared (Colab) | Tunnel | Public URL untuk Colab deployment |
