import json
from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

backend_dir = Path(__file__).resolve().parent.parent.parent
env_file_path = backend_dir / ".env"

class Settings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""
    DATABASE_URL: str
    REDIS_URL: str
    CLERK_SECRET_KEY: str
    CLERK_WEBHOOK_SIGNING_SECRET: str
    CLERK_AUTHORIZED_PARTIES: List[str] = Field(default_factory=list)
    GEMINI_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=str(env_file_path),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CLERK_AUTHORIZED_PARTIES", mode="before")
    @classmethod
    def parse_authorized_parties(cls, v: str | List[str]) -> List[str]:
        """Parse the authorized parties field. Can accept a JSON array string or a comma-separated string."""
        if isinstance(v, list):
            return v
        if not v:
            return []
        v_str = str(v).strip()
        if v_str.startswith("[") and v_str.endswith("]"):
            try:
                return json.loads(v_str)
            except json.JSONDecodeError:
                pass
        return [party.strip() for party in v_str.split(",") if party.strip()]

settings = Settings()
