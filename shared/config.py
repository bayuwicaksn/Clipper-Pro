"""
Shared application settings — read from environment variables / .env file.
Used by backend, worker_gpu, and worker_node.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CLIPPER_WORKSPACE: str = "workspace"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: str = ""

    # ── Database ──────────────────────────────────────────────────────────
    # Supports SQLite (local dev) and PostgreSQL (production via Supabase)
    DATABASE_URL: str = "sqlite:///clipper.db"

    # ── API Keys ──────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # ── Supabase ──────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # ── GCP / Pub/Sub ─────────────────────────────────────────────────────
    GCP_PROJECT_ID: str = ""
    GCS_BUCKET: str = ""

    PUBSUB_TOPIC_JOBS: str = "clipper-jobs"
    PUBSUB_TOPIC_CAPTION: str = "clipper-caption-jobs"
    PUBSUB_TOPIC_EXPORT: str = "clipper-export-jobs"

    PUBSUB_SUBSCRIPTION_JOBS: str = "clipper-jobs-sub"
    PUBSUB_SUBSCRIPTION_CAPTION: str = "clipper-caption-jobs-sub"
    PUBSUB_SUBSCRIPTION_EXPORT: str = "clipper-export-jobs-sub"

    # ── Worker / GPU ──────────────────────────────────────────────────────
    WHISPER_MODEL: str = "medium"
    GPU_ENABLED: bool = False

    # ── Storage behaviour ─────────────────────────────────────────────────
    # When True and GCS_BUCKET is set, processed files are uploaded to GCS
    # and served via signed URLs. Set False for pure local/dev mode.
    USE_GCS: bool = False

    # Signed URL expiry in seconds (default 1 hour)
    GCS_SIGNED_URL_EXPIRY: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def gcs_enabled(self) -> bool:
        return bool(self.USE_GCS and self.GCS_BUCKET and self.GCP_PROJECT_ID)

    @property
    def pubsub_enabled(self) -> bool:
        return bool(self.GCP_PROJECT_ID)


# Singleton instance used everywhere
settings = Settings()
