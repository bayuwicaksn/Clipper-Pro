# Phase 2 — Dockerfiles + Entry Points + docker-compose
## Instruksi untuk Coding Agent

---

## KONTEKS

Lanjutan dari Phase 1. Semua folder sudah ada.
Phase 2 membuat:
1. Dockerfile untuk setiap service
2. nginx.conf untuk frontend
3. Entry point worker_gpu/worker.py
4. Entry point worker_node/worker.py
5. backend/main.py (entry point baru)
6. docker-compose.yml untuk development lokal

**PENTING:**
- Jangan ubah file lama (core/, api/, services/, app.py)
- File lama masih dipakai sampai Phase 3
- Phase 2 hanya menambah file baru

---

## RULES UNTUK AGENT

1. Kerjakan BERURUTAN sesuai nomor step
2. Setiap Dockerfile harus bisa di-build tanpa error
3. Test setiap Dockerfile dengan `docker build` sebelum lanjut
4. Jangan skip step verifikasi

---

## STEP 1 — Dockerfile Frontend (React + Vite + Nginx)

Buat file `frontend/Dockerfile`:

```dockerfile
# ── Stage 1: Build React ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files dulu (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy source
COPY . .

# Build production
# Vite output ke dist/, CRA output ke build/
RUN npm run build

# ── Stage 2: Serve dengan Nginx ───────────────────────────────────────
FROM nginx:1.25-alpine

# Copy build output
# Vite: dist/ | CRA: build/
# Ganti 'dist' dengan 'build' jika pakai Create React App
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

Buat file `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # React Router — semua route ke index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy ke backend API
    # GANTI backend-service-url dengan URL Cloud Run backend
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE support (untuk progress streaming)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

VERIFY:
```bash
cd frontend && docker build -t clipper-frontend . && echo "Frontend OK"
```

---

## STEP 2 — Dockerfile Backend (FastAPI)

Buat file `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dulu (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy shared models
COPY ../shared /app/shared

# Copy backend source
COPY . .

# Create non-root user (security best practice)
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Buat file `backend/main.py` (entry point baru):

```python
"""
Backend Entry Point — FastAPI
Clipper-Pro Backend API

Sementara ini re-export dari app.py lama sampai Phase 3 selesai.
"""

import sys
import os

# Tambahkan root ke path agar bisa import dari app.py lama
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Re-export app dari root app.py
# Ini SEMENTARA — akan diganti di Phase 3 dengan implementasi proper
try:
    from app import app
    print("[Backend] Loaded app from root app.py")
except ImportError as e:
    print(f"[Backend] Warning: Could not import from root app.py: {e}")
    print("[Backend] Creating minimal app for testing...")

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Clipper-Pro API", version="0.1.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "phase": "2"})

    @app.get("/")
    async def root():
        return JSONResponse({"message": "Clipper-Pro API Running"})
```

VERIFY:
```bash
cd backend && docker build -t clipper-backend . && echo "Backend OK"
```

---

## STEP 3 — Dockerfile worker_gpu (Python + ffmpeg + Whisper + MediaPipe)

Buat file `worker_gpu/Dockerfile`:

```dockerfile
# ── Base: Python + CUDA (jika GPU tersedia) ───────────────────────────
# Untuk Cloud Run L4 GPU, gunakan base image dengan CUDA
# Untuk CPU-only dev, gunakan python:3.11-slim
FROM python:3.11-slim

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    # Whisper model cache directory
    WHISPER_CACHE=/app/.cache/whisper \
    # OpenCV headless mode
    OPENCV_IO_ENABLE_OPENEXR=0

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ffmpeg untuk video processing
    ffmpeg \
    # OpenCV dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # yt-dlp dependencies
    curl \
    wget \
    # General utils
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create cache directory untuk Whisper model
RUN mkdir -p /app/.cache/whisper

# Copy requirements
COPY requirements.txt .

# Install PyTorch CPU dulu (bisa diganti cu121 untuk CUDA)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch \
        torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Install remaining requirements
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model saat build (bukan saat runtime)
# Ganti 'medium' sesuai kebutuhan: tiny/base/small/medium/large
RUN python3 -c "import whisper; whisper.load_model('medium')" && \
    echo "Whisper model pre-downloaded OK"

# Copy shared models
COPY ../shared /app/shared

# Copy worker source
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos "" workeruser && \
    chown -R workeruser:workeruser /app
USER workeruser

# Health check — cek apakah worker process berjalan
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
  CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Entry point
CMD ["python3", "worker.py"]
```

Buat file `worker_gpu/worker.py` (entry point):

```python
"""
Worker GPU — Entry Point
Clipper-Pro Video Processing Worker

Consume jobs dari Pub/Sub dan proses:
1. Download video (yt-dlp)
2. Transcribe audio (Whisper)
3. Analyze highlights (Gemini/OpenAI)
4. Extract clips (ffmpeg)
5. Push caption job ke Pub/Sub worker_node
"""

