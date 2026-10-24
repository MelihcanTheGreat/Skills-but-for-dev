"""PyPI download statistics client for measuring real-world production adoption."""

import logging
import math

import httpx

from skills_but_for_dev.cache import cache, make_cache_key
from skills_but_for_dev.config import config

logger = logging.getLogger(__name__)
PYPI_STATS_BASE = "https://pypistats.org/api/packages"


class PyPIClient:
    """Fetches real-world download metrics from pypistats.org with caching."""

    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        is_closed = getattr(self._http_client, "is_closed", False)
        if not isinstance(is_closed, bool):
            is_closed = False
        if self._http_client is None or is_closed:
            self._http_client = httpx.AsyncClient(timeout=8.0, follow_redirects=True)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def get_monthly_downloads(self, package_name: str) -> int | None:
        """Fetch 30-day download count from pypistats.org. Cached for 24 hours."""
        clean_name = package_name.strip().lower()
        if not clean_name:
            return None

        cache_key = make_cache_key("pypi_downloads_30d", package=clean_name)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached.get("downloads")

        try:
            url = f"{PYPI_STATS_BASE}/{clean_name}/recent"
            resp = await self.http_client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                downloads = data.get("last_month")
                await cache.set(cache_key, {"downloads": downloads}, ttl_seconds=24 * 3600)
                return downloads
            elif resp.status_code == 404:
                # Cache miss to avoid hammering PyPI for non-Python repos
                await cache.set(cache_key, {"downloads": None}, ttl_seconds=24 * 3600)
                return None
            else:
                logger.debug("pypistats returned %s for %s", resp.status_code, clean_name)
                return None
        except Exception as e:
            logger.debug("Error fetching PyPI stats for %s: %s", clean_name, e)
            return None

    async def get_repo_downloads(self, repo_name: str) -> int | None:
        """Try resolving a repository name to its corresponding PyPI package."""
        candidates = [repo_name.lower()]

        # Common package naming conventions: python-xxx -> xxx, xxx-python -> xxx
        if repo_name.lower().startswith("python-"):
            candidates.append(repo_name.lower().replace("python-", ""))
        elif repo_name.lower().endswith("-python"):
            candidates.append(repo_name.lower().replace("-python", ""))

        for candidate in candidates:
            count = await self.get_monthly_downloads(candidate)
            if count is not None and count > 0:
                return count

        return None


def calculate_pypi_adoption_score(downloads_30d: int | None) -> tuple[float, bool]:
    """Normalize monthly PyPI downloads on log10 scale:

    10M+ downloads/mo = 1.0, 1M = ~0.86, 100k = ~0.71, 10k = ~0.57.
    Returns (score, is_prior).
    """
    if downloads_30d is None:
        return config.weights.prior, True

    if downloads_30d <= 0:
        return 0.0, False

    # Log10 scale up to 10M downloads (10^7 = 7.0)
    score = math.log10(downloads_30d + 1.0) / 7.0
    return min(1.0, max(0.0, round(score, 3))), False


pypi_client = PyPIClient()
