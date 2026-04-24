"""
ClipperApp — Google Colab Launcher
═══════════════════════════════════════════════════════════════

USAGE: Copy this entire file into a Google Colab cell and run it.
It will:
  1. Clone/upload the project files
  2. Install all dependencies
  3. Start the Flask server
  4. Create a cloudflared tunnel
  5. Print the public URL for you to access

PREREQUISITES:
  - Set your OpenAI API key as a Colab secret named 'OPENAI_API_KEY'
    or set it in the cell below before running.
"""

import subprocess
import os
import sys
import threading
import time
import re

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION — Edit these values before running
# ═══════════════════════════════════════════════════════════════

# Option 1: Set your API key directly (less secure)
# os.environ['OPENAI_API_KEY'] = 'sk-your-key-here'

# Option 2: Use Colab secrets (recommended)
try:
    from google.colab import userdata
    os.environ['OPENAI_API_KEY'] = userdata.get('OPENAI_API_KEY')
    print("✅ OpenAI API key loaded from Colab secrets")
except Exception:
    if 'OPENAI_API_KEY' not in os.environ:
        print("⚠️  No OPENAI_API_KEY found! Set it as a Colab secret or in the cell above.")

# ═══════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════

PROJECT_DIR = '/content/clipperApp'
WORKSPACE_DIR = '/content/clipper_workspace'
PORT = 5000

def run_cmd(cmd, desc="", silent=False):
    """Run a shell command with optional description."""
    if desc:
        print(f"  {desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=silent, text=True)
    if result.returncode != 0 and not silent:
        print(f"  ⚠️  Command failed: {cmd}")
        if result.stderr:
            print(f"  {result.stderr[:200]}")
    return result


print("╔═══════════════════════════════════════════╗")
print("║    🎬 ClipperApp — Colab Launcher         ║")
print("╚═══════════════════════════════════════════╝")
print()

# ─── Step 1: Install System Deps ────────────────────────────
print("📦 Step 1/4: Installing dependencies...")
run_cmd("apt-get update -qq && apt-get install -y -qq ffmpeg unzip curl > /dev/null 2>&1", "Installing FFmpeg", silent=True)
print("  ✅ FFmpeg")

# Install Deno (yt-dlp's preferred JS runtime for YouTube)
run_cmd("curl -fsSL https://deno.land/install.sh | sh > /dev/null 2>&1", "Installing Deno", silent=True)
os.environ['PATH'] = os.path.expanduser('~/.deno/bin') + ':' + os.environ.get('PATH', '')
print("  ✅ Deno (JS runtime for yt-dlp)")

# Install cloudflared
run_cmd(
    "wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb "
    "&& dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1 "
    "&& rm -f cloudflared-linux-amd64.deb",
    "Installing cloudflared",
    silent=True
)
print("  ✅ Cloudflared")

# ─── Step 2: Install Python Deps ────────────────────────────
print()
print("🐍 Step 2/4: Installing Python packages...")
run_cmd(
    "pip install -q flask openai opencv-python mediapipe numpy Pillow pysrt python-dotenv",
    silent=True
)
# yt-dlp[default] includes yt-dlp-ejs (JS challenge solver for YouTube)
run_cmd('pip install -q -U "yt-dlp[default]"', silent=True)
print("  ✅ All packages installed")
print("  ✅ yt-dlp + EJS challenge solver installed")

# ─── Step 3: Check if project exists ────────────────────────
print()
print("📁 Step 3/4: Setting up project files...")

if os.path.exists(os.path.join(PROJECT_DIR, 'app.py')):
    print("  ✅ Project files found!")
else:
    print("  ⚠️  Project files not found at /content/clipperApp")
    print("  📂 Please upload the project files:")
    print("     Option A: Upload the clipperApp folder to /content/")
    print("     Option B: Clone from your repo:")
    print("       !git clone https://github.com/YOUR_USER/clipperApp /content/clipperApp")
    print()
    print("  After uploading, re-run this cell.")
    sys.exit(1)

# Create workspace
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.environ['CLIPPER_WORKSPACE'] = WORKSPACE_DIR

# Check for cookies.txt
cookies_path = os.path.join(PROJECT_DIR, 'cookies.txt')
if os.path.exists(cookies_path):
    print("  ✅ cookies.txt found!")
else:
    print("  ⚠️  No cookies.txt found. YouTube may block downloads.")
    print("     To fix: export cookies from your browser and upload as cookies.txt")
    print("     See: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp")

# ─── Step 4: Start Flask + Cloudflared ──────────────────────
print()
print("🚀 Step 4/4: Starting server...")

# Start Flask in background
flask_process = subprocess.Popen(
    [sys.executable, 'app.py'],
    cwd=PROJECT_DIR,
    env={**os.environ, 'PORT': str(PORT), 'CLIPPER_WORKSPACE': WORKSPACE_DIR},
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# Wait for Flask to start
time.sleep(3)
print(f"  ✅ Flask server running on port {PORT}")

# Start cloudflared tunnel
print("  🌐 Starting cloudflared tunnel...")
tunnel_process = subprocess.Popen(
    ['cloudflared', 'tunnel', '--url', f'http://localhost:{PORT}'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# Wait for tunnel URL
tunnel_url = None
start_time = time.time()
while time.time() - start_time < 30:
    line = tunnel_process.stdout.readline()
    if not line:
        break
    # Look for the tunnel URL
    match = re.search(r'(https://[\w-]+\.trycloudflare\.com)', line)
    if match:
        tunnel_url = match.group(1)
        break

if tunnel_url:
    print()
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🎉 ClipperApp is LIVE!                              ║")
    print("╠═══════════════════════════════════════════════════════╣")
    print(f"║  🌐 URL: {tunnel_url}")
    print("║                                                       ║")
    print("║  Open the URL above in your browser to start!         ║")
    print("║  The app will run as long as this Colab cell runs.    ║")
    print("╚═══════════════════════════════════════════════════════╝")
else:
    print("  ⚠️  Could not detect tunnel URL. Check cloudflared logs.")
    print("  The server is still running on port 5000.")

# ─── Keep alive: stream Flask logs ──────────────────────────
print()
print("📋 Server logs (Ctrl+C or stop cell to quit):")
print("─" * 50)

try:
    while True:
        line = flask_process.stdout.readline()
        if not line:
            # Check if process is still running
            if flask_process.poll() is not None:
                print("⚠️  Flask server stopped unexpectedly!")
                break
            time.sleep(0.1)
            continue
        print(line.rstrip())
except KeyboardInterrupt:
    print("\n🛑 Stopping server...")
    flask_process.terminate()
    tunnel_process.terminate()
    print("✅ Server stopped.")
