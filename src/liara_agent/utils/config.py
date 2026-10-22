"""Configuration manager for liara-agent."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from liara_agent.utils.constants import LIARA_API_BASE_URL


def _get_config_dir() -> Path:
    """Get the config directory for liara-agent."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_dir = base / "liara-agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_data_dir() -> Path:
    """Get the data directory for liara-agent."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / "liara-agent"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


CONFIG_DIR = _get_config_dir()
DATA_DIR = _get_data_dir()
DB_PATH = DATA_DIR / "liara_agent.db"
AUDIT_LOG_PATH = DATA_DIR / "audit.log"


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # Liara
    liara_api_token: str = Field(default="", description="Liara API Bearer Token")
    liara_api_base_url: str = Field(
        default=LIARA_API_BASE_URL,
        description="Liara API base URL",
    )
    liara_default_project: str = Field(default="", description="Default project name")

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="openai/gpt-4o-mini", description="OpenAI model to use")

    # General
    log_level: str = Field(default="INFO", description="Logging level")
    language: str = Field(default="fa", description="UI language (fa/en)")

    @property
    def has_liara_token(self) -> bool:
        """Check if Liara API token is configured."""
        return bool(self.liara_api_token) and self.liara_api_token != "liara_xxxxxxxxxxxxxxxx"

    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.openai_api_key) and self.openai_api_key != "sk-xxxxxxxxxxxxxxxx"


def get_settings() -> Settings:
    """Get application settings (singleton-like)."""
    return Settings()
