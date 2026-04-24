# --- Stage 1: Build Frontend ---
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Final Image ---
FROM python:3.11-slim-bookworm

# 1. Install System Dependencies (FFmpeg & OpenCV/MediaPipe deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy Application Code
COPY . .

# 4. Copy Built Frontend from Stage 1
# FastAPI app.py is already configured to serve frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 5. Environment Variables
ENV PORT=8080
ENV CLIPPER_WORKSPACE=/app/workspace
ENV PYTHONUNBUFFERED=1

# Ensure workspace exists
RUN mkdir -p /app/workspace

# 6. Start the App
# Use uvicorn directly for Cloud Run performance
CMD uvicorn app:app --host 0.0.0.0 --port $PORT
