"""
App configuration — reads from environment / .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic import BaseModel


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv()


class Settings(BaseModel):
    # Gemini API settings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
    gemini_timeout: float = float(os.getenv("GEMINI_TIMEOUT", "120"))
    
    # Image processing
    max_image_dim: int = int(os.getenv("MAX_IMAGE_DIM", "2048"))
    
    # Retry settings
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
    retry_max_delay: float = float(os.getenv("RETRY_MAX_DELAY", "30.0"))
    
    # Confidence thresholds
    confidence_threshold_validate: float = float(os.getenv("CONFIDENCE_VALIDATE", "0.70"))
    confidence_threshold_drop: float = float(os.getenv("CONFIDENCE_DROP", "0.30"))
    region_density_threshold: int = int(os.getenv("REGION_DENSITY", "8"))
    
    # Cache settings
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    cache_max_size: int = int(os.getenv("CACHE_MAX_SIZE", "100"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