import os
import sys
import json
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_gpu")


def process_job(job_data: dict) -> None:
    """
    Proses satu job dari Pub/Sub.
    
    Ini adalah placeholder — implementasi penuh di Phase 3.
    """
    job_id = job_data.get("job_id", "unknown")
    logger.info(f"[Job {job_id}] Starting processing...")

    try:
        # Phase 3 akan implement:
        # 1. from worker_gpu.tasks.download import download_video
        # 2. from worker_gpu.tasks.transcribe import transcribe_audio
        # 3. from worker_gpu.tasks.analyze import analyze_highlights
        # 4. from worker_gpu.tasks.clip import extract_clips
        # 5. Push ke caption Pub/Sub topic

        logger.info(f"[Job {job_id}] Placeholder — full implementation in Phase 3")

    except Exception as e:
        logger.error(f"[Job {job_id}] Failed: {e}", exc_info=True)
        raise


def pull_messages():
    """
    Pull messages dari Google Cloud Pub/Sub.
    Placeholder — implementasi penuh di Phase 3.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_JOBS", "clipper-jobs-sub")

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — running in demo mode")
        logger.info("Worker GPU ready, waiting for jobs...")

        # Demo loop
        while True:
            logger.info("Polling for jobs... (demo mode)")
            time.sleep(30)
        return

    try:
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)

        logger.info(f"Listening on {subscription_path}")

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                logger.info(f"Received job: {data.get('job_id')}")
                process_job(data)
                message.ack()
                logger.info(f"Job {data.get('job_id')} acknowledged")
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                message.nack()

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

        with subscriber:
            try:
                streaming_pull_future.result()
            except Exception as e:
                streaming_pull_future.cancel()
                raise

    except ImportError:
        logger.error("google-cloud-pubsub not installed")
        raise


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received, exiting gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Clipper-Pro GPU Worker Starting")
    logger.info(f"Whisper Model: {os.getenv('WHISPER_MODEL', 'medium')}")
    logger.info(f"GPU Enabled: {os.getenv('GPU_ENABLED', 'false')}")
    logger.info("=" * 50)

    # Handle graceful shutdown
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Start pulling
    pull_messages()
```

VERIFY:
```bash
cd worker_gpu && docker build -t clipper-worker-gpu . && echo "Worker GPU OK"
# CATATAN: Build ini lambat karena download Whisper model (~1.5GB untuk medium)
# Tambahkan --no-cache jika ada masalah cache
```

---

## STEP 4 — Dockerfile worker_node (Python + Node.js + Chromium)

Buat file `worker_node/Dockerfile`:

```dockerfile
# ── Base: Python + Node.js ────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    # Puppeteer/Chromium config
    PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    NODE_ENV=production

# Install Node.js + Chromium + dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Node.js
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends \
    nodejs \
    # Chromium untuk HyperFrames render
    chromium \
    # Chromium dependencies
    fonts-liberation \
    fonts-noto-color-emoji \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # ffmpeg untuk compositing akhir
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Verify Node.js installed
RUN node --version && npm --version

# Pre-install hyperframes globally (biar tidak download tiap run)
RUN npm install -g hyperframes 2>/dev/null || \
    npx -y hyperframes --version 2>/dev/null || \
    echo "hyperframes will be installed on first run"

# Copy Python requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy shared models
COPY ../shared /app/shared

# Copy worker source
COPY . .

# Create non-root user
# CATATAN: Chromium butuh user non-root untuk berjalan
RUN adduser --disabled-password --gecos "" nodeuser && \
    chown -R nodeuser:nodeuser /app
USER nodeuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
  CMD python3 -c "import sys; sys.exit(0)" || exit 1

CMD ["python3", "worker.py"]
```

Buat file `worker_node/worker.py` (entry point):

```python
"""
Worker Node — Entry Point
Clipper-Pro Caption Rendering Worker

