"""Environment-based service settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    app_name: str = "factchecker-ai"
    app_version: str = "1.0.0"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    text_encoder_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    text_encoder_device: str = "auto"
    text_encoder_batch_size: int = 8
    text_encoder_chunk_size: int = 4000
    image_encoder_model: str = "ViT-B-32"
    image_encoder_checkpoint: str = "openai"
    image_encoder_device: str = "auto"
    image_encoder_batch_size: int = 4
    whisper_model_variant: str = "tiny"
    whisper_device: str = "auto"
    whisper_language: Optional[str] = None
    whisper_task: str = "transcribe"
    whisper_max_duration_seconds: int = 600
    whisper_chunk_seconds: Optional[int] = None
    ocr_languages: str = "en"
    ocr_device: str = "auto"
    ocr_use_gpu: bool = False
    ocr_model_directory: Optional[str] = None
    ocr_paragraph_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the process."""

    return Settings()


def get_allowed_origins(settings: Settings) -> list[str]:
    """Return configured origins and reject an unsafe wildcard configuration."""

    origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
    origins = [origin for origin in origins if origin]

    if "*" in origins:
        raise ValueError("ALLOWED_ORIGINS cannot contain '*' .")

    return origins
