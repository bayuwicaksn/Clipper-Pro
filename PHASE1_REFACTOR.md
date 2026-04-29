# Phase 1 Refactor — Clipper-Pro
## Instruksi untuk Coding Agent

---

## KONTEKS

Repo: https://github.com/bayuwicaksn/Clipper-Pro
Stack saat ini: FastAPI (root) + React (frontend/) + semua file berserakan di root
Target: Pisah menjadi backend/ + worker_gpu/ + worker_node/ + shared/

**PENTING:** Phase 1 hanya memindahkan dan membuat file baru.
TIDAK mengubah logic apapun. TIDAK mengubah kode yang sudah berjalan.

---

## RULES UNTUK AGENT

1. Baca seluruh instruksi ini sebelum mulai
2. Kerjakan BERURUTAN sesuai nomor step
3. Setiap step harus SELESAI dan VERIFIED sebelum lanjut ke step berikutnya
4. Jangan ubah isi file yang dipindah — hanya pindahkan
5. Update import path HANYA jika file dipindah ke lokasi berbeda
6. Jangan hapus file lama sampai Step 6

---

## STEP 1 — Buat Struktur Folder Baru

Jalankan command berikut dari root repo:

```bash
# Backend
mkdir -p backend/api
mkdir -p backend/core
mkdir -p backend/db

# Worker GPU
mkdir -p worker_gpu/tasks
mkdir -p worker_gpu/core

# Worker Node
mkdir -p worker_node/src/caption

# Shared
mkdir -p shared

# Infra
mkdir -p infra
mkdir -p .github/workflows
```

VERIFY: Pastikan semua folder ada dengan `find . -type d | grep -v node_modules | grep -v .git`

---

## STEP 2 — Buat File `__init__.py` di Semua Folder Python

```bash
touch backend/__init__.py
touch backend/api/__init__.py
touch backend/core/__init__.py
touch backend/db/__init__.py

touch worker_gpu/__init__.py
touch worker_gpu/tasks/__init__.py
touch worker_gpu/core/__init__.py

touch worker_node/__init__.py

touch shared/__init__.py
```

VERIFY: `find . -name "__init__.py" | grep -v node_modules`

---

## STEP 3 — Buat requirements.txt untuk Setiap Service

### 3A. backend/requirements.txt
Buat file `backend/requirements.txt` dengan isi berikut.
JANGAN copy dari root requirements.txt — tulis dari awal:

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
sqlmodel>=0.0.16
supabase>=2.4.0
google-cloud-pubsub>=2.21.0
google-cloud-storage>=2.16.0
python-dotenv>=1.0.0
pydantic>=2.6.0
pydantic-settings>=2.2.0
python-multipart>=0.0.9
httpx>=0.27.0
sse-starlette>=2.0.0
```

### 3B. worker_gpu/requirements.txt
Buat file `worker_gpu/requirements.txt`:

```
# PyTorch CPU only (lebih kecil, cukup untuk mediapipe)
# Ganti dengan cu121 jika butuh CUDA penuh
--extra-index-url https://download.pytorch.org/whl/cpu
torch>=2.2.0
torchvision>=0.17.0

# AI & ML
mediapipe>=0.10.11
opencv-python-headless>=4.9.0
openai-whisper>=20231117
google-generativeai>=0.5.0
openai>=1.23.0

# Video Processing
yt-dlp>=2024.4.9
ffmpeg-python>=0.2.0

# GCP
google-cloud-pubsub>=2.21.0
google-cloud-storage>=2.16.0

