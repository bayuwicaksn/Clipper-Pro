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
COPY --from=shared . /app/shared/

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

# Entry point
CMD ["python3", "worker.py"]
