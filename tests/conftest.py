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
