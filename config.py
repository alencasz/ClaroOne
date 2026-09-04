from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "CLARO ONE"
    database_path: Path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "claro_one.db"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_transcription_model: str = os.getenv(
        "GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo"
    ).strip()
    groq_context_model: str = os.getenv("GROQ_CONTEXT_MODEL", "openai/gpt-oss-20b").strip()
    groq_timeout_seconds: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
    cce_ttl_hours: int = int(os.getenv("CCE_TTL_HOURS", "2"))
    demo_fallback: bool = _as_bool(os.getenv("DEMO_FALLBACK"), False)
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    timezone: str = "America/Sao_Paulo"


settings = Settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
