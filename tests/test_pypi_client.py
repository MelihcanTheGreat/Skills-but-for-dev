"""Unit tests for PyPI download statistics client and adoption scoring."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills_but_for_dev.config import config
from skills_but_for_dev.pypi_client import PyPIClient, calculate_pypi_adoption_score


def test_calculate_pypi_adoption_score():
    # When no PyPI data is available, fallback to conservative prior
    score, is_prior = calculate_pypi_adoption_score(None)
    assert is_prior is True
    assert score == config.weights.prior

    # Zero or negative downloads
    score_zero, is_prior_zero = calculate_pypi_adoption_score(0)
    assert is_prior_zero is False
    assert score_zero == 0.0

    score_neg, _ = calculate_pypi_adoption_score(-10)
    assert score_neg == 0.0

    # 10M downloads should cap at 1.0
    score_10m, is_prior_10m = calculate_pypi_adoption_score(10_000_000)
    assert is_prior_10m is False
    assert score_10m == 1.0

    # Intermediate scores: 100k downloads (~0.71)
    score_100k, _ = calculate_pypi_adoption_score(100_000)
    assert 0.70 <= score_100k <= 0.73


@pytest.mark.asyncio
async def test_get_monthly_downloads_success():
    client = PyPIClient()
    pkg_name = f"test-pkg-{uuid.uuid4().hex[:8]}"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"last_month": 150000}}

    with patch.object(client.http_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        # First call fetches from API
        downloads = await client.get_monthly_downloads(pkg_name)
        assert downloads == 150000
        assert mock_get.call_count == 1

        # Second call should hit the cache
        cached_downloads = await client.get_monthly_downloads(pkg_name)
        assert cached_downloads == 150000
        assert mock_get.call_count == 1  # No additional network call

    await client.close()


@pytest.mark.asyncio
async def test_get_monthly_downloads_not_found():
    client = PyPIClient()
    pkg_name = f"nonexistent-pkg-{uuid.uuid4().hex[:8]}"

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch.object(client.http_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        downloads = await client.get_monthly_downloads(pkg_name)
        assert downloads is None
        assert mock_get.call_count == 1

        # Cached negative result
        cached_downloads = await client.get_monthly_downloads(pkg_name)
        assert cached_downloads is None
        assert mock_get.call_count == 1

    await client.close()


@pytest.mark.asyncio
async def test_get_repo_downloads_with_prefix_resolution():
    client = PyPIClient()

    async def mock_get_monthly(pkg_name: str):
        if pkg_name == "dotenv":
            return 8000000
        return None

    with patch.object(client, "get_monthly_downloads", side_effect=mock_get_monthly):
        # Testing resolving "python-dotenv" -> "dotenv"
        downloads = await client.get_repo_downloads("python-dotenv")
        assert downloads == 8000000

    await client.close()
