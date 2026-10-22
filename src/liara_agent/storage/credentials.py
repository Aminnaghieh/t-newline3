"""Secure credential storage using OS keyring with .env fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from liara_agent.utils.config import CONFIG_DIR

logger = logging.getLogger(__name__)

SERVICE_NAME = "liara-agent"


class CredentialStore:
    """Manages secure storage of API tokens and keys."""

    def __init__(self, env_path: Path | None = None) -> None:
        self.env_path = env_path or Path(".env")
        self._keyring_available = True
        try:
            import keyring
            self._keyring = keyring
        except Exception:
            self._keyring_available = False

    def store_token(self, key: str, value: str) -> None:
        """Store a token securely."""
        key_upper = key.upper()
        if self._keyring_available:
            try:
                self._keyring.set_password(SERVICE_NAME, key_upper, value)
            except Exception as e:
                logger.debug("Keyring storage failed, falling back to .env: %s", e)

        # Also persist/update in .env file for portability
        self._update_env_file(key_upper, value)

    def get_token(self, key: str) -> str | None:
        """Retrieve a stored credential."""
        key_upper = key.upper()
        # 1. Environment variable
        env_val = os.environ.get(key_upper)
        if env_val:
            return env_val

        # 2. Keyring
        if self._keyring_available:
            try:
                val = self._keyring.get_password(SERVICE_NAME, key_upper)
                if val:
                    return val
            except Exception:
                pass

        # 3. .env file
        if self.env_path.exists():
            with open(self.env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key_upper:
                            return v.strip().strip("'\"")

        return None

    def delete_token(self, key: str) -> None:
        """Delete a stored credential."""
        key_upper = key.upper()
        if self._keyring_available:
            try:
                self._keyring.delete_password(SERVICE_NAME, key_upper)
            except Exception:
                pass
        self._remove_from_env_file(key_upper)

    def has_token(self, key: str) -> bool:
        """Check if credential exists and is non-empty."""
        val = self.get_token(key)
        return bool(val and not val.endswith("xxxx"))

    def _update_env_file(self, key: str, value: str) -> None:
        lines: list[str] = []
        found = False
        if self.env_path.exists():
            with open(self.env_path, encoding="utf-8") as f:
                lines = f.readlines()

        new_lines: list[str] = []
        for line in lines:
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={value}\n")

        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _remove_from_env_file(self, key: str) -> None:
        if not self.env_path.exists():
            return
        with open(self.env_path, encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = [
            line for line in lines
            if not (line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="))
        ]
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)


default_credential_store = CredentialStore()