# Utils
python-dotenv>=1.0.0
pydantic>=2.6.0
httpx>=0.27.0
numpy>=1.26.0
```

### 3C. worker_node/requirements.txt
Buat file `worker_node/requirements.txt`:

```
# Minimal — hanya perlu consume Pub/Sub dan trigger hyperframes
google-cloud-pubsub>=2.21.0
google-cloud-storage>=2.16.0
python-dotenv>=1.0.0
httpx>=0.27.0
pydantic>=2.6.0
```

### 3D. shared/requirements.txt
Buat file `shared/requirements.txt`:

```
pydantic>=2.6.0
google-cloud-pubsub>=2.21.0
google-cloud-storage>=2.16.0
python-dotenv>=1.0.0
```

VERIFY: Pastikan 4 file requirements.txt ada:
```bash
ls backend/requirements.txt worker_gpu/requirements.txt worker_node/requirements.txt shared/requirements.txt
```

---

## STEP 4 — Buat shared/models.py

Buat file `shared/models.py` dengan isi:

```python
"""
Shared Pydantic models — digunakan oleh backend, worker_gpu, dan worker_node.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    CLIPPING = "clipping"
    CAPTIONING = "captioning"
    UPLOADING = "uploading"
    DONE = "done"
    FAILED = "failed"


class HighlightSegment(BaseModel):
    start_time: str          # HH:MM:SS.mmm
    end_time: str            # HH:MM:SS.mmm
    title: str
    hook_text: str
    hook_score: int          # 0-100
    description: str
    tags: List[str]
    duration_seconds: Optional[float] = None


class JobPayload(BaseModel):
    """Payload yang dikirim ke Pub/Sub."""
    job_id: str
    video_url: str
    user_id: str
    settings: dict           # Caption settings dari editor
    config: dict             # AI config (model, min/max duration, dll)


class CaptionJobPayload(BaseModel):
    """Payload dari worker_gpu ke worker_node."""
    job_id: str
    clip_path: str           # GCS path ke video clip
    segment: HighlightSegment
    words: List[dict]        # Word timestamps dari Whisper
    settings: dict           # Caption settings
    output_path: str         # GCS path output final
```

VERIFY: `python3 -c "from shared.models import JobStatus, JobPayload; print('OK')"` dari root repo.
Jika error karena pydantic belum install, skip verify ini — akan ditest di Step 7.

---

## STEP 5 — Pindahkan File Caption ke worker_node

### 5A. Copy file caption generator
```bash
cp services/caption_generator.py worker_node/src/caption/generator.py
```

Jika file tidak ada di `services/caption_generator.py`, cari file yang berisi fungsi
`generate_caption_composition` dan `render_composition` di seluruh repo:
```bash
grep -rl "generate_caption_composition" . --include="*.py"
```
Lalu copy file tersebut ke `worker_node/src/caption/generator.py`

### 5B. Update import di generator.py
Buka `worker_node/src/caption/generator.py` dan JANGAN ubah apapun selain:
- Tidak perlu update import untuk Phase 1
- Hanya pastikan file berhasil dicopy

### 5C. Buat worker_node/src/caption/__init__.py
```bash
touch worker_node/src/caption/__init__.py
```

VERIFY:
```bash
ls -la worker_node/src/caption/
# Harus ada: __init__.py, generator.py
```

---

## STEP 6 — Pindahkan File Analyzer ke worker_gpu

### 6A. Copy analyzer
```bash
cp core/analyzer.py worker_gpu/core/analyzer.py
```

Jika tidak ada di `core/analyzer.py`, cari dengan:
```bash
grep -rl "analyze_highlights" . --include="*.py"
```

### 6B. Copy utils
```bash
cp core/utils.py worker_gpu/core/utils.py
```

Jika tidak ada, buat `worker_gpu/core/utils.py` dengan isi:
```python
"""
Utility functions untuk worker_gpu.
Dipindah dari core/utils.py
"""


def timestamp_to_seconds(ts: str) -> float:
    """
    Convert HH:MM:SS.mmm atau HH:MM:SS,mmm ke float seconds.
    
    Args:
        ts: Timestamp string format HH:MM:SS.mmm
    
    Returns:
        Float seconds
    """
    ts = ts.replace(',', '.')
    parts = ts.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def seconds_to_timestamp(seconds: float) -> str:
    """
    Convert float seconds ke HH:MM:SS.mmm format.
    
    Args:
        seconds: Float seconds
    
    Returns:
        Timestamp string HH:MM:SS.mmm
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
```

### 6C. Update import di worker_gpu/core/analyzer.py
Buka `worker_gpu/core/analyzer.py` dan cari baris:
```python
from core.utils import timestamp_to_seconds
```
Ganti dengan:
```python
from worker_gpu.core.utils import timestamp_to_seconds
```

VERIFY:
```bash
ls -la worker_gpu/core/
# Harus ada: __init__.py, analyzer.py, utils.py
```

---

## STEP 7 — Buat .env.example di Root

Buat file `.env.example`:

```bash
# ─── Supabase ───────────────────────────────────────────
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# ─── GCP ────────────────────────────────────────────────
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=asia-southeast1

# Pub/Sub Topics
PUBSUB_TOPIC_JOBS=clipper-jobs
PUBSUB_TOPIC_CAPTION=clipper-caption-jobs
PUBSUB_SUBSCRIPTION_JOBS=clipper-jobs-sub
PUBSUB_SUBSCRIPTION_CAPTION=clipper-caption-jobs-sub

# Cloud Storage
GCS_BUCKET=clipper-pro-outputs
GCS_TEMP_BUCKET=clipper-pro-temp

# ─── AI Keys ────────────────────────────────────────────
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key

