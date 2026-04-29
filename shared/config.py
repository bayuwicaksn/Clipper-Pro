from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # App Settings
    CLIPPER_WORKSPACE: str = "workspace"
    
    # Database Settings (Supports Supabase/Postgres via DATABASE_URL env)
    # Default to local sqlite for development
    DATABASE_URL: str = "sqlite:///clipper.db"
    
    DEBUG: bool = False
    PORT: int = 5000
    HOST: str = "0.0.0.0"

    # API Keys & Secrets
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # Pub/Sub Topics
    GCP_PROJECT_ID: str = ""
    PUBSUB_TOPIC_JOBS: str = "clipper-jobs"
    PUBSUB_TOPIC_CAPTION: str = "clipper-caption-jobs"

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Create an instance of the settings
settings = Settings()
