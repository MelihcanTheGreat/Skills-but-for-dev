"""Unit tests for scoring engine and anomaly detection rules."""

import pytest
from stack_scout.config import config
from stack_scout.models import GitHubRepoCandidate, StarVelocity
from stack_scout.scoring import (
    calculate_acceleration_score,
    calculate_popularity_score,
    calculate_recency_score,
    calculate_relevance_score,
    calculate_velocity_score,
    score_stage1,
    score_stage2_finalists,
)


def test_popularity_normalization():
    assert calculate_popularity_score(0) == 0.0
    # 100k stars = log10(100001) / 5 ~= 1.0
    assert pytest.approx(calculate_popularity_score(100000), 0.01) == 1.0
    # 100 stars
    assert 0.35 <= calculate_popularity_score(100) <= 0.45


def test_recency_exponential_decay():
    assert calculate_recency_score(0) == 1.0
    assert pytest.approx(calculate_recency_score(90), 0.05) == 0.367
    assert calculate_recency_score(365) < 0.05


def test_velocity_and_acceleration_priors():
    # When missing, should return conservative prior (0.25) and flag used_prior=True
    vel_score, vel_prior = calculate_velocity_score(None)
    assert vel_score == config.weights.prior
    assert vel_prior is True

    acc_score, acc_prior = calculate_acceleration_score(None)
    assert acc_score == config.weights.prior
    assert acc_prior is True

    # Real velocity
    v_score_real, v_prior_real = calculate_velocity_score(50.0)
    assert v_prior_real is False
    assert v_score_real > 0.5


def test_relevance_matching():
    query = ["speaker", "diarization"]
    # Exact match in name should score high
    high_score = calculate_relevance_score(
        query, name="pyannote-speaker-diarization", description=None, topics=[]
    )
    assert high_score >= 0.5

    # Completely unrelated
    low_score = calculate_relevance_score(
        query, name="unrelated-calc", description="simple math", topics=["math"]
    )
    assert low_score == 0.0


def test_stage1_scoring_with_prior_flags_confidence_low():
    cand = GitHubRepoCandidate(
        full_name="test/repo",
        name="repo",
        owner="test",
        url="https://github.com/test/repo",
        stars=1000,
        pushed_days_ago=5,
        created_days_ago=100,
        bucket="A",
        velocity=StarVelocity(source="unavailable"),  # Missing velocity!
    )
    score, breakdown, conf = score_stage1(cand, query_terms=["repo"])
    assert conf == "low"
    assert "velocity" in breakdown.priors_used
    assert "acceleration" in breakdown.priors_used
    assert score > 0.0


def test_stage2_finalists_reranking():
    cand1 = GitHubRepoCandidate(
        full_name="a/finalist1",
        name="f1",
        owner="a",
        url="https://github.com/a/f1",
        stars=5000,
        pushed_days_ago=2,
        created_days_ago=300,
        bucket="A",
        score=0.80,
        maintenance_score=0.20,  # poor maintenance
    )
    cand2 = GitHubRepoCandidate(
        full_name="b/finalist2",
        name="f2",
        owner="b",
        url="https://github.com/b/f2",
        stars=3000,
        pushed_days_ago=1,
        created_days_ago=250,
        bucket="A",
        score=0.75,
        maintenance_score=0.95,  # stellar maintenance
    )

    re_ranked = score_stage2_finalists([cand1, cand2])
    # cand2 has lower stage 1 (0.75 vs 0.80), but much better maintenance (0.95 vs 0.20):
    # cand1 combined: 0.85 * 0.80 + 0.15 * 0.20 = 0.68 + 0.03 = 0.71
    # cand2 combined: 0.85 * 0.75 + 0.15 * 0.95 = 0.6375 + 0.1425 = 0.78
    assert re_ranked[0].full_name == "b/finalist2"
