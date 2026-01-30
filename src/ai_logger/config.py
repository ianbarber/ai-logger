"""Configuration management using environment variables."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path("~/.config/ai-logger/.env").expanduser()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Roam Research
    roam_graph_name: str
    roam_api_token: str

    # Local storage
    db_path: Path = Path("~/.local/share/ai-logger/queue.db")

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 60

    def get_db_path(self) -> Path:
        """Get expanded database path."""
        return self.db_path.expanduser()


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_settings_from_env_file(env_file: Path) -> Settings:
    """Load settings from a specific env file."""
    global _settings
    _settings = Settings(_env_file=env_file)
    return _settings
