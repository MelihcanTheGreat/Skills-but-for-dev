"""Scoring engine with conservative priors and two-stage ranking."""

import math

from skills_but_for_dev.config import config
from skills_but_for_dev.models import (
    ConfidenceLevel,
    GitHubRepoCandidate,
    RepoScoreBreakdown,
)


def calculate_popularity_score(stars: int) -> float:
    """Normalize stars on log10 scale: 100k+ stars = 1.0, 100 stars = ~0.4."""
    if stars <= 0:
        return 0.0
    val = math.log10(stars + 1) / 5.0
    return min(1.0, max(0.0, val))


def calculate_recency_score(days_since_push: int) -> float:
    """Exponential decay: 0 days = 1.0, 90 days = ~0.37, 180 days = ~0.13."""
    days = max(0, days_since_push)
    return math.exp(-days / 90.0)


def calculate_velocity_score(v4: float | None) -> tuple[float, bool]:
    """Normalize daily star velocity (v4): 300+ stars/day = 1.0."""
    if v4 is None:
        return config.weights.prior, True
    val = math.log10(max(0.0, v4) + 1.0) / 2.5
    return min(1.0, max(0.0, val)), False


def calculate_acceleration_score(accel: float | None) -> tuple[float, bool]:
    """Sigmoid on (accel - 1): accel=1 -> 0.5, accel=2 -> ~0.88, accel=0.5 -> ~0.27."""
    if accel is None:
        return config.weights.prior, True
    diff = accel - 1.0
    # Sigmoid with scaling factor 2.0
    val = 1.0 / (1.0 + math.exp(-2.0 * diff))
    return min(1.0, max(0.0, val)), False


def calculate_relevance_score(
    query_terms: list[str],
    name: str,
    description: str | None,
    topics: list[str],
) -> float:
    """BM25-lite keyword relevance score across name, topics, and description."""
    if not query_terms:
        return 0.5

    name_lower = name.lower()
    desc_lower = (description or "").lower()
    topics_lower = [t.lower() for t in topics]

    term_scores: list[float] = []
    for term in query_terms:
        t = term.lower()
        score = 0.0
        # Exact match in name is highest weight
        if t in name_lower:
            score += 0.50
        # Match in topics
        if any(t in topic for topic in topics_lower):
            score += 0.35
        # Match in description
        if t in desc_lower:
            score += 0.15
        term_scores.append(min(1.0, score))

    return sum(term_scores) / len(term_scores)


def calculate_license_penalty(license_class: str, commercial_use: bool) -> float:
    """Determine penalty based on commercial viability requirements."""
    if not commercial_use:
        return 0.0

    if license_class == "strong_copyleft":
        return 0.15
    elif license_class in ("non_commercial", "unknown"):
        return 0.30
    elif license_class == "custom":
        return 0.05
    return 0.0


def score_stage1(
    candidate: GitHubRepoCandidate,
    query_terms: list[str],
    commercial_use: bool = False,
) -> tuple[float, RepoScoreBreakdown, ConfidenceLevel]:
    """Compute Stage 1 candidate score across the 12 shortlisted candidates."""
    priors_used: list[str] = []

    # 1. Popularity
    s_pop = calculate_popularity_score(candidate.stars)

    # 2. Recency
    s_rec = calculate_recency_score(candidate.pushed_days_ago)

    # 3. Velocity
    v4 = candidate.velocity.v4 if candidate.velocity else None
    s_vel, vel_prior = calculate_velocity_score(v4)
    if vel_prior:
        priors_used.append("velocity")

    # 4. Acceleration
    accel = candidate.velocity.accel if candidate.velocity else None
    s_acc, acc_prior = calculate_acceleration_score(accel)
    if acc_prior:
        priors_used.append("acceleration")

    # 5. Relevance
    s_rel = calculate_relevance_score(
        query_terms, candidate.name, candidate.description, candidate.topics
    )

    w = config.weights
    raw_score = (
        w.popularity * s_pop
        + w.velocity * s_vel
        + w.acceleration * s_acc
        + w.recency * s_rec
        + w.relevance * s_rel
    )

    penalty = calculate_license_penalty(candidate.license_class, commercial_use)
    final_score = max(0.0, raw_score - penalty)

    breakdown = RepoScoreBreakdown(
        popularity=round(s_pop, 3),
        velocity=round(s_vel, 3),
        acceleration=round(s_acc, 3),
        recency=round(s_rec, 3),
        relevance=round(s_rel, 3),
        priors_used=priors_used,
    )

    confidence: ConfidenceLevel = "low" if priors_used else "high"
    return round(final_score, 4), breakdown, confidence


def score_stage2_finalists(
    finalists: list[GitHubRepoCandidate],
) -> list[GitHubRepoCandidate]:
    """Re-rank the top 3 finalists incorporating maintenance scores and real-world PyPI adoption."""
    from skills_but_for_dev.pypi_client import calculate_pypi_adoption_score

    w = config.weights
    for cand in finalists:
        m_score = cand.maintenance_score
        if m_score is None:
            m_score = w.prior
            if cand.score_breakdown:
                cand.score_breakdown.priors_used.append("maintenance")
            cand.confidence = "low"

        pypi_score, pypi_prior = calculate_pypi_adoption_score(cand.pypi_downloads_30d)
        if pypi_prior and cand.score_breakdown:
            cand.score_breakdown.priors_used.append("pypi_adoption")

        # Balanced formula: 80% stage1 score + 10% maintenance + 10% real PyPI adoption
        combined = 0.80 * cand.score + 0.10 * m_score + 0.10 * pypi_score
        cand.score = round(combined, 4)
        if cand.score_breakdown:
            cand.score_breakdown.maintenance = round(m_score, 3)
            cand.score_breakdown.pypi_adoption = round(pypi_score, 3)

    return sorted(finalists, key=lambda c: c.score, reverse=True)

