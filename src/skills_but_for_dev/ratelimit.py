"""Rate limit tracking and throttling for GitHub and external APIs."""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class GitHubRateLimiter:
    """Manages separate rate limits for GitHub Search and Core endpoints."""

    def __init__(self):
        # Search rate limit: 30/min max, safe target: 25/min
        self._search_semaphore: asyncio.Semaphore | None = None
        self.search_request_timestamps: list[float] = []
        self._search_lock: asyncio.Lock | None = None
        self._search_lock_loop: asyncio.AbstractEventLoop | None = None
        self._search_semaphore: asyncio.Semaphore | None = None
        self._search_semaphore_loop: asyncio.AbstractEventLoop | None = None

        # Tracked headers
        self.search_remaining: int | None = None
        self.search_reset_at: int | None = None

        self.core_remaining: int | None = None
        self.core_reset_at: int | None = None
        self.last_search_error: str | None = None
        self.last_core_error: str | None = None

    @property
    def search_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._search_lock is None or self._search_lock_loop != loop:
            self._search_lock = asyncio.Lock()
            self._search_lock_loop = loop
        return self._search_lock

    @property
    def search_semaphore(self) -> asyncio.Semaphore:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._search_semaphore is None or self._search_semaphore_loop != loop:
            self._search_semaphore = asyncio.Semaphore(3)
            self._search_semaphore_loop = loop
        return self._search_semaphore

    async def acquire_search_slot(self) -> None:
        """Throttle requests to stay within safe search limit (25/min if authenticated, 8/min if unauthenticated)."""
        from skills_but_for_dev.config import config

        max_allowed = 25 if config.github_token else 8
        async with self.search_lock:
            now = time.time()
            # Clean up timestamps older than 60 seconds
            self.search_request_timestamps = [
                ts for ts in self.search_request_timestamps if now - ts < 60.0
            ]

            if len(self.search_request_timestamps) >= max_allowed:
                oldest = self.search_request_timestamps[0]
                sleep_time = max(0.1, 60.0 - (now - oldest) + 0.5)
                logger.warning(
                    "GitHub Search rate limit throttle: pausing for %.2fs to respect quota. "
                    "Tip: Run 'gh auth login' or set GITHUB_TOKEN to bypass throttling.",
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)

            self.search_request_timestamps.append(time.time())

    @staticmethod
    def _parse_int_header(value: str | None) -> int | None:
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def _update_error_state(self, status_code: int, is_search: bool) -> None:
        if status_code == 200:
            if is_search:
                self.last_search_error = None
            else:
                self.last_core_error = None
            return

        if status_code not in (403, 429):
            return

        reset_at = self.search_reset_at if is_search else self.core_reset_at
        reset_secs = max(0, int((reset_at or 0) - time.time()))

        if is_search:
            self.last_search_error = (
                f"GitHub Search rate limit reached (HTTP {status_code}). "
                f"Resets in {reset_secs}s. Quick fix: run 'gh auth login' or export GITHUB_TOKEN."
            )
        else:
            self.last_core_error = (
                f"GitHub Core API rate limit reached (HTTP {status_code}). "
                f"Resets in {reset_secs}s. Quick fix: run 'gh auth login' or export GITHUB_TOKEN to unlock 5,000 req/hr."
            )

    def update_from_headers(self, response: httpx.Response, is_search: bool = False) -> None:
        """Parse rate limit headers from GitHub response."""
        rem = self._parse_int_header(response.headers.get("x-ratelimit-remaining"))
        rst = self._parse_int_header(response.headers.get("x-ratelimit-reset"))

        if rem is not None:
            if is_search:
                self.search_remaining = rem
            else:
                self.core_remaining = rem

        if rst is not None:
            if is_search:
                self.search_reset_at = rst
            else:
                self.core_reset_at = rst

        self._update_error_state(response.status_code, is_search)

    def can_make_core_request(self, min_remaining: int = 2) -> bool:
        """Return False if core remaining quota is critically low to protect rate limits."""
        if self.core_remaining is not None and self.core_remaining <= min_remaining:
            return False
        return True


rate_limiter = GitHubRateLimiter()

