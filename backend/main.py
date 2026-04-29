from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .db.database import create_db_and_tables
from .api.projects import router as projects_router
from .api.media import router as media_router
from .api.pipeline import router as pipeline_router
from .api.editor import router as editor_router
from .api.ai import router as ai_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    create_db_and_tables()
    yield

app = FastAPI(
    title="Clipper-Pro API",
    description="Microservice backend for AI-powered video clipping",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
allowed_origins = [
    origin.strip()
    for origin in getattr(settings, "CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if not allowed_origins:
    allowed_origins = [
        "https://clipper-frontend-715622381960.asia-southeast1.run.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(projects_router)
app.include_router(media_router)
app.include_router(pipeline_router)
app.include_router(editor_router)
app.include_router(ai_router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend", "version": "2.0.0"}

@app.get("/")
async def root():
    return {"message": "Clipper-Pro Backend API is running"}
