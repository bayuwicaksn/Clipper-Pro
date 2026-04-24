"""
ClipperApp — FastAPI Backend
Modular application entry point.

All route handlers are organized into routers under the api/ directory:
  - api/projects.py  → Project CRUD, clip listing
  - api/media.py     → Video streaming, downloads, thumbnails
  - api/pipeline.py  → Processing jobs, export, SSE progress
  - api/editor.py    → Editor state save/load, transcript API
  - api/ai.py        → Caption presets, scene detection, face tracking
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# ─── Create App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="ClipperApp",
    description="AI-powered video clipping engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ────────────────────────────────────────────────────────
from api.projects import router as projects_router
from api.media import router as media_router
from api.pipeline import router as pipeline_router
from api.editor import router as editor_router
from api.ai import router as ai_router

app.include_router(projects_router)
app.include_router(media_router)
app.include_router(pipeline_router)
app.include_router(editor_router)
app.include_router(ai_router)


# ─── SPA Catch-all ───────────────────────────────────────────────────────────
# Serve frontend static files if the dist directory exists
_frontend_dist = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
_templates_dir = os.path.join(os.path.dirname(__file__), 'templates')

if os.path.isdir(_frontend_dist) and os.path.isfile(os.path.join(_frontend_dist, "index.html")):
    assets_path = os.path.join(_frontend_dist, "assets")
    if os.path.isdir(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Try to serve static file first
        file_path = os.path.join(_frontend_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Fallback to index.html for SPA routing
        return FileResponse(os.path.join(_frontend_dist, "index.html"))

elif os.path.isdir(_templates_dir):
    @app.get("/{full_path:path}")
    async def serve_template(full_path: str):
        index = os.path.join(_templates_dir, 'index.html')
        if os.path.exists(index):
            return FileResponse(index)
        return {"message": "ClipperApp API is running. Frontend not built yet."}


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host='0.0.0.0', port=port)
