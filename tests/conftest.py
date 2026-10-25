"""Pytest configuration and global fixtures for skills-but-for-dev test suite."""

import os
from pathlib import Path

import pytest

# Disable DBus/SecretService keyring calls in headless environments
os.environ["PYTHONKEYRING_BACKEND"] = "keyring.backends.null.Keyring"


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure every test runs with an isolated temporary cache directory and CI flags."""
    monkeypatch.setenv("SKILLS_BUT_FOR_DEV_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("PYTHONKEYRING_BACKEND", "keyring.backends.null.Keyring")

    from skills_but_for_dev.cache import cache
    from skills_but_for_dev.config import config

    config.cache_dir = tmp_path
    cache.db_dir = tmp_path
    cache.db_path = tmp_path / "cache.db"


@pytest.fixture(autouse=True)
async def cleanup_global_singletons():
    """Ensure background connections are closed so worker threads do not block exit."""
    yield
    from skills_but_for_dev.cache import cache
    from skills_but_for_dev.github_client import github_client
    from skills_but_for_dev.pypi_client import pypi_client

    try:
        await cache.close()
    except Exception:
        pass
    try:
        await github_client.close()
    except Exception:
        pass
    try:
        await pypi_client.close()
    except Exception:
        pass
