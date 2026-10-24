"""Unit tests for cache and configuration."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from stack_scout.cache import CacheManager, make_cache_key
from stack_scout.models import GitHubRepoCandidate, StarVelocity


@pytest.mark.asyncio
async def test_cache_set_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CacheManager(db_dir=Path(tmpdir))
        try:
            key = make_cache_key("test", 123, query="speech")

            # Initial get should be None
            val = await cm.get(key)
            assert val is None

            # Store data
            data = {"hello": "world", "count": 42}
            await cm.set(key, data, ttl_seconds=10)

            # Retrieve data
            retrieved = await cm.get(key)
            assert retrieved == data
        finally:
            await cm.close()


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CacheManager(db_dir=Path(tmpdir))
        try:
            key = make_cache_key("test_expiry", "foo")

            # Set with 0.3 second TTL
            await cm.set(key, "bar", ttl_seconds=0.3)
            assert await cm.get(key) == "bar"

            # Wait for expiry
            await asyncio.sleep(0.4)
            assert await cm.get(key) is None
        finally:
            await cm.close()


def test_models_serialization():
    vel = StarVelocity(v4=12.5, v12=10.0, accel=1.25, rel_v4=0.005)
    repo = GitHubRepoCandidate(
        full_name="owner/sample-repo",
        name="sample-repo",
        owner="owner",
        url="https://github.com/owner/sample-repo",
        description="A great repo",
        stars=2500,
        pushed_days_ago=5,
        created_days_ago=200,
        bucket="A",
        velocity=vel,
    )
    dumped = repo.model_dump()
    assert dumped["name"] == "sample-repo"
    assert dumped["velocity"]["accel"] == 1.25
