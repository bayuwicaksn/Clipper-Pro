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
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # yt-dlp dependencies (nodejs is CRITICAL for bypassing YouTube bot detection)
    curl \
    wget \
    nodejs \
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

# Pre-download Whisper model saat build (DISABLED: Using API for now)
# ARG WHISPER_MODEL=medium
# ENV WHISPER_MODEL=${WHISPER_MODEL}
# RUN python3 -c "import whisper; import os; whisper.load_model(os.getenv('WHISPER_MODEL', 'medium'))" && \
#     echo "Whisper model pre-downloaded OK"

# Copy shared models
COPY --from=shared . /app/shared/

# Copy worker source
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos "" workeruser && \
    chown -R workeruser:workeruser /app
USER workeruser

# Health check — cek apakah worker process berjalan
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Entry point
CMD ["python3", "worker.py"]
