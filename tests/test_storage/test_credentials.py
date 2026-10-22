"""Tests for the secure CredentialStore (keyring primary, .env fallback)."""

import os

from liara_agent.storage.credentials import CredentialStore


class FakeKeyring:
    """In-memory keyring stand-in."""

    def __init__(self) -> None:
        self.storage: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, key: str, value: str) -> None:
        self.storage[(service, key)] = value

    def get_password(self, service: str, key: str) -> str | None:
        return self.storage.get((service, key))

    def delete_password(self, service: str, key: str) -> None:
        self.storage.pop((service, key), None)


def make_store(tmp_path, keyring: bool) -> CredentialStore:
    store = CredentialStore(env_path=tmp_path / "env")
    if keyring:
        store._keyring = FakeKeyring()
        store._keyring_available = True
    else:
        store._keyring = None
        store._keyring_available = False
    return store


def test_store_prefers_keyring_and_never_writes_plaintext(tmp_path):
    store = make_store(tmp_path, keyring=True)
    store.store_token("LIARA_API_TOKEN", "sk-real-token")

    # Held by the keyring…
    fake: FakeKeyring = store._keyring  # type: ignore[assignment]
    assert fake.storage[("liara-agent", "LIARA_API_TOKEN")] == "sk-real-token"

    # …and no plaintext .env file was created at all.
    assert not (tmp_path / "env").exists()
    assert store.get_token("LIARA_API_TOKEN") == "sk-real-token"


def test_store_falls_back_to_env_when_keyring_unavailable(tmp_path):
    store = make_store(tmp_path, keyring=False)
    store.store_token("LIARA_API_TOKEN", "env-token-value")

    assert (tmp_path / "env").exists()
    content = (tmp_path / "env").read_text(encoding="utf-8")
    assert "env-token-value" in content
    assert store.get_token("LIARA_API_TOKEN") == "env-token-value"


def test_successful_keyring_store_purges_stale_plaintext(tmp_path):
    store = make_store(tmp_path, keyring=True)
    env_file = tmp_path / "env"
    env_file.write_text("LIARA_API_TOKEN=old-plaintext-token\nOTHER=keepme\n", encoding="utf-8")

    store.store_token("LIARA_API_TOKEN", "secure-token")

    content = env_file.read_text(encoding="utf-8")
    assert "old-plaintext-token" not in content  # stale copy purged
    assert "secure-token" not in content          # new secret not persisted plaintext
    assert "OTHER=keepme" in content              # other keys untouched
    assert store.get_token("LIARA_API_TOKEN") == "secure-token"


def test_delete_removes_from_every_surface(tmp_path, monkeypatch):
    store = make_store(tmp_path, keyring=False)
    monkeypatch.setenv("LIARA_API_TOKEN", "mem-copy")
    store.store_token("LIARA_API_TOKEN", "disk-copy")

    store.delete_token("LIARA_API_TOKEN")

    assert store.get_token("LIARA_API_TOKEN") is None
    assert "LIARA_API_TOKEN" not in os.environ    # process copy dropped
    assert "disk-copy" not in (tmp_path / "env").read_text(encoding="utf-8")


def test_has_token_rejects_placeholder(tmp_path):
    store = make_store(tmp_path, keyring=False)
    store.store_token("ALPHA_KEY", "liara_xxxxxxxx")
    assert store.has_token("ALPHA_KEY") is False

    store.delete_token("ALPHA_KEY")
    store.store_token("ALPHA_KEY", "real-value")
    assert store.has_token("ALPHA_KEY") is True


def test_env_var_takes_priority(tmp_path, monkeypatch):
    store = make_store(tmp_path, keyring=True)
    monkeypatch.setenv("LIARA_API_TOKEN", "env-wins")
    store.store_token("LIARA_API_TOKEN", "keyring-copy")

    assert store.get_token("LIARA_API_TOKEN") == "env-wins"
