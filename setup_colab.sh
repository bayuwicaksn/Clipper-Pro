#!/bin/bash
# ═══════════════════════════════════════════════════════════
# ClipperApp — Colab Setup Script
# Installs all dependencies and starts the cloudflared tunnel
# ═══════════════════════════════════════════════════════════

set -e

echo "╔═══════════════════════════════════════════╗"
echo "║       ClipperApp — Setup Starting         ║"
echo "╚═══════════════════════════════════════════╝"

# ─── System Dependencies ────────────────────────────────
echo ""
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq ffmpeg > /dev/null 2>&1
echo "   ✅ FFmpeg installed"

# ─── Cloudflared ────────────────────────────────────────
echo ""
echo "🌐 Installing cloudflared..."
if ! command -v cloudflared &> /dev/null; then
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1
    rm -f cloudflared-linux-amd64.deb
fi
echo "   ✅ Cloudflared installed"

# ─── Python Dependencies ───────────────────────────────
echo ""
echo "🐍 Installing Python dependencies..."
pip install -q flask openai yt-dlp opencv-python mediapipe numpy Pillow pysrt
echo "   ✅ Python packages installed"

# ─── yt-dlp Update ──────────────────────────────────────
echo ""
echo "📺 Updating yt-dlp to latest..."
pip install -q --upgrade yt-dlp
echo "   ✅ yt-dlp updated"

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║       ✅ Setup Complete!                  ║"
echo "╚═══════════════════════════════════════════╝"
echo ""
echo "Run 'python run_colab.py' to start the app!"