Consume caption jobs dari Pub/Sub dan:
1. Generate HTML composition (HyperFrames + GSAP)
2. Render transparent MOV via headless Chromium
3. Composite caption overlay ke video
4. Upload hasil ke Cloud Storage
5. Update status di Supabase
"""

import os
import sys
import json
import logging
import signal
import time

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker_node")


def process_caption_job(job_data: dict) -> None:
    """
    Proses satu caption job.
    Placeholder — implementasi penuh di Phase 3.
    """
    job_id = job_data.get("job_id", "unknown")
    logger.info(f"[Job {job_id}] Starting caption rendering...")

    try:
        # Phase 3 akan implement:
        # from worker_node.src.caption.generator import generate_caption_composition
        # from worker_node.src.caption.generator import render_composition
        # from worker_node.src.caption.generator import composite_transparent_captions

        logger.info(f"[Job {job_id}] Placeholder — full implementation in Phase 3")

    except Exception as e:
        logger.error(f"[Job {job_id}] Failed: {e}", exc_info=True)
        raise


def pull_messages():
    """Pull messages dari Pub/Sub caption topic."""
    project_id = os.getenv("GCP_PROJECT_ID")
    subscription_id = os.getenv("PUBSUB_SUBSCRIPTION_CAPTION", "clipper-caption-jobs-sub")

    if not project_id:
        logger.warning("GCP_PROJECT_ID not set — running in demo mode")
        logger.info("Worker Node ready, waiting for caption jobs...")

        while True:
            logger.info("Polling for caption jobs... (demo mode)")
            time.sleep(30)
        return

    try:
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)

        logger.info(f"Listening on {subscription_path}")

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                logger.info(f"Received caption job: {data.get('job_id')}")
                process_caption_job(data)
                message.ack()
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                message.nack()

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

        with subscriber:
            try:
                streaming_pull_future.result()
            except Exception as e:
                streaming_pull_future.cancel()
                raise

    except ImportError:
        logger.error("google-cloud-pubsub not installed")
        raise


def handle_shutdown(signum, frame):
    logger.info("Shutdown signal received, exiting gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Clipper-Pro Node Worker Starting")

    # Verify Chromium tersedia
    chromium_path = os.getenv("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium")
    if os.path.exists(chromium_path):
        logger.info(f"Chromium found: {chromium_path}")
    else:
        logger.warning(f"Chromium not found at {chromium_path}")

    # Verify Node.js tersedia
    import subprocess
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        logger.info(f"Node.js: {result.stdout.strip()}")
    except Exception:
        logger.warning("Node.js not found in PATH")

    logger.info("=" * 50)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    pull_messages()
```

VERIFY:
```bash
cd worker_node && docker build -t clipper-worker-node . && echo "Worker Node OK"
# CATATAN: Build ini juga besar (~1GB) karena Chromium
```

---

## STEP 5 — docker-compose.yml untuk Development Lokal

Buat file `docker-compose.yml` di root:

```yaml
version: '3.9'

services:

  # ── Frontend React ──────────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

  # ── Backend FastAPI ─────────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
    volumes:
      # Hot reload untuk development
      - ./backend:/app
      - ./shared:/app/shared
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── Worker GPU ──────────────────────────────────────────────────────
  worker_gpu:
    build:
      context: ./worker_gpu
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - WHISPER_MODEL=tiny  # pakai tiny saat dev (lebih cepat)
      - GPU_ENABLED=false   # false untuk local dev tanpa GPU
    volumes:
      - ./worker_gpu:/app
      - ./shared:/app/shared
      - whisper_cache:/app/.cache/whisper  # persist whisper model
    restart: unless-stopped
    # Uncomment baris ini jika punya GPU lokal:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # ── Worker Node ─────────────────────────────────────────────────────
  worker_node:
    build:
      context: ./worker_node
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
    volumes:
      - ./worker_node:/app
      - ./shared:/app/shared
    restart: unless-stopped
    # Chromium butuh shm yang cukup besar
    shm_size: '2gb'

# ── Volumes ────────────────────────────────────────────────────────────
volumes:
  whisper_cache:
    driver: local
```

VERIFY:
```bash
# Dari root repo
docker compose config  # validasi syntax
docker compose build   # build semua
echo "docker-compose OK"
```

---

## STEP 6 — Buat .dockerignore untuk Setiap Service

### frontend/.dockerignore
```
node_modules/
dist/
.vite/
*.log
.env
.env.*
```

### backend/.dockerignore
```
__pycache__/
*.pyc
*.pyo
.env
.env.*
*.log
.pytest_cache/
```

### worker_gpu/.dockerignore
```
__pycache__/
*.pyc
*.pyo
.env
.env.*
*.log
.cache/
*.mp4
*.mp3
*.wav
*.mov
tmp/
temp/
outputs/
```

### worker_node/.dockerignore
```
__pycache__/
*.pyc
.env
.env.*
*.log
node_modules/
*.mp4
*.mov
tmp/
temp/
outputs/
```

VERIFY:
```bash
ls frontend/.dockerignore backend/.dockerignore worker_gpu/.dockerignore worker_node/.dockerignore
```

---

## STEP 7 — Verifikasi Full Build

Test semua service bisa build:

```bash
# Build satu per satu dan cek error
echo "Building frontend..."
docker build -t clipper-frontend ./frontend && echo "✅ Frontend OK" || echo "❌ Frontend FAILED"

echo "Building backend..."
docker build -t clipper-backend ./backend && echo "✅ Backend OK" || echo "❌ Backend FAILED"

echo "Building worker_gpu..."
docker build -t clipper-worker-gpu ./worker_gpu && echo "✅ Worker GPU OK" || echo "❌ Worker GPU FAILED"

echo "Building worker_node..."
docker build -t clipper-worker-node ./worker_node && echo "✅ Worker Node OK" || echo "❌ Worker Node FAILED"
```

Test docker-compose:
```bash
# Jalankan semua service
docker compose up -d

# Cek status
docker compose ps

# Cek logs
docker compose logs --tail=20

# Test backend health
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000
```

---

## STEP 8 — Update PHASE1_DONE.md → PHASE2_DONE.md

Buat file `PHASE2_DONE.md` di root:

```markdown
# Phase 2 Complete

## Yang sudah dikerjakan:
- [x] frontend/Dockerfile (React + Vite + Nginx)
- [x] frontend/nginx.conf
- [x] frontend/.dockerignore
- [x] backend/Dockerfile (FastAPI)
- [x] backend/main.py (entry point, re-export dari app.py)
- [x] backend/.dockerignore
- [x] worker_gpu/Dockerfile (Python + ffmpeg + Whisper + MediaPipe)
- [x] worker_gpu/worker.py (entry point placeholder)
- [x] worker_gpu/.dockerignore
- [x] worker_node/Dockerfile (Python + Node.js + Chromium)
- [x] worker_node/worker.py (entry point placeholder)
- [x] worker_node/.dockerignore
- [x] docker-compose.yml (development lokal)
- [x] Semua service berhasil docker build
- [x] docker-compose up berjalan

## Yang BELUM dikerjakan (Phase 3):
- [ ] Implementasi worker_gpu/tasks/ (download, transcribe, analyze, clip)
- [ ] Implementasi worker_node tasks (caption render penuh)
- [ ] Pub/Sub integration penuh
- [ ] Migrasi backend ke backend/main.py (hapus app.py lama)
- [ ] Cloud Run deployment configs (infra/)
- [ ] GitHub Actions CI/CD
- [ ] Hapus file lama (core/, api/, services/, app.py root)

## File lama yang masih ada (akan dihapus di Phase 3):
- core/ (lama)
- api/ (lama)
- services/ (lama)
- app.py (lama root)
- requirements.txt (root lama)
```

---

## CHECKLIST FINAL UNTUK AGENT

```
[ ] frontend/Dockerfile ada
[ ] frontend/nginx.conf ada
[ ] frontend/.dockerignore ada
[ ] backend/Dockerfile ada
[ ] backend/main.py ada
[ ] backend/.dockerignore ada
[ ] worker_gpu/Dockerfile ada
[ ] worker_gpu/worker.py ada
[ ] worker_gpu/.dockerignore ada
[ ] worker_node/Dockerfile ada
[ ] worker_node/worker.py ada
[ ] worker_node/.dockerignore ada
[ ] docker-compose.yml ada di root
[ ] docker build frontend berhasil (no error)
[ ] docker build backend berhasil (no error)
[ ] docker build worker_gpu berhasil (no error)
[ ] docker build worker_node berhasil (no error)
[ ] docker compose up berjalan
[ ] curl http://localhost:8000/health mengembalikan {"status": "ok"}
[ ] PHASE2_DONE.md ada
```

---

## JIKA ADA ERROR

### Error: frontend build — "dist not found"
Cek build output folder di vite.config.ts:
```bash
cat frontend/vite.config.ts | grep outDir
# Default Vite: dist/
# Jika CRA: build/
```
Ganti di Dockerfile baris `COPY --from=builder /app/dist` sesuai output.

### Error: backend — "cannot import app"
Normal di Phase 2. Backend main.py sudah handle dengan fallback minimal app.
Cek logs: `docker logs clipper-backend`

### Error: worker_gpu — "whisper download timeout"
Tambahkan `--network=host` saat build atau gunakan model lebih kecil:
```bash
docker build --build-arg WHISPER_MODEL=tiny -t clipper-worker-gpu ./worker_gpu
```
Dan update Dockerfile baris whisper download ke `tiny`.

### Error: worker_node — "Chromium sandbox"
Tambahkan environment variable:
```yaml
environment:
  - CHROMIUM_FLAGS=--no-sandbox --disable-dev-shm-usage
```

### Error: docker compose — "shared not found"
Pastikan build context di docker-compose.yml benar.
Shared folder di-copy via Dockerfile `COPY ../shared /app/shared`.
Jika masih error, copy manual dulu:
```bash
cp -r shared backend/shared
cp -r shared worker_gpu/shared
cp -r shared worker_node/shared
```

---

**END OF PHASE 2 INSTRUCTIONS**