# ─── Worker Config ───────────────────────────────────────
WHISPER_MODEL=medium
# Options: tiny, base, small, medium, large
# tiny = fastest, least accurate
# medium = good balance
# large = most accurate, slowest

GPU_ENABLED=true
# Set false untuk CPU-only mode

# ─── App Config ─────────────────────────────────────────
ENVIRONMENT=development
# Options: development, production

LOG_LEVEL=INFO
```

VERIFY: `ls .env.example`

---

## STEP 8 — Buat .gitignore (jika belum ada atau update)

Pastikan `.gitignore` berisi minimal:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
*.egg
.venv/
venv/
env/

# Environment
.env
.env.local
.env.*.local

# Node
node_modules/
frontend/dist/
frontend/.vite/

# Output
outputs/
tmp/
temp/
*.mp4
*.mov
*.mp3
*.wav

# GCP credentials
*-credentials.json
service-account*.json

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

---

## STEP 9 — Verifikasi Struktur Final

Jalankan command ini dan pastikan output sesuai:

```bash
find . -type f -name "*.py" | grep -v node_modules | grep -v .git | grep -v __pycache__ | sort
```

Output yang diharapkan minimal:
```
./backend/__init__.py
./backend/api/__init__.py
./backend/core/__init__.py
./backend/db/__init__.py
./shared/__init__.py
./shared/models.py
./worker_gpu/__init__.py
./worker_gpu/core/__init__.py
./worker_gpu/core/analyzer.py
./worker_gpu/core/utils.py
./worker_gpu/tasks/__init__.py
./worker_node/__init__.py
./worker_node/src/caption/__init__.py
./worker_node/src/caption/generator.py
```

Dan pastikan file lama MASIH ADA (belum dihapus):
```bash
ls core/ api/ services/ 2>/dev/null || echo "Folder lama tidak ada — skip"
```

---

## STEP 10 — Buat Ringkasan Perubahan

Setelah semua step selesai, buat file `PHASE1_DONE.md` di root:

```markdown
# Phase 1 Complete

## Yang sudah dikerjakan:
- [x] Struktur folder baru dibuat
- [x] requirements.txt dipecah menjadi 4 file
- [x] shared/models.py dibuat
- [x] worker_gpu/core/analyzer.py (copy dari core/analyzer.py)
- [x] worker_gpu/core/utils.py (copy dari core/utils.py)
- [x] worker_node/src/caption/generator.py (copy dari services/)
- [x] .env.example dibuat
- [x] .gitignore diupdate

## Yang BELUM dikerjakan (Phase 2):
- [ ] Dockerfile worker_gpu
- [ ] Dockerfile worker_node
- [ ] Dockerfile backend
- [ ] Dockerfile frontend + nginx.conf
- [ ] docker-compose.yml
- [ ] Pub/Sub integration
- [ ] backend/main.py (entry point baru)
- [ ] worker_gpu/worker.py (entry point)
- [ ] worker_node/worker.py (entry point)

## File lama yang masih ada (akan dihapus di Phase 3):
- core/ (lama)
- api/ (lama)
- services/ (lama)
- app.py (lama)
- requirements.txt (root, lama)
```

---

## CHECKLIST FINAL UNTUK AGENT

Sebelum selesai, verifikasi semua ini:

```
[ ] mkdir semua folder berhasil
[ ] semua __init__.py ada
[ ] backend/requirements.txt ada dan berisi fastapi, uvicorn, dll
[ ] worker_gpu/requirements.txt ada dan berisi torch, mediapipe, dll
[ ] worker_node/requirements.txt ada dan berisi google-cloud-pubsub
[ ] shared/requirements.txt ada
[ ] shared/models.py ada dan valid Python syntax
[ ] worker_gpu/core/analyzer.py ada (copy dari lama)
[ ] worker_gpu/core/utils.py ada
[ ] worker_node/src/caption/generator.py ada (copy dari lama)
[ ] .env.example ada
[ ] .gitignore diupdate
[ ] PHASE1_DONE.md ada
[ ] File lama (core/, api/, services/) MASIH ADA, belum dihapus
```

---

## JIKA ADA ERROR

### Import Error setelah copy file
Solusi: Ini normal di Phase 1. Import akan diperbaiki di Phase 2.
Jangan fix import yang butuh refactor besar.

### File tidak ditemukan saat copy
Solusi: Gunakan grep untuk cari file yang benar:
```bash
grep -rl "FUNCTION_NAME" . --include="*.py" | grep -v __pycache__
```

### Permission denied
Solusi:
```bash
chmod +x script.sh
# atau
sudo chown -R $USER .
```

---

**END OF PHASE 1 INSTRUCTIONS**
