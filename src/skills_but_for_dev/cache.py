"""Asynchronous SQLite cache with WAL mode and TTL support."""

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import aiosqlite

from skills_but_for_dev.config import config

logger = logging.getLogger(__name__)


def make_cache_key(namespace: str, *args: Any, **kwargs: Any) -> str:
    """Generate a deterministic SHA-256 cache key from namespace and arguments."""
    payload = {
        "ns": namespace,
        "args": args,
        "kwargs": {k: kwargs[k] for k in sorted(kwargs.keys())},
    }
    dumped = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class CacheManager:
    """Manages SQLite cache with WAL mode and connection safety."""

    def __init__(self, db_dir: Path | None = None):
        self.db_dir = db_dir or config.cache_dir
        self.db_path = self.db_dir / "cache.db"
        self._db: aiosqlite.Connection | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock_obj: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._initialized = False

    @property
    def lock(self) -> asyncio.Lock:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._lock_obj is None or self._lock_loop != current_loop:
            self._lock_obj = asyncio.Lock()
            self._lock_loop = current_loop
        return self._lock_obj

    async def _init_db(self) -> None:
        """Create directory and table with WAL and busy timeout pragmas."""
        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if self._db and self._loop != current_loop:
                self._db = None
                self._initialized = False
            self._loop = current_loop

            self.db_dir.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(str(self.db_path))
            if hasattr(self._db, "_thread") and self._db._thread:
                self._db._thread.daemon = True
            await self._db.execute("PRAGMA journal_mode=WAL;")
            await self._db.execute("PRAGMA busy_timeout=5000;")
            await self._db.execute("PRAGMA synchronous=NORMAL;")
            await self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries (expires_at)"
            )
            await self._db.commit()
            self._initialized = True
        except Exception as e:
            logger.warning("Cache init failed, attempting rebuild: %s", e)
            try:
                if self._db:
                    await self._db.close()
                if self.db_path.exists():
                    self.db_path.unlink()
                self._db = await aiosqlite.connect(str(self.db_path))
                await self._db.execute("PRAGMA journal_mode=WAL;")
                await self._db.execute("PRAGMA busy_timeout=5000;")
                await self._db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )
                await self._db.commit()
                self._initialized = True
            except Exception as e_rebuild:
                logger.error("Cache complete failure: %s", e_rebuild)
                self._db = None
                self._initialized = False

    async def get(self, key: str) -> Any | None:
        """Fetch unexpired cached item. Returns None on cache miss, expiry, or error."""
        async with self.lock:
            if not self._initialized or not self._db:
                await self._init_db()
            if not self._db:
                return None

            try:
                now = time.time()
                async with self._db.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                    (key,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    val_str, expires_at = row
                    if expires_at <= now:
                        return None
                    return json.loads(val_str)
            except Exception as e:
                logger.debug("Cache get error for key %s: %s", key, e)
                return None

    async def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store item in cache with TTL. Fails gracefully without throwing."""
        async with self.lock:
            if not self._initialized or not self._db:
                await self._init_db()
            if not self._db:
                return

            try:
                now = time.time()
                expires_at = now + ttl_seconds
                val_str = json.dumps(value, default=str)
                await self._db.execute(
                    """
                    INSERT INTO cache_entries (key, value, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        expires_at = excluded.expires_at
                    """,
                    (key, val_str, expires_at),
                )
                await self._db.commit()
            except Exception as e:
                logger.debug("Cache set error for key %s: %s", key, e)

    async def close(self) -> None:
        """Close cache connection."""
        async with self.lock:
            if self._db:
                try:
                    await self._db.close()
                except Exception:
                    pass
                self._db = None
                self._initialized = False


# Global cache instance
cache = CacheManager()

