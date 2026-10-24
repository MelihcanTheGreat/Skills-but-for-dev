"""Unit tests for query relaxation fallback mechanisms."""

from unittest.mock import AsyncMock, patch

import pytest

from skills_but_for_dev.github_client import GitHubClient
from skills_but_for_dev.models import RepoScoreBreakdown


def _dummy_breakdown(pop: float = 0.8) -> RepoScoreBreakdown:
    return RepoScoreBreakdown(
        popularity=pop,
        velocity=0.7,
        acceleration=1.0,
        recency=0.9,
        relevance=0.8,
    )


@pytest.mark.asyncio
async def test_query_relaxation_level_1_term_fallback():
    """Verify that if a 3-term query returns 0 results in Bucket A, it relaxes to 2 terms."""
    client = GitHubClient()

    mock_item = {
        "full_name": "py-pdf/pypdf",
        "stargazers_count": 8500,
        "pushed_at": "2026-10-20T10:00:00Z",
        "created_at": "2020-01-01T00:00:00Z",
        "description": "A pure-python PDF library capable of splitting, merging, cropping",
        "license": {"spdx_id": "BSD-3-Clause"},
        "topics": ["pdf", "parser"],
    }

    call_queries = []

    async def mock_search_raw(query: str, sort: str | None = None):
        call_queries.append(query)
        if "invoice" in query:
            return []
        if "parse pdf" in query:
            return [mock_item]
        return []

    client._search_raw = AsyncMock(side_effect=mock_search_raw)

    with patch("skills_but_for_dev.github_client.score_stage1") as mock_score:
        mock_score.return_value = (0.85, _dummy_breakdown(0.8), 0.9)
        results = await client.search_repositories(query="I want a fast python tool to parse pdf invoices")

    # Verify query relaxation executed
    assert len(call_queries) >= 2
    assert any("invoice" in q for q in call_queries)
    assert any("parse pdf" in q and "invoice" not in q for q in call_queries)
    assert len(results) > 0
    assert results[0].full_name == "py-pdf/pypdf"
    await client.close()


@pytest.mark.asyncio
async def test_query_relaxation_level_2_language_fallback():
    """Verify that if language filter causes 0 results, it relaxes the language constraint."""
    client = GitHubClient()

    mock_item = {
        "full_name": "pymupdf/PyMuPDF",
        "stargazers_count": 14000,
        "pushed_at": "2026-10-22T10:00:00Z",
        "created_at": "2018-01-01T00:00:00Z",
        "description": "PyMuPDF is a high performance data extraction library",
        "license": {"spdx_id": "AGPL-3.0"},
        "topics": ["pdf", "c++"],
    }

    call_queries = []

    async def mock_search_raw(query: str, sort: str | None = None):
        call_queries.append(query)
        if "language:" in query:
            return []
        return [mock_item]

    client._search_raw = AsyncMock(side_effect=mock_search_raw)

    with patch("skills_but_for_dev.github_client.score_stage1") as mock_score:
        mock_score.return_value = (0.75, _dummy_breakdown(0.9), 0.8)
        results = await client.search_repositories(query="pdf extraction python")

    assert any("language:python" in q for q in call_queries)
    assert any("language:" not in q for q in call_queries)
    assert len(results) > 0
    assert results[0].full_name == "pymupdf/PyMuPDF"
    await client.close()


@pytest.mark.asyncio
async def test_query_relaxation_level_3_wide_net_fallback():
    """Verify that if both Bucket A and B yield 0 items, wide-net search (stars:>15) triggers."""
    client = GitHubClient()

    mock_item = {
        "full_name": "niche/brand-new-ai-tool",
        "stargazers_count": 25,
        "pushed_at": "2026-10-24T10:00:00Z",
        "created_at": "2026-10-01T00:00:00Z",
        "description": "Brand new niche library",
        "license": {"spdx_id": "MIT"},
        "topics": [],
    }

    call_queries = []

    async def mock_search_raw(query: str, sort: str | None = None):
        call_queries.append(query)
        if "stars:>15" in query:
            return [mock_item]
        return []

    client._search_raw = AsyncMock(side_effect=mock_search_raw)

    with patch("skills_but_for_dev.github_client.score_stage1") as mock_score:
        mock_score.return_value = (0.6, _dummy_breakdown(0.5), 0.5)
        results = await client.search_repositories(query="brand-new niche tool")

    assert any("stars:>15" in q for q in call_queries)
    assert len(results) > 0
    assert results[0].full_name == "niche/brand-new-ai-tool"
    await client.close()
