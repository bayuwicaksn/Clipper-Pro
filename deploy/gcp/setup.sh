#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ClipperApp — GCP Compute Engine Setup Script
# 
# Usage: Run this on a fresh Ubuntu 22.04 VM
#   curl -sSL <raw_url> | bash
#   OR
#   bash setup.sh
# ═══════════════════════════════════════════════════════════════════

set -e

APP_DIR="/opt/clipperapp"
WORKSPACE_DIR="/opt/clipperapp/workspace"
NODE_VERSION="20"

echo "╔═══════════════════════════════════════════════════╗"
echo "║   ClipperApp — GCP Setup (Budget Optimized)      ║"
echo "╚═══════════════════════════════════════════════════╝"

# ─── System Dependencies ──────────────────────────────────
echo ""
echo "📦 [1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    ffmpeg \
    git \
    curl \
    wget \
    build-essential \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    certbot \
    python3-certbot-nginx \
    > /dev/null 2>&1
echo "   ✅ System packages installed"

# ─── Node.js ──────────────────────────────────────────────
echo ""
echo "📗 [2/6] Installing Node.js ${NODE_VERSION}..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | sudo -E bash - > /dev/null 2>&1
    sudo apt-get install -y -qq nodejs > /dev/null 2>&1
fi
echo "   ✅ Node.js $(node --version) installed"

# ─── Python Virtual Environment ──────────────────────────
echo ""
echo "🐍 [3/6] Setting up Python environment..."
sudo mkdir -p ${APP_DIR}
sudo chown $(whoami):$(whoami) ${APP_DIR}

python3.11 -m venv ${APP_DIR}/venv
source ${APP_DIR}/venv/bin/activate

pip install --upgrade pip -q
pip install -q \
    flask>=3.0.0 \
    flask-cors \
    openai>=1.0.0 \
    "yt-dlp[default]" \
    opencv-python-headless>=4.8.0 \
    mediapipe>=0.10.0 \
    numpy>=1.24.0 \
    Pillow>=10.0.0 \
    pysrt>=1.1.2 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    torch>=2.0.0 --index-url https://download.pytorch.org/whl/cpu \
    google-generativeai>=0.5.0 \
    gunicorn \
    pycaps

echo "   ✅ Python packages installed"

# ─── Clone/Copy Application ─────────────────────────────
echo ""
echo "📂 [4/6] Setting up application..."
mkdir -p ${WORKSPACE_DIR}

# If running from the repo, copy files
if [ -f "app.py" ]; then
    echo "   Found local files, copying..."
    cp -r . ${APP_DIR}/src/
else
    echo "   ⚠️  No local files found."
    echo "   Please copy your ClipperApp code to ${APP_DIR}/src/"
fi

# ─── Frontend Build ──────────────────────────────────────
echo ""
echo "🏗️  [5/6] Building frontend..."
if [ -d "${APP_DIR}/src/frontend" ]; then
    cd ${APP_DIR}/src/frontend
    npm install --silent 2>/dev/null
    npm run build --silent 2>/dev/null
    echo "   ✅ Frontend built"
else
    echo "   ⚠️  Frontend directory not found, skipping..."
fi

# ─── Systemd Service ─────────────────────────────────────
echo ""
echo "⚙️  [6/6] Configuring system services..."

# Backend service
sudo tee /etc/systemd/system/clipperapp.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=ClipperApp Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clipperapp/src
Environment="PATH=/opt/clipperapp/venv/bin:/usr/local/bin:/usr/bin"
Environment="CLIPPER_WORKSPACE=/opt/clipperapp/workspace"
Environment="PORT=5000"
EnvironmentFile=/opt/clipperapp/src/.env
ExecStart=/opt/clipperapp/venv/bin/gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 300 \
    --worker-class gthread \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Nginx reverse proxy
sudo tee /etc/nginx/sites-available/clipperapp > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    # Frontend (built static files)
    location / {
        root /opt/clipperapp/src/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
    }

    # Video file serving (direct, bypass Flask for performance)
    location /workspace/ {
        alias /opt/clipperapp/workspace/;
        add_header Accept-Ranges bytes;
        add_header Cache-Control "public, max-age=3600";
    }

    # Large upload support
    client_max_body_size 5G;
}
NGINXEOF

sudo ln -sf /etc/nginx/sites-available/clipperapp /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable clipperapp
sudo systemctl enable nginx

echo "   ✅ Services configured"

# ─── Summary ─────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                    ✅ Setup Complete!                     ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║                                                           ║"
echo "║  1. Copy your .env file to /opt/clipperapp/src/.env       ║"
echo "║  2. Start services:                                       ║"
echo "║     sudo systemctl start clipperapp                       ║"
echo "║     sudo systemctl start nginx                            ║"
echo "║                                                           ║"
echo "║  3. Access at: http://<YOUR_VM_IP>                        ║"
echo "║                                                           ║"
echo "║  Logs: sudo journalctl -u clipperapp -f                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
