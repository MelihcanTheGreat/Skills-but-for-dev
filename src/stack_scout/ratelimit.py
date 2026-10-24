"""Rate limit tracking and throttling for GitHub and external APIs."""

import asyncio
import logging
import time
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class GitHubRateLimiter:
    """Manages separate rate limits for GitHub Search and Core endpoints."""

    def __init__(self):
        # Search rate limit: 30/min max, safe target: 25/min
        self.search_semaphore = asyncio.Semaphore(3)
        self.search_request_timestamps: list[float] = []
        self.search_lock = asyncio.Lock()

        # Tracked headers
        self.search_remaining: Optional[int] = None
        self.search_reset_at: Optional[int] = None

        self.core_remaining: Optional[int] = None
        self.core_reset_at: Optional[int] = None

    async def acquire_search_slot(self) -> None:
        """Throttle requests to stay within safe search limit (25/min if authenticated, 8/min if unauthenticated)."""
        from stack_scout.config import config

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
                    "GitHub Search rate limit throttle: pausing for %.2fs", sleep_time
                )
                await asyncio.sleep(sleep_time)

            self.search_request_timestamps.append(time.time())

    def update_from_headers(self, response: httpx.Response, is_search: bool = False) -> None:
        """Parse rate limit headers from GitHub response."""
        remaining_str = response.headers.get("x-ratelimit-remaining")
        reset_str = response.headers.get("x-ratelimit-reset")

        try:
            if remaining_str is not None:
                rem = int(remaining_str)
                if is_search:
                    self.search_remaining = rem
                else:
                    self.core_remaining = rem

            if reset_str is not None:
                rst = int(reset_str)
                if is_search:
                    self.search_reset_at = rst
                else:
                    self.core_reset_at = rst
        except (ValueError, TypeError):
            pass


rate_limiter = GitHubRateLimiter()
