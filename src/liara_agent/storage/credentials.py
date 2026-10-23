"""Secure credential storage using OS keyring with .env fallback.

Security contract
-----------------
- The OS keyring is the **primary** storage. A secret is written to the
  ``.env`` file only when the keyring is unavailable or fails — plaintext
  persistence is a deliberate fallback, never a side-effect of a successful
  keyring write.
- When the keyring succeeds and a stale plaintext copy of the same key
  already exists in ``.env``, it is purged.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key

from liara_agent.utils.config import CONFIG_DIR

logger = logging.getLogger(__name__)

SERVICE_NAME = "liara-agent"


def is_placeholder(value: str | None) -> bool:
    """True when a token is empty or an obvious placeholder value."""
    if not value:
        return True
    stripped = value.strip().lower()
    return (
        stripped.endswith("xxxx")
        or stripped in {"changeme", "placeholder", "your-token-here"}
    )


def resolve_liara_token() -> str | None:
    """Single source of truth for token resolution.

    Lookup order: process env → OS keyring → private ``.env`` → settings.
    Returns ``None`` when no usable token is configured.
    """
    from liara_agent.utils.config import get_settings

    token = default_credential_store.get_token("LIARA_API_TOKEN")
    if token and not is_placeholder(token):
        return token
    settings = get_settings()
    token = settings.liara_api_token
    return token if token and not is_placeholder(token) else None


class CredentialStore:
    """Manages secure storage of API tokens and keys."""

    def __init__(self, env_path: Path | None = None) -> None:
        # Prefer the app config directory; keep parameter override for tests.
        self.env_path = env_path or CONFIG_DIR / ".env"
        self._keyring_available = True
        try:
            import keyring
            self._keyring = keyring
        except Exception:
            self._keyring = None
            self._keyring_available = False

    # ── Public API ───────────────────────────────────────────

    def store_token(self, key: str, value: str) -> None:
        """Store a token in the keyring when possible.

        ``.env`` persistence happens **only** as a fallback and the file is
        restricted to owner-only permissions on POSIX. A plaintext copy of
        the key is removed from ``.env`` whenever keyring storage succeeds.
        """
        key_upper = key.upper()
        stored_securely = False

        if self._keyring_available and self._keyring is not None:
            try:
                self._keyring.set_password(SERVICE_NAME, key_upper, value)
                stored_securely = True
            except Exception as e:
                logger.debug("Keyring storage failed: %s", e)

        if stored_securely:
            # Migrate out any previously persisted plaintext copy.
            self._remove_from_env_file(key_upper)
            if key_upper in os.environ:
                logger.info("Token %s also present in env; runtime override kept.", key_upper)
            return

        self._update_env_file(key_upper, value)
        self._restrict_env_permissions()

    def get_token(self, key: str) -> str | None:
        """Retrieve a stored credential.

        Lookup order: process environment → OS keyring → ``.env`` file.
        """
        key_upper = key.upper()

        env_val = os.environ.get(key_upper)
        if env_val:
            return env_val

        if self._keyring_available and self._keyring is not None:
            try:
                val = self._keyring.get_password(SERVICE_NAME, key_upper)
                if val:
                    return val
            except Exception:
                logger.debug("Keyring read failed for %s", key_upper, exc_info=True)

        return self._read_from_env_file(key_upper)

    def delete_token(self, key: str) -> None:
        """Delete a stored credential from every storage surface."""
        key_upper = key.upper()
        if self._keyring_available and self._keyring is not None:
            # Not stored there is not an error — nothing to do.
            with contextlib.suppress(Exception):
                self._keyring.delete_password(SERVICE_NAME, key_upper)
        self._remove_from_env_file(key_upper)
        # Drop the process-local copy so env precedence cannot resurrect it.
        os.environ.pop(key_upper, None)

    def has_token(self, key: str) -> bool:
        """Check if credential exists and is not the placeholder value."""
        val = self.get_token(key)
        return bool(val and not val.endswith("xxxx"))

    # ── Internal ─────────────────────────────────────────────

    def _read_from_env_file(self, key_upper: str) -> str | None:
        """Read a key from the ``.env`` file (python-dotenv parsing)."""
        if not self.env_path.exists():
            return None
        try:
            values = dotenv_values(self.env_path)
        except OSError:
            logger.debug("Could not read %s", self.env_path, exc_info=True)
            return None
        val = values.get(key_upper)
        return str(val) if val else None

    def _update_env_file(self, key: str, value: str) -> None:
        """Upsert ``KEY=value`` in the ``.env`` file (preserving other keys).

        The file is created with owner-only permissions *before* any secret
        is written, closing the world-readable window that ``set_key`` alone
        would leave open.
        """
        try:
            if not self.env_path.exists():
                fd = os.open(self.env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
            set_key(self.env_path, key, str(value))
        except OSError as e:
            logger.error("Could not write %s: %s", self.env_path, e)
        finally:
            self._restrict_env_permissions()

    def _remove_from_env_file(self, key: str) -> None:
        """Remove ``KEY=...`` lines from the ``.env`` file."""
        if not self.env_path.exists():
            return
        try:
            unset_key(self.env_path, key)
        except OSError:
            logger.debug("Could not update %s", self.env_path, exc_info=True)

    def _restrict_env_permissions(self) -> None:
        """Restrict the ``.env`` file to owner-only access (POSIX)."""
        if os.name != "posix" or not self.env_path.exists():
            return
        try:
            self.env_path.chmod(0o600)
        except OSError:
            logger.debug("chmod failed on %s", self.env_path, exc_info=True)


default_credential_store = CredentialStore()
