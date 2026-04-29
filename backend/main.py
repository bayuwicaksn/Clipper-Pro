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
