from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # App Settings
    CLIPPER_WORKSPACE: str = "workspace"
    DATABASE_URL: str = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'clipper.db')}"
    DEBUG: bool = False
    PORT: int = 5000
    HOST: str = "0.0.0.0"

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Create an instance of the settings
settings = Settings()
