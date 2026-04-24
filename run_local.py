import os
import sys
import subprocess
import time
import webbrowser
import threading

# Configuration
PORT = 5000
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(PROJECT_DIR, 'workspace')

def check_command(cmd):
    try:
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=5
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

print("+-------------------------------------------+")
print("|       ClipperApp - Local Launcher         |")
print("+-------------------------------------------+")
print()

# --- Check dependencies ---
print("[Checking dependencies...]")

# Python packages
try:
    import fastapi
    print(f"  [OK] FastAPI {fastapi.__version__}")
except ImportError:
    print("  [MISSING] FastAPI not found. Run: pip install fastapi uvicorn python-multipart")
    sys.exit(1)

try:
    import uvicorn
    print(f"  [OK] Uvicorn {uvicorn.__version__}")
except ImportError:
    print("  [MISSING] Uvicorn not found. Run: pip install uvicorn")
    sys.exit(1)

try:
    import openai
    print("  [OK] OpenAI")
except ImportError:
    print("  [MISSING] OpenAI not found. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import cv2
    print("  [OK] OpenCV")
except ImportError:
    print("  [MISSING] OpenCV not found. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import mediapipe
    print("  [OK] MediaPipe")
except ImportError:
    print("  [WARNING] MediaPipe not found. This is optional but recommended.")

# Check workspace
if not os.path.exists(WORKSPACE_DIR):
    os.makedirs(WORKSPACE_DIR)
    print(f"[Workspace created at {WORKSPACE_DIR}]")

# Set env vars
os.environ['CLIPPER_WORKSPACE'] = WORKSPACE_DIR

# --- Start server ---
print(f"Starting server on http://localhost:{PORT}")
print()
print("+-------------------------------------------------------+")
print("|  - ClipperApp is starting! (FastAPI + Uvicorn)        |")
print(f"|  - API URL:  http://localhost:{PORT}                  |")
print(f"|  - API Docs: http://localhost:{PORT}/docs             |")
print("|                                                       |")
print("|  - Please open http://localhost:5173 for React UI     |")
print("|  Press Ctrl+C to stop the server.                     |")
print("+-------------------------------------------------------+")
print()

# Open browser after a short delay
def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:5173")

threading.Thread(target=open_browser, daemon=True).start()

# Start FastAPI with Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=PORT, reload=False)
