"""Unit tests for repository details and rate limit error tracking."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from stack_scout.github_client import GitHubClient
from stack_scout.ratelimit import GitHubRateLimiter


@pytest.mark.asyncio
async def test_get_repo_details_parsing():
    client = GitHubClient()
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {
        "description": "Fast and lightweight web framework",
        "stargazers_count": 85000,
        "forks_count": 7000,
        "open_issues_count": 120,
        "language": "Python",
        "license": {"spdx_id": "MIT"},
        "created_at": "2018-12-08T00:00:00Z",
        "pushed_at": "2026-10-20T00:00:00Z",
    }

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get.return_value = mock_resp
    client._http_client = mock_http

    details = await client.get_repo_details("tiangolo", "fastapi")
    assert details is not None
    assert details["stars"] == 85000
    assert details["license_class"] == "permissive"
    assert details["language"] == "Python"
    assert details["forks"] == 7000


def test_rate_limiter_search_error_tracking():
    limiter = GitHubRateLimiter()
    resp_403 = MagicMock(spec=httpx.Response)
    resp_403.status_code = 403
    resp_403.headers = {
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": "1892800000",
    }
    limiter.update_from_headers(resp_403, is_search=True)
    assert limiter.last_search_error is not None
    assert "rate limit reached (HTTP 403)" in limiter.last_search_error

    resp_200 = MagicMock(spec=httpx.Response)
    resp_200.status_code = 200
    resp_200.headers = {"x-ratelimit-remaining": "30"}
    limiter.update_from_headers(resp_200, is_search=True)
    assert limiter.last_search_error is None
