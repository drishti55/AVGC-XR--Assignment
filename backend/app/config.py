"""Application settings, loaded from environment variables / backend/.env.

Secrets (GEMINI_API_KEY) live only here on the backend; the frontend never sees them.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Primary LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_seconds: float = 30
    gemini_thinking_level: str = "minimal"   # minimal|low|medium|high — minimal is ~4x faster

    # Fallback LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 90

    # Retrieval
    embedding_model: str = "intfloat/multilingual-e5-small"
    top_k: int = 4
    semantic_threshold: float = 0.80          # needs keyword support
    strong_semantic_threshold: float = 0.85   # enough on its own
    bm25_threshold: float = 6.0

    # App
    database_path: str = "data/garuda.db"
    cors_origins: str = "http://localhost:5173"
    rate_limit: str = "10/minute"

    @property
    def db_file(self) -> Path:
        p = Path(self.database_path)
        return p if p.is_absolute() else BACKEND_DIR / p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
