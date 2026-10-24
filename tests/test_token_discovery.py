"""Unit tests for GitHub token discovery and unauthenticated quota protection."""

from unittest.mock import MagicMock, patch

import pytest

from skills_but_for_dev.config import Settings, detect_github_token
from skills_but_for_dev.github_client import GitHubClient
from skills_but_for_dev.ratelimit import rate_limiter


def test_detect_github_token_from_env():
    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test_token_12345"}):
        token, source = detect_github_token()
        assert token == "ghp_test_token_12345"
        assert source == "env"

    with patch.dict("os.environ", {"GITHUB_TOKEN": "", "GH_TOKEN": "ghp_from_gh_env"}):
        token, source = detect_github_token()
        assert token == "ghp_from_gh_env"
        assert source == "env"


def test_detect_github_token_from_gh_cli():
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "gho_mocked_cli_token_abc\n"

    with patch.dict("os.environ", {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=True):
        with patch("shutil.which", return_value="/usr/bin/gh"):
            with patch("subprocess.run", return_value=mock_res):
                token, source = detect_github_token()
                assert token == "gho_mocked_cli_token_abc"
                assert source == "gh_cli"


def test_detect_github_token_none():
    with patch.dict("os.environ", {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=True):
        with patch("shutil.which", return_value=None):
            token, source = detect_github_token()
            assert token is None
            assert source == "none"


def test_settings_initializes_token_source():
    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_sample"}, clear=True):
        s = Settings()
        assert s.github_token == "ghp_sample"
        assert s.token_source == "env"


@pytest.mark.asyncio
async def test_get_star_velocity_estimated_fallback_when_core_quota_low():
    client = GitHubClient()

    # Simulate low core remaining quota (e.g., 2 remaining)
    rate_limiter.core_remaining = 2

    # Call get_star_velocity - should fallback to estimated without calling API
    vel, anomaly = await client.get_star_velocity(
        owner="test-owner", repo="test-repo", stars=1200, created_days_ago=400
    )

    assert vel.source == "estimated"
    assert vel.v4 > 0
    assert anomaly is None

    # Reset core_remaining
    rate_limiter.core_remaining = None
    await client.close()
